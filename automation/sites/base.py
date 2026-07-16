"""사이트별 퇴사 처리 시나리오의 공통 뼈대.

새 사이트를 추가할 때는 이 모듈의 SiteScenario 를 상속해서
run() 안에 실제 클릭/입력 순서를 채워 넣으면 된다.
그룹웨어, 업무 사이트, VPN 관리처럼 '브라우저를 직접 조작'하는 사이트는
kind = "browser" 로 두고 run(page, employee) 를 구현한다.
M365 처럼 API로 처리하는 사이트는 kind = "api" 로 두고 run(employee) 를 구현한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Employee:
    """퇴사 처리 대상. 동명이인은 없다는 전제로 이름을 키로 사용한다."""

    name: str
    resign_date: str  # YYYY-MM-DD

    @property
    def resign_date_compact(self) -> str:
        """20260715 형태가 필요한 사이트용."""
        return self.resign_date.replace("-", "")


@dataclass
class StepResult:
    """run() 이 돌려주는 실행 결과.

    ok        : 자동화가 의도대로 끝났는지
    awaiting  : 사람이 마지막으로 확인/제출해야 하는지 (제출 직전에서 멈춘 경우)
    message   : UI 에 그대로 보여줄 설명
    """

    ok: bool = True
    awaiting: bool = False
    message: str = ""
    details: dict = field(default_factory=dict)


class SiteScenario:
    """모든 사이트 시나리오의 부모 클래스."""

    # 사이트 식별자 (영문/숫자, 고유). 예: "groupware"
    id: str = ""
    # UI 에 보여줄 이름. 예: "그룹웨어"
    name: str = ""
    # "browser" 또는 "api"
    kind: str = "browser"
    # 브라우저 사이트일 때 처음 열어줄 주소
    url: str = ""
    # 사용자가 직접 로그인해야 하는 사이트인지 (browser 전용)
    login_required: bool = True
    # 자동으로 최종 제출까지 할지. 기본값 False = 제출 직전에서 멈춘다.
    auto_submit: bool = False
    # 테스트 모드: 실제 확정 없이 흐름만 확인(팝업 열고 바로 닫기 등). 실행 직전에 설정된다.
    test_mode: bool = False
    # 자동 로그인용 자격증명 {"username":..,"password":..}. 실행 직전에 설정된다.
    credentials: dict | None = None

    # ----- 브라우저 시나리오용 -----
    def run(self, page, employee: Employee) -> StepResult:  # noqa: D401
        """page(Playwright Page)를 조작해서 퇴사 처리를 진행한다.

        하위 클래스에서 반드시 구현. auto_submit=False 이면
        마지막에 StepResult(awaiting=True) 로 반환해 사람이 제출하도록 남긴다.
        """
        raise NotImplementedError

    # ----- API 시나리오용 -----
    def run_api(self, employee: Employee) -> StepResult:
        """API 로 퇴사 처리를 진행한다. kind == 'api' 인 시나리오만 구현."""
        raise NotImplementedError
