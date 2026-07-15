"""Playwright 브라우저 컨트롤러.

Playwright 동기 API 객체는 스레드에 묶여 있어서, 브라우저 관련 모든 호출을
'단일 워커 스레드' 안에서만 실행해야 한다. Flask 는 여러 요청을 여러 스레드로
처리하므로, 요청 스레드는 여기 submit() 으로 작업을 워커에 넘기고 결과만 받는다.

두 가지 브라우저 모드를 지원한다:
  1) launch(기본)  : Playwright 전용 크로미움 창을 새로 띄운다. 사용자가 그 창에서
                     직접 로그인한다. 세션은 data/.browser 프로필에 유지된다.
  2) attach        : 환경변수 BROWSER_CDP_URL(예: http://127.0.0.1:9222)이 있으면
                     이미 실행 중인(사용자가 로그인해 둔) 크롬/엣지에 붙는다.
                     사용자가 미리 열어 로그인한 탭을 그대로 감지해서 조작한다.
                     엣지에서:
                       msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\\edge-debug"
"""

from __future__ import annotations

import os
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse


@dataclass
class _Job:
    fn: Callable[[], Any]
    done: threading.Event
    result: Any = None
    error: BaseException | None = None


class BrowserController:
    def __init__(self) -> None:
        self._jobs: "queue.Queue[_Job | None]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        # attach 여부는 첫 브라우저 사용 시점(_ensure_context)에서 env 로 판단한다.
        self._attached = False

    # ---- 워커 스레드 ----
    def _worker(self) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        try:
            while True:
                job = self._jobs.get()
                if job is None:  # 종료 신호
                    break
                try:
                    job.result = job.fn()
                except BaseException as exc:  # noqa: BLE001 - 호출자에게 전달
                    job.error = exc
                finally:
                    job.done.set()
        finally:
            # attach 모드에서는 사용자의 브라우저이므로 컨텍스트를 닫지 않는다.
            if self._context is not None and not self._attached:
                try:
                    self._context.close()
                except Exception:
                    pass
            self._pw.stop()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def submit(self, fn: Callable[[], Any]) -> Any:
        """워커 스레드에서 fn 을 실행하고 결과를 받아온다(블로킹)."""
        self.start()
        job = _Job(fn=fn, done=threading.Event())
        self._jobs.put(job)
        job.done.wait()
        if job.error is not None:
            raise job.error
        return job.result

    def stop(self) -> None:
        if self._thread and self._thread.is_alive():
            self._jobs.put(None)
            self._thread.join(timeout=10)
        self._thread = None
        self._browser = None
        self._context = None
        self._page = None
        self._attached = False

    # ---- 브라우저 조작 (모두 submit 경유) ----
    def _context_alive(self) -> bool:
        """현재 컨텍스트/브라우저가 살아있는지 확인한다(사용자가 창을 닫았을 수 있음)."""
        if self._context is None:
            return False
        try:
            _ = self._context.pages  # 닫힌 컨텍스트면 예외
            br = self._context.browser
            if br is not None and not br.is_connected():
                return False
            return True
        except Exception:
            return False

    def _reset_browser(self) -> None:
        self._browser = None
        self._context = None
        self._page = None
        self._attached = False

    def _ensure_context(self):
        # 사용자가 창을 닫아 컨텍스트가 죽었으면 새로 만든다.
        if self._context is not None and not self._context_alive():
            self._reset_browser()
        if self._context is not None:
            return self._context

        cdp_url = os.environ.get("BROWSER_CDP_URL", "").strip()
        if cdp_url:
            # attach 모드: 이미 떠 있는 크롬/엣지에 붙어 로그인 세션을 재사용한다.
            self._browser = self._pw.chromium.connect_over_cdp(cdp_url)
            if self._browser.contexts:
                self._context = self._browser.contexts[0]
            else:
                self._context = self._browser.new_context()
            self._attached = True
        else:
            # launch 모드: 전용 크로미움 창. 세션은 data/.browser 에 유지.
            profile = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", ".browser"
            )
            os.makedirs(profile, exist_ok=True)
            self._context = self._pw.chromium.launch_persistent_context(
                profile, headless=False, args=["--start-maximized"]
            )
            self._attached = False
        return self._context

    def open_site(self, url: str) -> None:
        """사이트를 연다.

        attach 모드: 같은 호스트로 이미 열려 있는(로그인된) 탭이 있으면 그 탭을
                     그대로 감지해서 사용한다. 없으면 새 탭을 열어 이동한다.
        launch 모드: 전용 창에서 해당 URL 로 이동한다(사용자가 거기서 로그인).
        """

        def _do():
            ctx = self._ensure_context()
            host = (urlparse(url).hostname or "").lower()

            page = None
            if self._attached and host:
                # 사용자가 미리 열어둔 탭 감지 (같은 호스트)
                for p in ctx.pages:
                    try:
                        if host in (p.url or "").lower():
                            page = p
                            break
                    except Exception:
                        continue

            if page is None:
                if self._attached:
                    # 붙은 브라우저에는 새 탭을 열어 이동 (기존 탭은 건드리지 않음)
                    page = ctx.new_page()
                else:
                    # 전용 창: 살아있는 탭 재사용, 없으면 새 탭
                    living = [p for p in ctx.pages if not p.is_closed()]
                    page = living[0] if living else ctx.new_page()
                page.goto(url, wait_until="domcontentloaded")

            self._page = page
            page.bring_to_front()

        self.submit(_do)

    def run_scenario(self, scenario, employee) -> Any:
        """열려 있는 페이지에서 시나리오를 실행한다."""

        def _do():
            if (
                self._page is None
                or self._page.is_closed()
                or not self._context_alive()
            ):
                raise RuntimeError(
                    "자동화 브라우저가 닫혀 있습니다. [열기]를 다시 눌러 로그인한 뒤 진행해 주세요."
                )
            return scenario.run(self._page, employee)

        return self.submit(_do)


# Flask 앱에서 공유하는 단일 인스턴스
controller = BrowserController()
