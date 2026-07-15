"""더존 그룹웨어(BizBox Alpha) 퇴사 처리 시나리오.

대상: 성현 그룹웨어 (gw.bdo.kr), 관리자(ADMIN) 모드
화면 구조(실제 HTML 확인 완료):
  - 왼쪽 GNB '시스템설정' → LNB 트리 '사원관리 > 사원정보관리'
      anchor id = #902010000_anchor
  - 사원정보관리는 오른쪽 iframe(#_content)에 로드된다
      (/gw/cmm/systemx/empManageView.do)
  - iframe 안은 Kendo UI 화면:
      · 검색창  : #searchKeyword  (사용자명(ID)/Mail ID)
      · 검색버튼: #searchButton   (onclick=gridRead('search'))
      · 결과그리드: #grid  (행 tr[role=row], 사원명은 "이름(사번)" 형식)
      · 퇴사처리: #retireEmp → empResignProc()
            선택된 행이 있어야 동작하며, 팝업창 empResignPop 을 열고
            /gw/cmm/systemx/empResignPop.do 로 사원정보를 넘긴다.
      · 기본 재직여부 필터 = '재직'(999) 이므로 퇴사 대상(재직자)이 검색된다.

★ 퇴사처리 팝업(empResignPop.do)의 실제 동작(HTML 확인 완료):
  - 8단계 마법사: 퇴사일 > 메일정보 > 부서정보 > 필수결재라인 >
                  결재문서처리 > 문서함 권한 > 게시함 권한 > 메신저
  - 퇴사일(#out_date): 열자마자 disabled 되고 '오늘'로 자동 세팅된다.
      미래 날짜는 "예약 퇴사처리는 불가합니다" 로 막힌다.
      → 즉 퇴사일은 사용자가 지정하는 값이 아니라 '처리하는 당일'로 고정.
  - 중간 단계에서 미결 결재/문서함/게시판의 '대체자(후임자)'를 사람이 지정해야 한다.
      이는 사람마다 다르고 판단이 필요하므로 자동화 대상이 아니다.
  - 최종 '완료'(#finishBtn → ok()) 시 confirm 후 empResignProcFinish.do 로 확정.

따라서 자동화 범위(안전):
  1) 로그인은 사용자가 직접
  2) 관리자 모드 + 사원정보관리 자동 이동
  3) 이름으로 검색
  4) 결과 행 선택 (동명이인 없음. 결과가 정확히 1건이 아니면 안전상 중단)
  5) 퇴사처리 클릭 → 팝업창 열림
  6) 팝업의 '이름'이 입력한 대상과 일치하는지 대조(안전 확인)
  7) 마법사 [다음]을 갈 수 있는 데까지 자동 진행.
     대체자 지정이 필요한 단계에서 막히거나 마지막 단계면 멈춘다.
     [완료](실제 확정)는 절대 자동으로 누르지 않는다 → 사람이 마무리.
"""

from __future__ import annotations

import os

from .base import Employee, SiteScenario, StepResult

# 진단 스크린샷 저장 위치 (프로젝트/data)
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)

