"""퇴사 처리 진행상태 저장.

중간에 앱이 꺼져도 이어서 할 수 있도록 data/progress.json 에 기록한다.
동명이인이 없으므로 '이름|퇴사일' 을 대상 키로 쓴다.

사이트별 상태값:
  pending     대기
  in_progress 브라우저 열림/작업 중
  awaiting    자동 입력 끝, 사람이 최종 제출/확인 필요
  done        완료
  error       오류
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_PATH = os.path.join(_DATA_DIR, "progress.json")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load() -> dict:
    if not os.path.exists(_PATH):
        return {}
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _PATH)


def _key(name: str, resign_date: str) -> str:
    return f"{name}|{resign_date}"


def start_target(name: str, resign_date: str, site_ids: list[str]) -> dict:
    """퇴사자 처리를 시작(또는 이어하기)한다. 현재 대상의 상태를 돌려준다."""
    with _LOCK:
        data = _load()
        key = _key(name, resign_date)
        entry = data.get(key)
        if entry is None:
            entry = {
                "name": name,
                "resign_date": resign_date,
                "created_at": _now(),
                "sites": {},
            }
        # 등록된 사이트 목록과 동기화 (새 사이트 추가 시 반영)
        for sid in site_ids:
            entry["sites"].setdefault(sid, {"status": "pending", "message": "", "updated_at": ""})
        data[key] = entry
        data["_current"] = key
        _save(data)
        return entry


def current() -> dict | None:
    with _LOCK:
        data = _load()
        key = data.get("_current")
        if not key or key not in data:
            return None
        return data[key]


def set_site(name: str, resign_date: str, site_id: str, status: str, message: str = "") -> None:
    with _LOCK:
        data = _load()
        key = _key(name, resign_date)
        entry = data.get(key)
        if entry is None:
            return
        entry["sites"][site_id] = {
            "status": status,
            "message": message,
            "updated_at": _now(),
        }
        _save(data)
