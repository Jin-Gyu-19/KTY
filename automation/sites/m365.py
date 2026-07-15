"""M365(Entra) 퇴사 처리 시나리오 — Graph API 방식.

브라우저를 열지 않고 API 로 처리한다:
  1) 이름으로 사용자 조회
  2) 계정 차단(accountEnabled=False)
  3) 로그인 세션 강제 만료
  4) 라이선스 회수

환경변수(M365_TENANT_ID / M365_CLIENT_ID / M365_CLIENT_SECRET)가
설정돼 있지 않으면 안내 메시지만 돌려준다.
"""

from __future__ import annotations

from ..integrations.graph import GraphClient
from .base import Employee, SiteScenario, StepResult


class M365Scenario(SiteScenario):
    id = "m365"
    name = "M365 (Entra)"
    kind = "api"
    login_required = False

    def run_api(self, employee: Employee) -> StepResult:
        client = GraphClient()
        if not client.configured():
            return StepResult(
                ok=False,
                message=(
                    "M365 환경변수(M365_TENANT_ID/CLIENT_ID/CLIENT_SECRET)가 "
                    "설정되지 않았습니다. .env 를 채우면 API로 자동 처리됩니다."
                ),
            )

        try:
            user = client.find_user(employee.name)
            if user is None:
                return StepResult(
                    ok=False,
                    message=f"'{employee.name}' 사용자를 찾지 못했습니다.",
                )

            uid = user["id"]
            upn = user.get("userPrincipalName", "")
            client.disable_account(uid)
            client.revoke_sessions(uid)
            skus = client.list_licenses(uid)
            client.remove_licenses(uid, skus)

            return StepResult(
                ok=True,
                awaiting=False,
                message=(
                    f"{upn} 계정 차단 · 세션 만료 · 라이선스 {len(skus)}건 회수 완료"
                ),
                details={"upn": upn, "removed_licenses": skus},
            )
        except Exception as exc:  # noqa: BLE001 - UI 에 그대로 표시
            return StepResult(ok=False, message=f"처리 중 오류: {exc}")
