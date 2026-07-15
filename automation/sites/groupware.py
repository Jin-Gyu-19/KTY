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

처리 순서:
  1) 로그인은 사용자가 직접 (관리자 모드, '시스템설정' 진입 상태)
  2) 사원정보관리 진입 → iframe 로드
  3) 이름으로 검색
  4) 결과 행 선택 (동명이인 없음. 결과가 정확히 1건이 아니면 안전상 중단)
  5) 퇴사처리 클릭 → 팝업창 열림
  6) 팝업에서 퇴사일 입력 → (auto_submit=False) 저장 직전 멈춤

⚠️ 6단계(퇴사일 입력)는 팝업(empResignPop.do)의 HTML 을 받아야 채울 수 있다.
    지금은 팝업을 여는 데까지 자동화하고, 퇴사일 입력·저장은 사람이 마무리한다.
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


class GroupwareScenario(SiteScenario):
    id = "groupware"
    name = "더존 그룹웨어"
    kind = "browser"
    url = "https://gw.bdo.kr/gw/adminMain.do"
    login_required = True
    auto_submit = False  # 팝업의 저장은 사람이 최종 확인 후 직접

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
        # 이후 팝업에서 퇴사일 입력을 자동화하려면 이 참조를 사용한다.
        self._resign_popup = popup

        # ----- 6) 팝업에서 퇴사일 입력 (TODO: empResignPop.do HTML 필요) -----
        # popup.get_by_label("퇴사일").fill(employee.resign_date)  # 예시

        return StepResult(
            ok=True,
            awaiting=True,
            message=(
                f"'{employee.name}' 선택 후 퇴사처리 팝업을 열었습니다. "
                "팝업에서 퇴사일 입력·저장을 완료해 주세요. "
                "(팝업 HTML을 주면 퇴사일 입력까지 자동화됩니다.)"
            ),
        )
