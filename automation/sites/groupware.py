"""더존 그룹웨어 퇴사 처리 시나리오 (템플릿).

처리 순서(사용자가 손으로 하는 순서 그대로):
  1) 관리자 메뉴 → 시스템관리 → 사용자 관리 로 이동
  2) 이름으로 검색
  3) 검색 결과에서 해당 직원 선택
  4) '퇴사처리' 진입
  5) 퇴사일 입력
  6) 다음 단계 진행 (저장/제출 직전에서 멈춤 → 사람이 최종 확인)

⚠️ 아직 각 단계의 실제 셀렉터가 비어 있는 뼈대다.
    F12 → Elements 로 뜬 실제 HTML 을 받으면 TODO 부분만 채우면 동작한다.

더존 그룹웨어 참고:
  - 관리자 화면이 iframe/frameset 으로 감싸인 경우가 많다. 그때는
    page.frame_locator("iframe#...") 로 프레임 안으로 들어가서 조작해야 한다.
    아래 _root() 헬퍼에서 프레임 진입 여부를 한 곳에서 관리하도록 해뒀다.
"""

from __future__ import annotations

from .base import Employee, SiteScenario, StepResult


class GroupwareScenario(SiteScenario):
    id = "groupware"
    name = "더존 그룹웨어"
    kind = "browser"
    # TODO: 실제 그룹웨어 관리자 접속 주소로 교체
    url = "https://groupware.example.com/"
    login_required = True
    auto_submit = False  # 저장/제출은 사람이 최종 확인 후 직접

    def _root(self, page):
        """조작 대상 루트를 돌려준다.

        관리 화면이 iframe 안이면 아래를 프레임 로케이터로 바꾼다:
            return page.frame_locator("iframe#mainFrame")
        프레임이 아니면 page 를 그대로 쓴다.
        """
        # TODO: 더존 관리 화면이 iframe 이면 frame_locator 로 교체
        return page

    def run(self, page, employee: Employee) -> StepResult:
        root = self._root(page)

        # ----- 1) 시스템관리 → 사용자 관리 -----
        # TODO: 실제 메뉴 셀렉터로 교체
        # root.get_by_role("link", name="시스템관리").click()
        # root.get_by_role("link", name="사용자 관리").click()
        # page.wait_for_load_state("networkidle")

        # ----- 2) 이름 검색 -----
        # TODO: 검색 입력창/검색 버튼 셀렉터로 교체
        # search = root.get_by_placeholder("이름")
        # search.fill(employee.name)
        # root.get_by_role("button", name="검색").click()
        # page.wait_for_load_state("networkidle")

        # ----- 3) 검색 결과에서 대상 선택 -----
        # 동명이인이 없으므로 이름이 정확히 일치하는 행을 연다.
        # TODO: 결과 행/선택 셀렉터로 교체
        # root.get_by_role("row", name=employee.name).click()

        # ----- 4) 퇴사처리 진입 -----
        # TODO: '퇴사처리' 버튼/메뉴 셀렉터로 교체
        # root.get_by_role("button", name="퇴사처리").click()

        # ----- 5) 퇴사일 입력 -----
        # TODO: 퇴사일 입력칸 셀렉터로 교체. 형식이 20260715 면
        #       employee.resign_date_compact 사용.
        # root.get_by_label("퇴사일").fill(employee.resign_date)

        # ----- 6) 다음 단계 진행 (저장 직전에서 멈춤) -----
        # auto_submit=False 이므로 최종 저장 버튼은 누르지 않는다.
        return StepResult(
            ok=True,
            awaiting=True,
            message=(
                "더존 그룹웨어 셀렉터가 아직 비어 있습니다. "
                "사용자 관리 화면의 HTML(F12→Elements)을 주면 "
                "검색~퇴사일 입력까지 자동화됩니다. 지금은 브라우저에서 직접 처리해 주세요."
            ),
        )
