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


_BLOCK_TAGS = {"br", "div", "p", "li", "tr", "table", "h1", "h2", "h3"}


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def _strip_html(html: str) -> str:
    """HTML 을 텍스트로. 블록 태그(div/br/p 등)는 줄바꿈으로 바꿔 줄 구조를 살린다."""
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
    dept = None

    _stop = {
        "안내", "명단", "처리", "목록", "현황", "보고", "공지", "관련",
        "확인", "부탁", "감사", "성명", "이름", "부서", "소속", "퇴사",
        "퇴직", "대상", "직원", "사원", "귀하", "참조", "수신",
    }

    # 이름: 한글 2~4자 + (동명이인 구분용) 뒤 숫자 유지. 예: 홍길동, 홍길동2
    name = None
    m_strong = re.search(
        r"(?:이\s*름|성\s*명|성\s*함|직원명)\s*[:：]?\s*([가-힣]{2,4}\d*)", text
    )
    if m_strong:
        name = m_strong.group(1)
    if not name:
        # '대상자/퇴사자' 뒤 이름. (?![가-힣]) 로 더 긴 단어의 일부(안내드립…)는 제외
        for m in re.finditer(
            r"(?:대상자|퇴사자)\s*[:：]?\s*([가-힣]{2,4}\d*)(?![가-힣])", text
        ):
            # 숫자 뗀 순수 한글 부분이 제목성 단어면 제외
            base = re.match(r"([가-힣]+)", m.group(1)).group(1)
            if base not in _stop:
                name = m.group(1)
                break

    # 라벨이 전혀 없는 형식: 이름만 있는 줄(한글 2~4자 + 뒤 숫자)을 이름으로 본다.
    lines = [ln.strip() for ln in text.splitlines()]
    if not name:
        for i, s in enumerate(lines):
            m = re.fullmatch(r"([가-힣]{2,4}\d*)", s)
            if m:
                base = re.match(r"([가-힣]+)", m.group(1)).group(1)
                if base not in _stop:
                    name = m.group(1)
                    if i + 1 < len(lines):
                        nxt = lines[i + 1]
                        if nxt and "퇴사" not in nxt and not re.search(r"20\d{2}", nxt):
                            dept = dept or nxt
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


def _scan(
    mailbox: str,
    subject_keyword: str | None,
    sender: str | None,
    since_days: int,
    top: int,
) -> tuple[list[dict], list[str]]:
    """받은편지함을 훑어 메일별 판정 결과 행 리스트를 만든다(단일 로직).

    debug_list(모달)와 import_from_mail(등록)이 '똑같이' 이걸 쓰므로 결과가 안 갈린다.
    """
    client = GraphClient()
    if not client.configured():
        raise RuntimeError(
            "M365 환경변수(M365_TENANT_ID/CLIENT_ID/CLIENT_SECRET)가 설정되지 않았습니다."
        )
    if not mailbox:
        raise RuntimeError("읽을 메일함(M365_MAILBOX)이 .env 에 설정되지 않았습니다.")

    keywords = [k.strip() for k in (subject_keyword or "").split(",") if k.strip()]
    sender_l = (sender or "").strip().lower() or None

    since_iso = None
    if since_days and since_days > 0:
        from datetime import datetime, timedelta, timezone

        since_iso = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    rows = []
    for m in client.list_recent_messages(mailbox, top=top, since_iso=since_iso):
        subj = m.get("subject", "") or ""
        recv = m.get("receivedDateTime", "") or ""
        addr = (m.get("from") or {}).get("emailAddress") or {}
        frm = addr.get("name") or addr.get("address") or ""
        hay = f"{addr.get('name', '')} {addr.get('address', '')}".lower()

        in_window = (not since_iso) or (recv >= since_iso)
        subject_match = (not keywords) or any(k in subj for k in keywords)
        sender_match = (not sender_l) or (sender_l in hay)

        name = date = None
        if in_window and subject_match and sender_match:
            body = m.get("body") or {}
            if (body.get("contentType") or "").lower() == "html":
                bt = _strip_html(body.get("content", ""))
            else:
                bt = body.get("content", "") or m.get("bodyPreview", "")
            p = parse_resignation(subj + "\n" + bt)
            if p:
                name, date = p["name"], p["resign_date"]

        rows.append(
            {
                "subject": subj,
                "sender": frm,
                "received": recv[:16].replace("T", " "),
                "in_window": in_window,
                "subject_match": subject_match,
                "sender_match": sender_match,
                "name": name,
                "resign_date": date,
                "parsed": f"{name} / {date}" if name else None,
            }
        )
    return rows, keywords


def debug_list(
    mailbox: str,
    subject_keyword: str | None = "퇴사",
    sender: str | None = None,
    since_days: int = 90,
    top: int = 400,
) -> list[dict]:
    """받은편지함 최근 메일을 각 메일별 판정 결과와 함께 돌려준다(진단/확인용)."""
    rows, _ = _scan(mailbox, subject_keyword, sender, since_days, top)
    return rows


def import_from_mail(
    mailbox: str,
    subject_keyword: str | None = "퇴사",
    sender: str | None = None,
    since_days: int = 90,
    top: int = 400,
) -> tuple[list[dict], dict]:
    """메일함을 훑어 조건에 맞는 퇴사 공지에서 퇴사자 목록을 만든다(모달과 동일 로직)."""
    rows, keywords = _scan(mailbox, subject_keyword, sender, since_days, top)

    found: list[dict] = []
    seen = set()
    for r in rows:
        if not r["name"]:
            continue
        key = f"{r['name']}|{r['resign_date']}"
        if key not in seen:
            seen.add(key)
            found.append(
                {
                    "name": r["name"],
                    "resign_date": r["resign_date"],
                    "subject": r["subject"],
                }
            )

    matched = [r for r in rows if r["in_window"] and r["subject_match"] and r["sender_match"]]
    stats = {
        "total": len(rows),
        "subject_matched": len(matched),
        "parsed": len(found),
        "matched_no_parse": [r["subject"][:40] for r in matched if not r["name"]][:5],
        "keywords": keywords,
        "recent_subjects": [r["subject"][:40] for r in rows[:15]],
        "subjects_with_toi": [r["subject"][:40] for r in rows if "퇴" in r["subject"]][:5],
    }
    return found, stats
