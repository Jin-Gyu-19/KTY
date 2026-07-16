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
import re

from .base import Employee, SiteScenario, StepResult

# 진단 스크린샷/로그 저장 위치 (프로젝트/data)
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)

# ─────────────────────────────────────────────────────────────────────────
# 실제 화면 셀렉터 (F12 로 확인해서 채운다). 비어 있으면 자동화 안 함(수동 안내).
# ─────────────────────────────────────────────────────────────────────────
# 1) 로그인 페이지 (Carbon/React SPA)
LOGIN_ID_INPUT = "#carbon-text-input"                    # 아이디칸(type=email)
LOGIN_PW_INPUT = "#password"                             # 비밀번호칸
LOGIN_BUTTON = "button.mothership-login-view-login-button"  # '로그인' 기본 버튼(눈알 토글과 구분)

# 2) 계정(사용자) 관리 화면 — AG Grid 표
USER_ADMIN_URL = "https://bdo.accio.kr/tools/manage-id"  # 전 직원 목록 화면
SEARCH_INPUT = "#search-input"   # '결과 내 검색'(타이핑 즉시 필터, 별도 버튼 없음)
SEARCH_BUTTON = ""               # 검색 버튼 없음(엔터도 불필요)

# 3) 검색 결과(AG Grid) → 삭제
RESULT_ROW = "div[role='row']"                 # 한 줄(row)
NAME_CELL = "[col-id='name'] span.mold-label"  # 줄 안의 '이름' 텍스트
ID_CELL = "[col-id='userId']"                  # 줄 안의 '계정(이메일)' — 안전 표시용
DELETE_BUTTON = "button.cck-icon-button--ghost"  # 줄 안의 빨간 휴지통(삭제)
# 검색 칩(태그)의 X(제거) 버튼. 채우면, 새 검색 전에 이전 칩을 눌러 지운다.
# (새로고침만으로 칩이 안 지워질 때 대비. 비어 있으면 이 단계는 건너뜀)
CHIP_REMOVE = ""

# 검색창이 뜰 때까지 기다리는 최대 시간(ms)
SEARCH_READY_MS = 8000
# 검색어 입력 후 그리드가 필터링될 때까지 대기(ms)
FILTER_SETTLE_MS = 1200