# 왼쪽 LNB 트리에서 '사원정보관리' 메뉴 앵커
EMP_MANAGE_ANCHOR = "#902010000_anchor"
# 오른쪽 콘텐츠 iframe
CONTENT_IFRAME = "#_content"
# iframe 내부 셀렉터
SEARCH_INPUT = "#searchKeyword"
SEARCH_BUTTON = "#searchButton"
GRID_ROW = "#grid .k-grid-content tr[role='row']"
SELECTED_ROW = "#grid .k-grid-content tr.k-state-selected"
RETIRE_BUTTON = "#retireEmp"
# 관리자 메인(프레임 레이아웃 + #_content iframe 포함)
ADMIN_MAIN_URL = "http://gw.bdo.kr/gw/adminMain.do"
# 사원정보관리 화면(iframe 에 직접 로드할 URL)
EMP_MANAGE_VIEW_URL = "http://gw.bdo.kr/gw/cmm/systemx/empManageView.do?menu_no=902010000"
# 시스템설정 GNB 링크(폴백용)
SYSTEM_GNB_LINK = "#topMenu900000000 a"
# 팝업 상단 대상정보 표의 '이름' 값 (안전 대조용)
POPUP_NAME_XPATH = (
    "xpath=//div[contains(@class,'com_ta')]"
    "//th[normalize-space()='이름']/following-sibling::td[1]"
)
# 팝업 마법사 버튼
POPUP_NEXT_BUTTON = "#nextBtn"
POPUP_FINISH_BUTTON = "#finishBtn"
# 현재 보이는 마법사 단계 id 를 알아내는 스크립트
_CURRENT_STEP_JS = (
    "() => { const e=[...document.querySelectorAll(\"div[id^='step_div']\")]"
    ".find(x => x.offsetParent !== null); return e ? e.id : null; }"
)


