"""M365(Outlook) 메일에서 퇴사자(이름·퇴사일)를 읽어온다.

조건(기본값, .env 로 조정 가능):
  - 보낸사람 표시명/주소에 MAIL_SENDER(예: 이소안) 포함
  - 제목에 MAIL_SUBJECT_KEYWORD(예: 퇴사) 포함
  - 본문에 이름/부서/퇴사일 포함

안전을 위해 '대상자 목록 등록'까지만 하고, 실제 퇴사 처리는 사람이 확인 후 진행한다.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from .integrations.graph import GraphClient


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join(self._parts)


def _strip_html(html: str) -> str:
    s = _Stripper()
    try:
        s.feed(html or "")
    except Exception:
        return html or ""
    return s.text()


def _normalize_date(y: str, mo: str, d: str) -> str:
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def parse_resignation(text: str) -> dict | None:
    """메일 텍스트에서 {name, resign_date, dept?} 를 추출한다. 못 찾으면 None."""
    text = (text or "").replace("\xa0", " ")

    # 이름: 먼저 '이름/성명/성함/직원명' 을 우선 찾는다.
    name = None
    m_strong = re.search(
        r"(?:이\s*름|성\s*명|성\s*함|직원명)\s*[:：]?\s*([가-힣]{2,4})", text
    )
    if m_strong:
        name = m_strong.group(1)
    else:
        # 없으면 '대상자/퇴사자' 뒤 이름 (단, '안내/명단' 같은 제목성 단어는 제외)
        _stop = {"안내", "명단", "처리", "목록", "현황", "보고", "공지", "관련"}
        for m in re.finditer(r"(?:대상자|퇴사자)\s*[:：]?\s*([가-힣]{2,4})", text):
            if m.group(1) not in _stop:
                name = m.group(1)
                break

    # 부서(선택)
    dept = None
    mdpt = re.search(r"(?:부\s*서|소\s*속|팀)\s*[:：]?\s*([^\n\r,/|]{1,20})", text)
    if mdpt:
        # '퇴사일 ...' 등 뒤 라벨이 붙어 길게 잡히면 잘라낸다
        dept = re.split(r"\s*(?:퇴사|퇴직|최종|입사|성명|이름)", mdpt.group(1))[0].strip()

    # 퇴사일: '퇴사일/퇴직일/퇴사예정일/최종근무일' 근처 날짜 우선
    date = None
    md = re.search(
        r"(?:퇴사일|퇴직일|퇴사\s*예정일|퇴직\s*예정일|최종\s*근무일|퇴사)\D{0,10}"
        r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})",
        text,
    )
    if not md:
        md = re.search(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", text)
    if md:
        date = _normalize_date(*md.groups())
    else:
        md2 = re.search(r"(20\d{2})(\d{2})(\d{2})", text)
        if md2:
            date = _normalize_date(*md2.groups())

    if name and date:
        result = {"name": name, "resign_date": date}
        if dept:
            result["dept"] = dept
        return result
    return None


def import_from_mail(
    mailbox: str,
    subject_keyword: str | None = "퇴사",
    sender: str | None = None,
    top: int = 50,
) -> list[dict]:
    """메일함을 훑어 조건에 맞는 퇴사 공지에서 퇴사자 목록을 만든다."""
    client = GraphClient()
    if not client.configured():
        raise RuntimeError(
            "M365 환경변수(M365_TENANT_ID/CLIENT_ID/CLIENT_SECRET)가 설정되지 않았습니다."
        )
    if not mailbox:
        raise RuntimeError("읽을 메일함(M365_MAILBOX)이 .env 에 설정되지 않았습니다.")

    # 제목 키워드는 쉼표로 여러 개 지정 가능(하나라도 들어있으면 대상). 예: "퇴사,퇴직"
    keywords = [k.strip() for k in (subject_keyword or "").split(",") if k.strip()]

    messages = client.list_recent_messages(mailbox, top=top)
    found: list[dict] = []
    seen = set()
    for m in messages:
        subject = m.get("subject", "") or ""
        if keywords and not any(k in subject for k in keywords):
            continue
        if sender:
            addr = (m.get("from") or {}).get("emailAddress") or {}
            hay = f"{addr.get('name', '')} {addr.get('address', '')}".lower()
            if sender.lower() not in hay:
                continue

        body = m.get("body") or {}
        if (body.get("contentType") or "").lower() == "html":
            body_text = _strip_html(body.get("content", ""))
        else:
            body_text = body.get("content", "") or m.get("bodyPreview", "")

        parsed = parse_resignation(subject + "\n" + body_text)
        if parsed:
            key = f"{parsed['name']}|{parsed['resign_date']}"
            if key not in seen:
                seen.add(key)
                parsed["subject"] = subject
                parsed["received"] = m.get("receivedDateTime", "")
                found.append(parsed)
    return found
