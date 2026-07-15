"""더존 그룹웨어(BizBox Alpha) 퇴사 처리 시나리오.

대상: 성현 그룹웨어 (gw.bdo.kr), 관리자(ADMIN) 모드
화면 구조(실제 HTML 확인 완료):
  - 왼쪽 GNB '시스템설정' → LNB 트리(jstree)
      사원관리 > 사원정보관리  → anchor id = #902010000_anchor
  - 사원정보관리를 누르면 오른쪽 iframe(#_content)에
      /gw/cmm/systemx/empManageView.do?menu_no=902010000 가 로드된다.
  - ★ 검색창/직원목록/퇴사처리 버튼/퇴사일 입력은 모두 이 iframe 안에 있다.
    따라서 조작은 page 가 아니라 frame_locator("#_content") 를 통해야 한다.

처리 순서:
  1) 로그인은 사용자가 직접 (관리자 모드로 진입해 '시스템설정'이 떠 있는 상태)
  2) 왼쪽 트리에서 '사원정보관리' 클릭 → iframe 로드 대기
  3) iframe 안에서 이름 검색
  4) 검색 결과에서 대상 직원 선택
  5) '퇴사처리' 진입
  6) 퇴사일 입력
  7) (auto_submit=False) 저장 직전에서 멈춤 → 사람이 최종 확인/저장

⚠️ 3~6단계의 실제 셀렉터는 iframe 내부 HTML 을 받아야 채울 수 있다.
    (empManageView.do 화면에서 F12 로 iframe 내용을 복사해 주면 완성된다.)
"""

from __future__ import annotations

from .base import Employee, SiteScenario, StepResult

# 왼쪽 LNB 트리에서 '사원정보관리' 메뉴 앵커
EMP_MANAGE_ANCHOR = "#902010000_anchor"
# 오른쪽 콘텐츠 iframe
CONTENT_IFRAME = "#_content"


class GroupwareScenario(SiteScenario):
    id = "groupware"
    name = "더존 그룹웨어"
    kind = "browser"
    # 로그인 후 관리자 메인. 실제 접속 주소로 필요 시 교체.
    url = "https://gw.bdo.kr/gw/adminMain.do"
    login_required = True
    auto_submit = False  # 저장/제출은 사람이 최종 확인 후 직접

    def run(self, page, employee: Employee) -> StepResult:
        # ----- 2) 사원정보관리 메뉴 클릭 → iframe 로드 -----
        # 트리가 접혀 있을 수 있으나 이 메뉴는 leaf 라 앵커 클릭이면 iframe 이 갱신된다.
        try:
            page.locator(EMP_MANAGE_ANCHOR).click(timeout=5000)
        except Exception:
            # 이미 사원정보관리가 로드돼 있으면 무시하고 진행
            pass

        # 오른쪽 콘텐츠 iframe 안으로 들어간다. 이후 모든 조작은 frame 기준.
        frame = page.frame_locator(CONTENT_IFRAME)

        # ----- 3) 이름 검색 -----
        # TODO: iframe 내부 HTML 확인 후 검색 입력창/버튼 셀렉터로 교체
        # search = frame.get_by_placeholder("이름")   # 예시
        # search.fill(employee.name)
        # frame.get_by_role("button", name="검색").click()

        # ----- 4) 검색 결과에서 대상 선택 (동명이인 없음) -----
        # TODO: 결과 행/선택 셀렉터로 교체
        # frame.get_by_role("row", name=employee.name).click()

        # ----- 5) 퇴사처리 진입 -----
        # TODO: '퇴사처리' 버튼/탭 셀렉터로 교체
        # frame.get_by_role("button", name="퇴사처리").click()

        # ----- 6) 퇴사일 입력 -----
        # TODO: 퇴사일 입력칸 셀렉터로 교체.
        #       날짜 형식이 20260715 면 employee.resign_date_compact 사용.
        # frame.get_by_label("퇴사일").fill(employee.resign_date)

        # ----- 7) 저장 직전에서 멈춤 -----
        return StepResult(
            ok=True,
            awaiting=True,
            message=(
                "사원정보관리(iframe)까지 진입 구조는 반영됐습니다. "
                "iframe 내부 HTML(empManageView.do 화면)을 주면 "
                "이름 검색~퇴사일 입력까지 자동화됩니다. 지금은 브라우저에서 직접 처리해 주세요."
            ),
        )