class GroupwareScenario(SiteScenario):
    id = "groupware"
    name = "더존 그룹웨어"
    kind = "browser"
    # 이 그룹웨어는 http 로 서비스된다(HTML 내 http://gw.bdo.kr 확인). https 는 연결 거부됨.
    url = "http://gw.bdo.kr/gw/adminMain.do"
    login_required = True
    # 팝업 마법사(대체자 지정 등)는 사람이 판단해야 하므로 자동 완료하지 않는다.
    auto_submit = False

    def _find_emp_frame(self, page):
        """모든 프레임을 뒤져 사원 검색창이 있는 프레임(Frame)을 반환한다."""
        for fr in page.frames:
            try:
                if fr.locator(SEARCH_INPUT).count() > 0:
                    return fr
            except Exception:
                continue
        return None

    def _wait_emp_frame(self, page, timeout_ms: int):
        """검색창이 있는 프레임이 나타날 때까지(최대 timeout) 기다린다."""
        for _ in range(max(1, timeout_ms // 500)):
            fr = self._find_emp_frame(page)
            if fr is not None:
                return fr
            page.wait_for_timeout(500)
        return None

    def _search_ready(self, page, timeout: int) -> bool:
        """사원 검색창이 어느 프레임에든 떴는지 확인한다."""
        return self._wait_emp_frame(page, timeout) is not None

    def _diagnose(self, page) -> str:
        """실패 시 현재 화면 상태를 문자열로 요약하고 스크린샷을 저장한다."""
        parts = []
        try:
            parts.append(f"주소={page.url}")
        except Exception:
            pass
        try:
            parts.append(f"제목='{page.title()}'")
        except Exception:
            pass
        try:
            frs = []
            for fr in page.frames:
                frs.append(f"{fr.name or '(무명)'}:{(fr.url or '')[:70]}")
            parts.append("프레임=[" + " | ".join(frs) + "]")
        except Exception:
            pass
        try:
            if page.locator("input[type=password]").count() > 0:
                parts.append("※비밀번호칸 보임→자동화 창이 로그인 안 됐을 수 있음")
        except Exception:
            pass
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            shot = os.path.join(_DATA_DIR, "last_error.png")
            page.screenshot(path=shot, full_page=True)
            parts.append(f"스크린샷={shot}")
        except Exception:
            pass
        return " / ".join(parts)

    def _ensure_admin_emp(self, page) -> None:
        """관리자 모드의 '사원정보관리' 화면(iframe)을 확실히 로드한다.

        더존 LNB 는 jstree 라 메뉴 클릭이 타이밍에 잘 흔들린다. 그래서
        iframe(#_content)을 Playwright 정식 방법(Frame.goto)으로 사원정보관리
        화면에 직접 이동시킨다. 실패하면 메뉴 클릭으로 폴백.
        """
        # 0) 이미 사원정보관리가 떠 있으면(사용자가 수동으로 열었거나 기본 로드) 그대로 사용
        if self._search_ready(page, 2500):
            return

        # 1) 프레임 레이아웃(관리자 메인) 확보
        try:
            if "adminmain.do" not in (page.url or "").lower():
                page.goto(ADMIN_MAIN_URL, wait_until="domcontentloaded")
        except Exception:
            pass

        # 2) iframe 을 사원정보관리 화면으로 직접 이동 (Frame.goto)
        try:
            page.wait_for_selector(CONTENT_IFRAME, timeout=8000)
            fr = page.frame(name="_content")
            if fr is not None:
                fr.goto(EMP_MANAGE_VIEW_URL, wait_until="domcontentloaded")
        except Exception:
            pass
        if self._search_ready(page, 6000):
            return

        # 3) 폴백: 시스템설정 GNB → 사원정보관리 트리 클릭
        try:
            page.locator(SYSTEM_GNB_LINK).first.click(timeout=3000)
            page.wait_for_timeout(1500)
        except Exception:
            pass
        try:
            page.locator(EMP_MANAGE_ANCHOR).first.click(timeout=6000)
        except Exception:
            pass

    def _auto_next(self, popup) -> str:
        """팝업 마법사의 [다음]을 갈 수 있는 데까지 누른다.

        [완료]는 절대 누르지 않는다(실제 퇴사 확정이라 사람이 확인해야 함).
        대체자 지정 등으로 [다음]이 막히거나 마지막 단계에 도달하면 멈추고,
        멈춘 이유 문구를 돌려준다.
        """
        # 마법사 진행 중 뜨는 안내창은 닫되(=막힘 신호), 확인창은 절대 승인하지 않는다.
        state = {"blocked": False, "msg": ""}

        def _on_dialog(d):
            state["blocked"] = True
            state["msg"] = d.message or ""
            try:
                if d.type == "confirm":
                    d.dismiss()  # 안전: 확정 성격 확인창은 취소
                else:
                    d.accept()
            except Exception:
                pass

        popup.on("dialog", _on_dialog)

        def _cur_step():
            try:
                return popup.evaluate(_CURRENT_STEP_JS)
            except Exception:
                return None

        advanced = 0
        for _ in range(15):
            # 마지막 단계면 완료 버튼이 보인다 → 누르지 않고 멈춤
            try:
                if popup.locator(POPUP_FINISH_BUTTON).is_visible():
                    return (
                        f"마지막 단계까지 자동 진행({advanced}단계)했습니다. "
                        "확정하려면 [완료]를 직접 눌러 주세요."
                    )
            except Exception:
                pass

            before = _cur_step()
            state["blocked"] = False
            try:
                popup.locator(POPUP_NEXT_BUTTON).click(timeout=3000)
            except Exception:
                return f"{advanced}단계 진행 후 [다음] 버튼을 찾지 못해 멈췄습니다. 화면을 확인해 주세요."
            popup.wait_for_timeout(700)  # 단계 전환/데이터 로딩 대기

            after = _cur_step()
            if state["blocked"] or (after is not None and after == before):
                note = state["msg"].replace("\n", " ").strip()
                prefix = f"'{note}' 안내로 " if note else ""
                return (
                    f"{advanced}단계까지 자동 진행했고, {prefix}멈췄습니다. "
                    "이 단계는 대체자 지정 등 수동 처리가 필요합니다. "
                    "처리 후 [다음]~[완료]로 마무리해 주세요."
                )
            advanced += 1

        return f"{advanced}단계 자동 진행했습니다. 나머지는 직접 확인해 주세요."

    def run(self, page, employee: Employee) -> StepResult:
        # ----- 2) 관리자 모드 + 사원정보관리 자동 이동 -----
        self._ensure_admin_emp(page)

        # ----- 3) 검색창이 있는 프레임 찾기 (iframe 구조가 달라도 대응) -----
        frame = self._wait_emp_frame(page, 15000)
        if frame is None:
            return StepResult(
                ok=False,
                message=(
                    "사원정보관리 화면(검색창)을 찾지 못했습니다. "
                    "관리자로 로그인된 상태인지 확인하고, 안 되면 브라우저에서 "
                    "'시스템설정 > 사원관리 > 사원정보관리'를 직접 연 뒤 다시 [자동 처리] 해주세요. "
                    "── 진단: " + self._diagnose(page)
                ),
            )

        # ----- 이름 검색 -----
        search = frame.locator(SEARCH_INPUT)
        try:
            search.wait_for(state="visible", timeout=8000)
        except Exception:
            pass
        search.fill(employee.name)
        frame.locator(SEARCH_BUTTON).click()

        # ----- 4) 결과 행 선택 (동명이인 없음, 정확히 1건 검증) -----
        # 사원명 셀이 "이름(사번)" 형식이라 '이름(' 으로 좁히면 오탐이 거의 없다.
        target = frame.locator(GRID_ROW, has_text=f"{employee.name}(")
        try:
            target.first.wait_for(state="visible", timeout=15000)
        except Exception:
            return StepResult(
                ok=False,
                message=(
                    f"'{employee.name}' 검색 결과가 없습니다. "
                    "이름을 확인하거나(재직 상태인지 포함) 직접 처리해 주세요."
                ),
            )

        count = target.count()
        if count > 1:
            return StepResult(
                ok=False,
                message=(
                    f"'{employee.name}' 검색 결과가 {count}건입니다. "
                    "안전을 위해 자동 진행을 멈췄습니다. 직접 확인 후 처리해 주세요."
                ),
            )

        target.first.click()
        # 선택이 반영됐는지(퇴사처리는 선택 행이 없으면 동작 안 함) 확인
        try:
            frame.locator(SELECTED_ROW).first.wait_for(state="visible", timeout=5000)
        except Exception:
            return StepResult(
                ok=False,
                message="대상 직원 행 선택에 실패했습니다. 화면에서 직접 선택 후 퇴사처리해 주세요.",
            )

        # ----- 5) 퇴사처리 클릭 → 팝업창 열림 -----
        try:
            with page.expect_popup(timeout=15000) as pop_info:
                frame.locator(RETIRE_BUTTON).click()
            popup = pop_info.value
        except Exception:
            return StepResult(
                ok=False,
                message=(
                    "퇴사처리 팝업이 열리지 않았습니다. "
                    "대상이 선택된 상태인지 확인 후 직접 퇴사처리해 주세요."
                ),
            )

        popup.wait_for_load_state("domcontentloaded")
        popup.bring_to_front()
        self._resign_popup = popup

        # ----- 6) 팝업 대상 이름 대조 (엉뚱한 사람 방지) -----
        name_in_popup = ""
        try:
            name_in_popup = popup.locator(POPUP_NAME_XPATH).first.inner_text(
                timeout=5000
            ).strip()
        except Exception:
            name_in_popup = ""

        if name_in_popup and name_in_popup != employee.name:
            return StepResult(
                ok=False,
                message=(
                    f"⚠️ 팝업의 대상('{name_in_popup}')이 입력한 이름('{employee.name}')과 "
                    "다릅니다. 자동 진행을 멈췄습니다. 팝업을 닫고 다시 확인해 주세요."
                ),
            )

        # ----- 7) 마법사 [다음] 자동 진행 (완료는 사람이) -----
        who = f"{name_in_popup or employee.name}"
        tail = self._auto_next(popup)
        return StepResult(
            ok=True,
            awaiting=True,
            message=(
                f"'{who}' 퇴사처리 팝업 진행: {tail} "
                "(퇴사일은 오늘로 자동 지정됩니다. 최종 [완료]는 안전을 위해 직접 눌러 주세요.)"
            ),
        )
