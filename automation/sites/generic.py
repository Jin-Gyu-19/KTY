"""자동화 로직이 아직 없는 브라우저 사이트용 범용 시나리오.

[열기]로 로그인 페이지를 띄워 주고, 실제 퇴사/계정 정지 처리는 사람이 직접 한 뒤
[완료]로 체크한다. 순차 처리/체크리스트에는 정상적으로 포함된다.
나중에 사이트별 실제 클릭 순서를 파악하면 전용 시나리오로 교체하면 된다.
"""

from __future__ import annotations

from .base import Employee, SiteScenario, StepResult


class ManualBrowserScenario(SiteScenario):
    """[열기] → 사람이 직접 처리 → [완료] 흐름의 브라우저 사이트."""

    kind = "browser"

    def __init__(self, id: str, name: str, url: str, note: str = "") -> None:
        self.id = id
        self.name = name
        self.url = url
        self._note = note

    def run(self, page, employee: Employee) -> StepResult:
        tail = f" {self._note}" if self._note else ""
        return StepResult(
            ok=True,
            awaiting=True,
            message=(
                f"'{self.name}'은 아직 자동화 전이야. 열린 브라우저에서 "
                f"{employee.name}({employee.resign_date}) 계정을 직접 처리한 뒤 "
                f"[완료]를 눌러줘.{tail}"
            ),
        )
