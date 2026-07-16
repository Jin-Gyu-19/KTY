"""Accio (bdo.accio.kr) 퇴사 처리 시나리오 — 계정 삭제.

처리 = 계정 삭제(되돌릴 수 없음). 그래서 안전을 최우선으로 짠다.

안전 원칙(그룹웨어와 동일한 철학):
  1) 로그인은 앱에 저장된 ID/PW 로 자동 입력한다(저장 정보 없으면 사람이 직접).
  2) 대상 검색 결과가 '정확히 1건'일 때만 선택한다(동명이인/오탐 방지).
  3) 행/팝업의 이름·ID 를 입력값과 대조해 엉뚱한 계정 삭제를 막는다.
  4) '삭제' 버튼까지만 자동으로 누르고, **삭제 확인창 직전에서 멈춘다.**
     최종 확정(확인/예/삭제)은 절대 자동으로 누르지 않는다 → 사람이 마무리.

★ 실제 화면 셀렉터는 아래 상수에 채운다(브라우저 F12 → Elements 로 확인).
  아직 셀렉터가 비어 있으면 자동화를 시도하지 않고 '수동 처리' 안내만 한다.
  → 그래서 이 파일을 등록해두고 회사PC에서 pull 받아도 사고가 나지 않는다.
"""

from __future__ import annotations

import os

from .base import Employee, SiteScenario, StepResult

# 진단 스크린샷/로그 저장 위치 (프로젝트/data)
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)

# ─────────────────────────────────────────────────────────────────────────
# 실제 화면 셀렉터 (F12 로 확인해서 채운다). 비어 있으면 자동화 안 함(수동 안내).
# ─────────────────────────────────────────────────────────────────────────
# 1) 로그인 페이지
LOGIN_ID_INPUT = ""      # 예: "#userId" / "input[name='loginId']"
LOGIN_PW_INPUT = ""      # 예: "#userPw" / "input[type='password']"
LOGIN_BUTTON = ""        # 예: "#loginBtn" / "button:has-text('로그인')"

# 2) 계정(사용자) 관리 화면
USER_ADMIN_URL = ""      # 로그인 후 계정관리 목록의 주소(있으면 직접 이동)
SEARCH_INPUT = ""        # 이름/ID 검색창
SEARCH_BUTTON = ""       # 검색 실행 버튼

# 3) 검색 결과 → 삭제
RESULT_ROW = ""          # 결과 행 셀렉터(이 행 안에 이름/ID 가 보임). has_text=이름 으로 좁힘
DELETE_BUTTON = ""       # '삭제' 버튼(행 안 또는 상단 툴바)
# (선택) 삭제가 사이트 자체 모달을 띄우면, 그 모달의 '대상 이름/ID' 셀렉터로 대조
CONFIRM_MODAL_NAME = ""  # 예: 모달 안 대상 이름이 보이는 요소

# 검색창이 뜰 때까지 기다리는 최대 시간(ms)
SEARCH_READY_MS = 8000


