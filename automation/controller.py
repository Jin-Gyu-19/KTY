"""Playwright 브라우저 컨트롤러.

Playwright 동기 API 객체는 스레드에 묶여 있어서, 브라우저 관련 모든 호출을
'단일 워커 스레드' 안에서만 실행해야 한다. Flask 는 여러 요청을 여러 스레드로
처리하므로, 요청 스레드는 여기 submit() 으로 작업을 워커에 넘기고 결과만 받는다.

한 번에 사이트 하나만 다룬다(퇴사 처리는 순차 진행이므로 충분).
사용자가 브라우저에서 직접 로그인할 수 있도록 headed 모드로 띄운다.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable


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
        self._context = None
        self._page = None

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
            if self._context is not None:
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
        self._context = None
        self._page = None

    # ---- 브라우저 조작 (모두 submit 경유) ----
    def _ensure_context(self):
        if self._context is None:
            # persistent context: 쿠키/세션이 data/.browser 에 남아 재로그인 부담을 줄인다.
            import os

            profile = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", ".browser"
            )
            os.makedirs(profile, exist_ok=True)
            self._context = self._pw.chromium.launch_persistent_context(
                profile, headless=False, args=["--start-maximized"]
            )
        return self._context

    def open_site(self, url: str) -> None:
        """사이트를 새 창(페이지)으로 연다. 사용자는 여기서 직접 로그인한다."""

        def _do():
            ctx = self._ensure_context()
            self._page = ctx.pages[0] if ctx.pages else ctx.new_page()
            self._page.goto(url, wait_until="domcontentloaded")
            self._page.bring_to_front()

        self.submit(_do)

    def run_scenario(self, scenario, employee) -> Any:
        """열려 있는 페이지에서 시나리오를 실행한다."""

        def _do():
            if self._page is None:
                raise RuntimeError("먼저 사이트를 열어야 합니다.")
            return scenario.run(self._page, employee)

        return self.submit(_do)


# Flask 앱에서 공유하는 단일 인스턴스
controller = BrowserController()
