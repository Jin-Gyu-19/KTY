"""사이트 시나리오 등록소.

새 사이트를 추가하면 여기 SCENARIOS 리스트에 등록만 하면
UI 체크리스트에 자동으로 나타난다. 순서 = 처리 순서.
"""

from __future__ import annotations

from .sites.base import SiteScenario
from .sites.groupware import GroupwareScenario
from .sites.m365 import M365Scenario

# 처리 순서대로 나열. 앞으로 업무사이트/VPN 등을 여기에 추가한다.
SCENARIOS: list[SiteScenario] = [
    GroupwareScenario(),
    M365Scenario(),
    # TODO: 업무사이트 A, 업무사이트 B, VPN 관리(FortiGate) ...
]

_BY_ID = {s.id: s for s in SCENARIOS}


def all_scenarios() -> list[SiteScenario]:
    return list(SCENARIOS)


def get(site_id: str) -> SiteScenario | None:
    return _BY_ID.get(site_id)
