"""사이트 시나리오 등록소.

새 사이트를 추가하면 여기 SCENARIOS 리스트에 등록만 하면
UI 체크리스트에 자동으로 나타난다. 순서 = 처리 순서.
"""

from __future__ import annotations

from .sites.accio import AccioScenario
from .sites.base import SiteScenario
from .sites.generic import ManualBrowserScenario
from .sites.groupware import GroupwareScenario

# 처리 순서대로 나열. (M365 는 직접 처리하므로 제외)
SCENARIOS: list[SiteScenario] = [
    GroupwareScenario(),
    AccioScenario(),
    ManualBrowserScenario(
        id="vpn",
        name="VPN (61.73.184.193)",
        url="https://61.73.184.193/login?redir=%2F",
        note="자체 서명 인증서 경고가 뜨면 [고급 → 계속 진행]으로 들어가면 돼.",
    ),
]

_BY_ID = {s.id: s for s in SCENARIOS}


def all_scenarios() -> list[SiteScenario]:
    return list(SCENARIOS)


def get(site_id: str) -> SiteScenario | None:
    return _BY_ID.get(site_id)
