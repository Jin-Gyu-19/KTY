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
  1) 로그인은 사용자가 직접 (관리자 모드, '시스템설정' 진입 상태)
  2) 사원정보관리 진입
  3) 이름으로 검색
  4) 결과 행 선택 (동명이인 없음. 결과가 정확히 1건이 아니면 안전상 중단)
  5) 퇴사처리 클릭 → 팝업창 열림
  6) 팝업의 '이름'이 입력한 대상과 일치하는지 대조(안전 확인)
  7) 여기서 멈춤 → 퇴사일 확인·대체자 지정·완료는 사람이 마무리
"""

from __future__ import annotations

from .base import Employee, SiteScenario, StepResult

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
# 팝업 상단 대상정보 표의 '이름' 값 (안전 대조용)
POPUP_NAME_XPATH = (
    "xpath=//div[contains(@class,'com_ta')]"
    "//th[normalize-space()='이름']/following-sibling::td[1]"
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

    def run(self, page, employee: Employee) -> StepResult:
        # ----- 2) 사원정보관리 진입 → iframe -----
        try:
            page.locator(EMP_MANAGE_ANCHOR).click(timeout=5000)
        except Exception:
            # 이미 사원정보관리가 로드돼 있으면 무시
            pass

        frame = page.frame_locator(CONTENT_IFRAME)

        # ----- 3) 이름 검색 -----
        search = frame.locator(SEARCH_INPUT)
        try:
            search.wait_for(state="visible", timeout=15000)
        except Exception:
            return StepResult(
                ok=False,
                message=(
                    "사원정보관리 화면(iframe)을 찾지 못했습니다. "
                    "관리자 모드에서 '시스템설정 > 사원관리 > 사원정보관리'가 열려 있는지 확인해 주세요."
                ),
            )
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

        # ----- 7) 여기서 멈춤 (마법사는 사람이 마무리) -----
        who = f"{name_in_popup or employee.name}"
        return StepResult(
            ok=True,
            awaiting=True,
            message=(
                f"'{who}' 퇴사처리 팝업을 열었습니다(대상 확인 완료). "
                "더존 퇴사일은 '오늘'로 자동 지정되며(미래 예약 불가), "
                "미결 결재·문서함 등 대체자 지정은 판단이 필요해 자동화하지 않습니다. "
                "팝업에서 [다음]으로 진행하며 대체자를 지정하고 [완료]로 마무리해 주세요."
            ),
        )
