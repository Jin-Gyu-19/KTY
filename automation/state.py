"""퇴사 처리 진행상태 저장 (여러 명 동시 관리).

중간에 앱이 꺼져도 이어서 할 수 있도록 data/progress.json 에 기록한다.
동명이인이 없으므로 '이름|퇴사일' 을 대상 키로 쓴다.

저장 구조:
  {
    "targets": { "이형진|2026-07-15": {name, resign_date, created_at, sites{}}, ... },
    "active":  "이형진|2026-07-15"     # 현재 작업 중인 대상 키
  }

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
        return {"targets": {}, "active": None}
    with open(_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("targets", {})
    data.setdefault("active", None)
    return data


def _save(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _PATH)


def _key(name: str, resign_date: str) -> str:
    return f"{name}|{resign_date}"


def _first_key(targets: dict) -> str | None:
    return next(iter(targets), None)


def add_target(
    name: str, resign_date: str, site_ids: list[str], make_active: bool = False
) -> dict:
    """대상자를 추가(또는 갱신)한다. 이미 있으면 사이트 목록만 동기화한다."""
    with _LOCK:
        data = _load()
        targets = data["targets"]
        key = _key(name, resign_date)
        entry = targets.get(key)
        if entry is None:
            entry = {
                "name": name,
                "resign_date": resign_date,
                "created_at": _now(),
                "sites": {},
            }
        for sid in site_ids:
            entry["sites"].setdefault(
                sid, {"status": "pending", "message": "", "updated_at": ""}
            )
        targets[key] = entry
        if make_active or not data.get("active"):
            data["active"] = key
        _save(data)
        return entry


def snapshot() -> dict:
    """UI 표시용 전체 상태: 대상자 목록과 현재 활성 키."""
    with _LOCK:
        data = _load()
        targets = data["targets"]
        active = data.get("active")
        if active not in targets:
            active = _first_key(targets)
        return {
            "active": active,
            "targets": [{"key": k, **v} for k, v in targets.items()],
        }


def set_active(key: str) -> bool:
    with _LOCK:
        data = _load()
        if key in data["targets"]:
            data["active"] = key
            _save(data)
            return True
        return False


def active_entry() -> dict | None:
    with _LOCK:
        data = _load()
        targets = data["targets"]
        key = data.get("active")
        if key not in targets:
            key = _first_key(targets)
        return targets.get(key) if key else None


def remove_target(key: str) -> bool:
    with _LOCK:
        data = _load()
        targets = data["targets"]
        if key in targets:
            del targets[key]
            if data.get("active") == key:
                data["active"] = _first_key(targets)
            _save(data)
            return True
        return False


def set_site(
    name: str, resign_date: str, site_id: str, status: str, message: str = ""
) -> None:
    with _LOCK:
        data = _load()
        key = _key(name, resign_date)
        entry = data["targets"].get(key)
        if entry is None:
            return
        entry["sites"][site_id] = {
            "status": status,
            "message": message,
            "updated_at": _now(),
        }
        _save(data)