class AccioScenario(SiteScenario):
    id = "accio"
    name = "Accio (bdo.accio.kr)"
    kind = "browser"
    url = "https://bdo.accio.kr/"
    login_required = True
    # 계정 삭제는 되돌릴 수 없다. 확인창 직전에서 멈추고 사람이 확정한다.
    auto_submit = False

    # ── 아직 셀렉터가 안 채워졌는지 판단 ───────────────────────────────
    def _login_configured(self) -> bool:
        """로그인 자동입력에 필요한 셀렉터가 채워졌는지."""
        return bool(LOGIN_PW_INPUT and LOGIN_BUTTON)

    def _configured(self) -> bool:
        """검색~삭제 자동화에 꼭 필요한 셀렉터가 모두 채워졌는지."""
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
        # 1) 로그인 자동 입력 (검색/삭제가 아직이어도 로그인은 먼저 도와준다)
        if self._login_configured():
            self._auto_login(page)

        # 아직 검색/삭제 셀렉터 미구현 → 그 이후는 사람이 직접(안전)
        if not self._configured():
            logged = ""
            if self._login_configured():
                creds = getattr(self, "credentials", None)
                logged = (
                    "로그인은 저장된 정보로 자동입력했어(안 됐으면 직접 로그인). "
                    if (creds and creds.get("username"))
                    else ""
                )
            return StepResult(
                ok=True,
                awaiting=True,
                message=(
                    f"{logged}'{self.name}' 계정삭제 자동화는 아직 준비 중이야. "
                    f"열린 브라우저에서 {employee.name}({employee.resign_date}) 계정을 "
                    "직접 삭제한 뒤 [완료]를 눌러줘."
                ),
            )

        # 2) 계정관리 화면을 '매번 새로' 연다.
        #    검색창은 칩(태그)+AND/OR 필터라, 이전 사람 검색이 남긴 칩이 있으면
        #    다음 사람이 'AND' 로 묶여 검색되지 않는다. 새로 로드해 필터를 초기화한다.
        if USER_ADMIN_URL:
            try:
                page.goto(USER_ADMIN_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(600)
            except Exception:
                pass
        # 새로 로드해도 칩이 남아 있으면(필터 상태가 저장되는 경우) 직접 제거한다.
        self._clear_filter_chips(page)

        # 3) '결과 내 검색'에 이름을 넣어 목록을 좁힌다(타이핑 즉시 필터).
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
        # '결과 내 검색'은 이름을 입력한 뒤 '엔터'를 눌러야 검색이 실행된다.
        try:
            search.click()
            search.fill("")
            search.press_sequentially(employee.name, delay=60)
        except Exception:
            search.fill(employee.name)
        search.press("Enter")  # ← 엔터로 검색 실행(이게 핵심)
        page.wait_for_timeout(FILTER_SETTLE_MS)

        # 4) 이름이 '정확히' 일치하는 줄을 찾는다(부분일치 금지 → 김민 ↔ 김민수 오탐 방지).
        row = self._find_exact_row(page, employee.name)
        if row is None:
            # 아직 렌더 안 됐을 수 있으니 한 번 더 대기 후 재시도
            page.wait_for_timeout(1200)
            row = self._find_exact_row(page, employee.name)
        if row == "MULTI":
            return StepResult(
                ok=False,
                message=(
                    f"'{employee.name}'과 이름이 똑같은 계정이 2개 이상이야. "
                    "안전을 위해 자동 진행을 멈췄어. 화면에서 직접 확인 후 삭제해줘."
                ),
            )
        if row is None:
            vis = self._visible_names(page)
            return StepResult(
                ok=False,
                message=(
                    f"'{employee.name}' 계정을 목록에서 못 찾았어. 이름을 확인하거나 "
                    f"직접 처리해줘. ── 지금 화면에 보이는 이름({vis['count']}개): "
                    f"{vis['sample']} ── 진단: " + self._diagnose(page)
                ),
            )

        # 안전 표시용: 삭제 대상 계정(이메일)을 읽어 메시지에 함께 보여준다.
        acct = ""
        try:
            acct = (row.locator(ID_CELL).first.inner_text(timeout=2000) or "").strip()
        except Exception:
            acct = ""
        who = f"{employee.name}" + (f" / {acct}" if acct else "")

        # 5) 그 줄의 휴지통(삭제) 버튼을 확인한다(줄당 정확히 1개여야 함).
        delete_btn = row.locator(DELETE_BUTTON)
        if delete_btn.count() != 1:
            return StepResult(
                ok=False,
                message=(
                    f"'{who}' 줄에서 삭제 버튼을 정확히 못 찾았어"
                    f"(발견 {delete_btn.count()}개). 안전을 위해 멈췄어. 직접 삭제해줘."
                ),
            )

        # 테스트 모드: 대상만 확인하고 실제로 누르지는 않는다(확인창도 안 띄움).
        if getattr(self, "test_mode", False):
            return StepResult(
                ok=True,
                awaiting=False,
                message=(
                    f"[테스트] '{who}' 계정을 찾았고 삭제 버튼도 확인했어 → "
                    "실제로는 누르지 않음(테스트라 삭제 안 함)."
                ),
            )

        # 휴지통 클릭 — 단, 확인창은 절대 승인하지 않는다.
        #   브라우저 기본 confirm 이면 취소(dismiss)하고,
        #   사이트 자체 모달이면 그대로 열어둔 채 멈춘다(사람이 최종 확인).
        confirm_seen = {"native": False, "msg": ""}

        def _on_dialog(d):
            confirm_seen["native"] = True
            confirm_seen["msg"] = d.message or ""
            try:
                d.dismiss()  # 안전: 삭제 확정 confirm 은 취소
            except Exception:
                pass

        page.on("dialog", _on_dialog)

        try:
            delete_btn.first.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass
        try:
            delete_btn.first.click(timeout=5000)
        except Exception:
            return StepResult(
                ok=False,
                message="삭제 버튼 클릭에 실패했어. 화면에서 직접 삭제해줘. ── 진단: "
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
                    f"'{who}' 삭제 버튼을 눌렀고, 확인창"
                    + (f"('{note}')" if note else "")
                    + "은 안전을 위해 자동 취소했어. 삭제를 확정하려면 그 줄 휴지통을 다시 눌러 "
                    "[확인]을 직접 눌러줘."
                ),
            )
        return StepResult(
            ok=True,
            awaiting=True,
            message=(
                f"'{who}' 삭제 확인창 직전까지 진행했어. 대상이 맞는지 확인하고, "
                "최종 삭제 확정은 안전을 위해 직접 눌러줘."
            ),
        )

    def _clear_filter_chips(self, page) -> None:
        """이전 검색으로 남은 필터 칩(태그)을 모두 제거한다.

        CHIP_REMOVE 셀렉터가 채워져 있을 때만 동작한다(비어 있으면 안전하게 건너뜀).
        """
        if not CHIP_REMOVE:
            return
        try:
            chips = page.locator(CHIP_REMOVE)
            for _ in range(20):  # 지울 때마다 개수가 줄어드니 첫 칩을 반복 클릭
                if chips.count() == 0:
                    break
                try:
                    chips.first.click(timeout=1500)
                    page.wait_for_timeout(200)
                except Exception:
                    break
        except Exception:
            pass

    def _visible_names(self, page) -> dict:
        """현재 그리드에 렌더된 이름 셀 텍스트를 모아 개수/샘플을 돌려준다.

        필터가 먹었는지(목록이 좁혀졌는지) 진단하는 용도.
        """
        names = []
        try:
            cells = page.locator(NAME_CELL)
            n = min(cells.count(), 30)
            for i in range(n):
                try:
                    t = (cells.nth(i).inner_text(timeout=500) or "").strip()
                except Exception:
                    continue
                if t:
                    names.append(t)
        except Exception:
            pass
        sample = ", ".join(names[:12]) + ("..." if len(names) > 12 else "")
        return {"count": len(names), "sample": sample or "(없음)"}

    def _find_exact_row(self, page, name: str):
        """이름이 '정확히' 일치하는 AG Grid 줄(Locator)을 반환한다.

        - 정확히 1개면 그 줄의 Locator, 0개면 None, 2개 이상이면 "MULTI".
        - 위치(index)가 아니라 '이름 셀이 정확히 일치하는 내용' 기준으로 잡는다.
          (가상 스크롤로 DOM 이 재사용돼도 안전하게 재조회되도록)
        - 부분일치(김민 ↔ 김민수)는 정규식 ^이름$ 로 막는다.
        """
        exact = re.compile(r"^\s*" + re.escape(name.strip()) + r"\s*$")
        rows = page.locator(RESULT_ROW).filter(
            has=page.locator(NAME_CELL, has_text=exact)
        )
        try:
            cnt = rows.count()
        except Exception:
            return None
        if cnt == 0:
            return None
        if cnt > 1:
            return "MULTI"
        return rows.first