class AccioScenario(SiteScenario):
    id = "accio"
    name = "Accio (bdo.accio.kr)"
    kind = "browser"
    url = "https://bdo.accio.kr/"
    login_required = True
    # 계정 삭제는 되돌릴 수 없다. 확인창 직전에서 멈추고 사람이 확정한다.
    auto_submit = False

    # ── 아직 셀렉터가 안 채워졌는지 판단 ───────────────────────────────
    def _configured(self) -> bool:
        """자동화에 꼭 필요한 셀렉터가 모두 채워졌는지."""
        return all([SEARCH_INPUT, RESULT_ROW, DELETE_BUTTON])

    # ── 진단(그룹웨어와 동일한 방식) ──────────────────────────────────
    def _diagnose(self, page) -> str:
        parts = []
        for label, fn in (
            ("주소", lambda: page.url),
            ("제목", lambda: f"'{page.title()}'"),
        ):
            try:
                parts.append(f"{label}={fn()}")
            except Exception:
                pass
        try:
            if page.locator("input[type=password]:visible").count() > 0:
                parts.append("※보이는 비밀번호칸 있음→자동화 창이 로그인 안 됐을 수 있음")
        except Exception:
            pass
        text = " / ".join(parts)
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            shot = os.path.join(_DATA_DIR, "accio_error.png")
            for kwargs in ({"full_page": True}, {}):
                try:
                    page.screenshot(path=shot, **kwargs)
                    text += f" / 스크린샷={shot}"
                    break
                except Exception:
                    continue
            with open(os.path.join(_DATA_DIR, "accio_error.txt"), "w", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass
        return text

    # ── 로그인 자동 입력 ─────────────────────────────────────────────
    def _auto_login(self, page) -> None:
        """로그인 화면이면 저장된 ID/PW 로 자동 로그인한다.

        저장 정보가 없으면 아무것도 하지 않는다(사람이 직접 로그인).
        """
        # 로그인 화면 판단: 보이는 비밀번호칸이 있는지
        try:
            pw = page.locator(LOGIN_PW_INPUT or "input[type=password]:visible").first
            if pw.count() == 0:
                return
        except Exception:
            return

        creds = getattr(self, "credentials", None)
        if not (creds and creds.get("username")):
            return  # 저장된 자격증명 없음 → 사람이 직접 로그인

        try:
            uid = page.locator(
                LOGIN_ID_INPUT
                or "input[type=text]:visible, input[type=email]:visible"
            ).first
            uid.fill(creds["username"])
            pw.fill(creds["password"])
        except Exception:
            return

        # 제출: 로그인 버튼 → 없으면 Enter
        try:
            clicked = False
            for sel in filter(None, (
                LOGIN_BUTTON,
                "button:has-text('로그인')",
                "input[type=submit]",
                "a:has-text('로그인')",
            )):
                try:
                    page.locator(sel).first.click(timeout=1500)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                pw.press("Enter")
            page.wait_for_load_state("domcontentloaded")
            self._wait_login_done(page)
        except Exception:
            pass

    def _wait_login_done(self, page, max_ms: int = 12000) -> None:
        """로그인 화면을 벗어날 때까지(비밀번호칸이 사라질 때까지) 기다린다."""
        sel = LOGIN_PW_INPUT or "input[type=password]:visible"
        for _ in range(max(1, max_ms // 500)):
            try:
                if page.locator(sel).count() == 0:
                    return
            except Exception:
                return
            page.wait_for_timeout(500)

    # ── 메인 흐름 ────────────────────────────────────────────────────
    def run(self, page, employee: Employee) -> StepResult:
        try:
            return self._run_inner(page, employee)
        except Exception as exc:  # noqa: BLE001
            if "has been closed" in str(exc).lower():
                raise  # 브라우저 닫힘은 컨트롤러가 친절 메시지로 처리
            diag = self._diagnose(page)
            return StepResult(ok=False, message=f"처리 중 오류: {exc} ── 진단: {diag}")

    def _run_inner(self, page, employee: Employee) -> StepResult:
        # 아직 셀렉터 미구현 → 자동화 시도하지 않고 수동 안내(안전)
        if not self._configured():
            return StepResult(
                ok=True,
                awaiting=True,
                message=(
                    f"'{self.name}' 자동화는 아직 준비 중이야. 열린 브라우저에서 "
                    f"{employee.name}({employee.resign_date}) 계정을 직접 삭제한 뒤 "
                    "[완료]를 눌러줘."
                ),
            )

        # 1) 로그인 자동 입력
        self._auto_login(page)

        # 2) 계정관리 화면으로 이동(주소를 알면 직접 이동)
        if USER_ADMIN_URL:
            try:
                if USER_ADMIN_URL.split("://")[-1] not in (page.url or ""):
                    page.goto(USER_ADMIN_URL, wait_until="domcontentloaded")
            except Exception:
                pass

        # 3) 이름/ID 로 검색
        search = page.locator(SEARCH_INPUT).first
        try:
            search.wait_for(state="visible", timeout=SEARCH_READY_MS)
        except Exception:
            return StepResult(
                ok=False,
                message=(
                    "계정 검색창을 찾지 못했어. 계정관리 화면에 로그인된 상태인지 "
                    "확인하고, 안 되면 직접 삭제 후 [완료]해줘. ── 진단: "
                    + self._diagnose(page)
                ),
            )
        search.fill(employee.name)
        if SEARCH_BUTTON:
            try:
                page.locator(SEARCH_BUTTON).first.click()
            except Exception:
                search.press("Enter")
        else:
            search.press("Enter")

        # 4) 결과 행 — 정확히 1건일 때만 진행(동명이인/오탐 방지)
        target = page.locator(RESULT_ROW, has_text=employee.name)
        try:
            target.first.wait_for(state="visible", timeout=15000)
        except Exception:
            return StepResult(
                ok=False,
                message=(
                    f"'{employee.name}' 검색 결과가 없어. 이름을 확인하거나 직접 처리해줘."
                ),
            )
        count = target.count()
        if count != 1:
            return StepResult(
                ok=False,
                message=(
                    f"'{employee.name}' 검색 결과가 {count}건이야. 안전을 위해 자동 진행을 "
                    "멈췄어. 직접 확인 후 삭제해줘."
                ),
            )

        # 5) 삭제 버튼 클릭 — 단, 확인창은 절대 승인하지 않는다.
        #    사이트가 브라우저 기본 confirm 을 띄우면 취소(dismiss)하고,
        #    사이트 자체 모달을 띄우면 그대로 열어둔 채 멈춘다.
        confirm_seen = {"native": False, "msg": ""}

        def _on_dialog(d):
            confirm_seen["native"] = True
            confirm_seen["msg"] = d.message or ""
            try:
                d.dismiss()  # 안전: 삭제 확정 confirm 은 취소
            except Exception:
                pass

        page.on("dialog", _on_dialog)

        delete_btn = target.locator(DELETE_BUTTON)
        if delete_btn.count() == 0:
            delete_btn = page.locator(DELETE_BUTTON)  # 상단 툴바형이면 행 밖에 있음
        try:
            target.first.click()  # 행 선택(툴바형 삭제 대비)
        except Exception:
            pass
        try:
            delete_btn.first.click(timeout=5000)
        except Exception:
            return StepResult(
                ok=False,
                message="삭제 버튼을 찾지 못했어. 화면에서 직접 삭제해줘. ── 진단: "
                + self._diagnose(page),
            )
        page.wait_for_timeout(800)

        # 6) 멈춤 안내
        if confirm_seen["native"]:
            note = confirm_seen["msg"].replace("\n", " ").strip()
            return StepResult(
                ok=True,
                awaiting=True,
                message=(
                    f"'{employee.name}' 삭제 버튼까지 눌렀고, 확인창"
                    + (f"('{note}')" if note else "")
                    + "은 안전을 위해 자동 취소했어. 삭제를 확정하려면 삭제를 다시 눌러 "
                    "[확인]을 직접 눌러줘."
                ),
            )
        return StepResult(
            ok=True,
            awaiting=True,
            message=(
                f"'{employee.name}' 삭제 확인창 직전까지 진행했어. "
                "최종 삭제 확정은 안전을 위해 직접 눌러줘."
            ),
        )
