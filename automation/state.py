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
_PATH = os.path.join(_DATA_DIR, "progress.json")  # 현재 작업 세트
_HIST = os.path.join(_DATA_DIR, "history.json")  # 지난 작업 보관(최근 처리내용)
_CRED = os.path.join(_DATA_DIR, "credentials.json")  # 사이트별 자동 로그인 정보(로컬 전용)
_HIST_MAX = 20


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


def _load_hist() -> dict:
    if not os.path.exists(_HIST):
        return {"sessions": []}
    with open(_HIST, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("sessions", [])
    return data


def _save_hist(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _HIST + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _HIST)


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


def reset_target(key: str) -> bool:
    """대상자의 모든 사이트 상태를 대기로 되돌린다(기록 지우기)."""
    with _LOCK:
        data = _load()
        entry = data["targets"].get(key)
        if entry is None:
            return False
        for sid in list(entry.get("sites", {})):
            entry["sites"][sid] = {"status": "pending", "message": "", "updated_at": ""}
        _save(data)
        return True


def clear_all() -> None:
    """대상자 목록 전체를 비운다."""
    with _LOCK:
        _save({"targets": {}, "active": None})


# ----- 작업 보관(최근 처리내용) -----
def begin_session() -> None:
    """앱 시작 시 호출. 이전 세션의 작업이 남아 있으면 보관함으로 옮기고,
    현재 작업 세트는 비운 상태로 시작한다(기본 빈 화면)."""
    with _LOCK:
        data = _load()
        targets = data.get("targets", {})
        if targets:
            hist = _load_hist()
            hist["sessions"].insert(
                0, {"id": _now(), "saved_at": _now(), "targets": targets}
            )
            hist["sessions"] = hist["sessions"][:_HIST_MAX]
            _save_hist(hist)
        _save({"targets": {}, "active": None})


def latest_restorable() -> dict:
    """가장 최근 보관 세션 요약(불러오기 팝업용)."""
    with _LOCK:
        hist = _load_hist()
        if not hist["sessions"]:
            return {"available": False}
        s = hist["sessions"][0]
        t = s.get("targets", {})
        return {
            "available": bool(t),
            "id": s["id"],
            "saved_at": s.get("saved_at", ""),
            "count": len(t),
            "names": [v.get("name", "") for v in t.values()],
        }


def list_history() -> list[dict]:
    """보관된 세션 목록(최근 처리내용 메뉴용)."""
    with _LOCK:
        hist = _load_hist()
        out = []
        for s in hist["sessions"]:
            t = s.get("targets", {})
            out.append(
                {
                    "id": s["id"],
                    "saved_at": s.get("saved_at", ""),
                    "count": len(t),
                    "names": [v.get("name", "") for v in t.values()],
                }
            )
        return out


# ----- 사이트별 자동 로그인 정보 (로컬 전용, git 제외) -----
def _load_cred() -> dict:
    if not os.path.exists(_CRED):
        return {}
    try:
        with open(_CRED, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cred(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _CRED + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _CRED)


def set_credentials(site_id: str, username: str, password: str) -> None:
    from . import secret

    enc, value = secret.encrypt(password)
    with _LOCK:
        data = _load_cred()
        data[site_id] = {"username": username, "password": value, "enc": enc}
        _save_cred(data)


def clear_credentials(site_id: str) -> None:
    with _LOCK:
        data = _load_cred()
        if site_id in data:
            del data[site_id]
            _save_cred(data)


def get_credentials(site_id: str) -> dict | None:
    from . import secret

    with _LOCK:
        c = _load_cred().get(site_id)
    if not c:
        return None
    # 저장된 값을 복호화해서 평문 비밀번호로 돌려준다(로그인 시에만 사용).
    return {
        "username": c.get("username", ""),
        "password": secret.decrypt(c.get("enc", "plain"), c.get("password", "")),
    }


def has_credentials(site_id: str) -> bool:
    with _LOCK:
        c = _load_cred().get(site_id)
    return bool(c and c.get("username"))


def restore(session_id: str | None = None) -> bool:
    """보관 세션을 현재 작업 세트로 불러온다(없으면 최근 것). 기존 목록에 합친다."""
    with _LOCK:
        hist = _load_hist()
        sess = None
        if session_id:
            sess = next((s for s in hist["sessions"] if s["id"] == session_id), None)
        elif hist["sessions"]:
            sess = hist["sessions"][0]
        if not sess:
            return False
        data = _load()
        data["targets"].update(sess.get("targets", {}))
        if not data.get("active"):
            data["active"] = _first_key(data["targets"])
        _save(data)
        return True


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
