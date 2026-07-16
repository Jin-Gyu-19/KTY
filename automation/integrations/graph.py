"""Microsoft Graph API 헬퍼 (M365 퇴사 처리용).

브라우저 자동화 대신 Graph API 로 처리한다. 관리센터 UI 는 MS가
수시로 바꿔서 셀렉터가 잘 깨지지만, API 는 안정적이다.

사전 준비 (한 번만):
  1) Entra 관리센터 → 앱 등록(App registration) 생성
  2) API 권한: User.ReadWrite.All (관리자 동의)
  3) 클라이언트 비밀 생성
  4) 아래 환경변수 설정 (.env)
       M365_TENANT_ID=...
       M365_CLIENT_ID=...
       M365_CLIENT_SECRET=...

이 모듈은 msal, requests 가 설치돼 있어야 동작한다.
"""

from __future__ import annotations

import os

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = ["https://graph.microsoft.com/.default"]


class GraphClient:
    def __init__(self) -> None:
        self.tenant = os.environ.get("M365_TENANT_ID", "")
        self.client_id = os.environ.get("M365_CLIENT_ID", "")
        self.secret = os.environ.get("M365_CLIENT_SECRET", "")
        self._token: str | None = None

    def configured(self) -> bool:
        return bool(self.tenant and self.client_id and self.secret)

    def _get_token(self) -> str:
        import msal  # 지연 임포트: M365 를 안 쓰면 설치 불필요

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant}",
            client_credential=self.secret,
        )
        result = app.acquire_token_for_client(scopes=SCOPE)
        if "access_token" not in result:
            raise RuntimeError(
                f"토큰 발급 실패: {result.get('error_description', result)}"
            )
        return result["access_token"]

    def _headers(self) -> dict:
        if self._token is None:
            self._token = self._get_token()
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def find_user(self, name: str) -> dict | None:
        """표시 이름으로 사용자 1명 조회. 동명이인이 없다는 전제."""
        import requests

        r = requests.get(
            f"{GRAPH}/users",
            headers=self._headers(),
            params={
                "$filter": f"displayName eq '{name}'",
                "$select": "id,displayName,userPrincipalName,accountEnabled",
            },
            timeout=30,
        )
        r.raise_for_status()
        users = r.json().get("value", [])
        return users[0] if users else None

    def disable_account(self, user_id: str) -> None:
        import requests

        r = requests.patch(
            f"{GRAPH}/users/{user_id}",
            headers=self._headers(),
            json={"accountEnabled": False},
            timeout=30,
        )
        r.raise_for_status()

    def revoke_sessions(self, user_id: str) -> None:
        """모든 기기의 로그인 세션을 강제 만료."""
        import requests

        r = requests.post(
            f"{GRAPH}/users/{user_id}/revokeSignInSessions",
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()

    def list_licenses(self, user_id: str) -> list[str]:
        import requests

        r = requests.get(
            f"{GRAPH}/users/{user_id}/licenseDetails",
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return [item["skuId"] for item in r.json().get("value", [])]

    def remove_licenses(self, user_id: str, sku_ids: list[str]) -> None:
        import requests

        if not sku_ids:
            return
        r = requests.post(
            f"{GRAPH}/users/{user_id}/assignLicense",
            headers=self._headers(),
            json={"addLicenses": [], "removeLicenses": sku_ids},
            timeout=30,
        )
        r.raise_for_status()

    def list_recent_messages(
        self, mailbox: str, top: int = 100, since_iso: str | None = None
    ) -> list[dict]:
        """받은편지함의 최근 메일을 가져온다(Mail.Read 권한 필요).

        /messages 는 모든 폴더가 섞이므로 받은편지함(inbox)만 콕 집어 읽는다.
        받은편지함이 많아도 조회 기간(since_iso)까지는 확실히 닿도록 페이지를
        따라가며(@odata.nextLink) 가져온다. top 은 '전체 상한'으로 쓴다.
        기간·제목 필터는 호출부에서 파이썬으로 처리한다(가장 확실).
        """
        import requests

        url = f"{GRAPH}/users/{mailbox}/mailFolders/inbox/messages"
        params = {
            "$top": min(top, 200),  # 페이지당 개수(그래프 상한 고려)
            "$select": "subject,receivedDateTime,from,bodyPreview,body",
            "$orderby": "receivedDateTime desc",
        }
        out: list[dict] = []
        for _ in range(50):  # 페이지 폭주 방지용 안전 상한
            r = requests.get(url, headers=self._headers(), params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            page = data.get("value", [])
            out.extend(page)
            # 조회 기간을 지났거나(내림차순) 상한에 닿으면 그만
            if since_iso and page and (page[-1].get("receivedDateTime", "") < since_iso):
                break
            if len(out) >= top:
                break
            url = data.get("@odata.nextLink")
            params = None  # nextLink 에 쿼리가 포함돼 있음
            if not url:
                break
        return out[:top]

    def search_messages(self, mailbox: str, search_term: str, top: int = 50) -> list[dict]:
        """메일함 전체에서 검색어로 메일을 찾는다($search, 폴더 깊이 무관)."""
        import requests

        r = requests.get(
            f"{GRAPH}/users/{mailbox}/messages",
            headers=self._headers(),
            params={
                "$search": f'"{search_term}"',
                "$top": top,
                "$select": "subject,receivedDateTime,from,bodyPreview,body",
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("value", [])
