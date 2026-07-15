"""퇴사자 처리 자동화 앱 (로컬 실행).

실행:
    pip install -r requirements.txt
    playwright install chromium
    python app.py
    → 브라우저에서 http://127.0.0.1:5000 접속

흐름:
  1) 퇴사자 이름 + 퇴사일 입력
  2) 사이트 체크리스트가 순서대로 표시됨
  3) 각 사이트에서 [열기] → 사용자가 직접 로그인 → [자동 처리]
     - 브라우저 사이트: 저장/제출 직전에서 멈춤(사람이 최종 확인)
     - API 사이트(M365): 로그인 없이 바로 처리
  4) 처리 후 [완료] 로 체크. 진행상태는 저장돼 이어서 가능.
"""

from __future__ import annotations

# .env 를 먼저 읽어야 M365_*, BROWSER_CDP_URL 등이 반영된다.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from flask import Flask, jsonify, render_template, request

from automation import registry, state
from automation.controller import controller
from automation.sites.base import Employee

app = Flask(__name__)


def _scenario_list() -> list[dict]:
    return [
        {"id": s.id, "name": s.name, "kind": s.kind, "url": s.url}
        for s in registry.all_scenarios()
    ]


@app.get("/")
def index():
    return render_template("index.html")


def _site_ids() -> list[str]:
    return [s.id for s in registry.all_scenarios()]


@app.get("/api/status")
def api_status():
    return jsonify({"scenarios": _scenario_list(), "targets": state.snapshot()})


@app.post("/api/target")
def api_target():
    """대상자 1명 추가(수동). 추가한 사람을 활성 대상으로 만든다."""
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    resign_date = (data.get("resign_date") or "").strip()
    if not name or not resign_date:
        return jsonify({"error": "이름과 퇴사일을 모두 입력하세요."}), 400
    state.add_target(name, resign_date, _site_ids(), make_active=True)
    return jsonify({"targets": state.snapshot()})


@app.post("/api/target/active")
def api_target_active():
    key = (request.get_json(force=True).get("key") or "").strip()
    if not state.set_active(key):
        return jsonify({"error": "대상을 찾지 못했습니다."}), 404
    return jsonify({"targets": state.snapshot()})


@app.post("/api/target/remove")
def api_target_remove():
    key = (request.get_json(force=True).get("key") or "").strip()
    state.remove_target(key)
    return jsonify({"targets": state.snapshot()})


@app.post("/api/target/reset")
def api_target_reset():
    key = (request.get_json(force=True).get("key") or "").strip()
    state.reset_target(key)
    return jsonify({"targets": state.snapshot()})


@app.post("/api/targets/clear")
def api_targets_clear():
    state.clear_all()
    return jsonify({"targets": state.snapshot()})


def _fmt_date(v) -> str:
    """엑셀 셀 값을 YYYY-MM-DD 문자열로 정규화한다."""
    import datetime

    if v is None:
        return ""
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 8:  # 20260715 → 2026-07-15
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return s.replace(".", "-").replace("/", "-").replace(" ", "")


def _parse_excel(file_storage) -> list[dict]:
    """이름/퇴사일 열이 있는 엑셀을 읽어 대상자 목록을 만든다.

    헤더에 '이름/성명', '퇴사/퇴직/날짜/일자' 가 있으면 그 열을 쓰고,
    없으면 첫 열=이름, 둘째 열=퇴사일 로 간주한다.
    """
    import io

    from openpyxl import load_workbook

    wb = load_workbook(filename=io.BytesIO(file_storage.read()), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    def _txt(v) -> str:
        return str(v).strip() if v is not None else ""

    name_idx, date_idx, start = 0, 1, 0
    header = [_txt(c) for c in rows[0]]
    found = False
    for i, t in enumerate(header):
        if any(k in t for k in ("이름", "성명")):
            name_idx, found = i, True
        if any(k in t for k in ("퇴사", "퇴직", "날짜", "일자")):
            date_idx, found = i, True
    if found:
        start = 1  # 헤더 행은 건너뛴다

    targets = []
    for row in rows[start:]:
        if not row:
            continue
        name = _txt(row[name_idx]) if name_idx < len(row) else ""
        raw = row[date_idx] if date_idx < len(row) else None
        if not name:
            continue
        targets.append({"name": name, "resign_date": _fmt_date(raw)})
    return targets


@app.post("/api/target/excel")
def api_target_excel():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"error": "엑셀 파일을 선택하세요."}), 400
    try:
        targets = _parse_excel(f)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"엑셀을 읽지 못했습니다: {exc}"}), 400
    if not targets:
        return jsonify({"error": "대상자를 찾지 못했습니다. (이름/퇴사일 열을 확인해 주세요)"}), 400
    # 파싱한 대상자 전원을 목록에 추가한다(활성은 기존 유지 or 첫 대상).
    site_ids = _site_ids()
    for t in targets:
        if t.get("resign_date"):
            state.add_target(t["name"], t["resign_date"], site_ids)
    return jsonify({"targets": state.snapshot(), "added": len(targets)})


def _current_employee() -> Employee | None:
    cur = state.active_entry()
    if not cur:
        return None
    return Employee(name=cur["name"], resign_date=cur["resign_date"])


@app.post("/api/site/<site_id>/open")
def api_open(site_id: str):
    scenario = registry.get(site_id)
    emp = _current_employee()
    if scenario is None:
        return jsonify({"error": "알 수 없는 사이트"}), 404
    if emp is None:
        return jsonify({"error": "먼저 퇴사자를 입력하세요."}), 400
    if scenario.kind != "browser":
        return jsonify({"error": "이 사이트는 브라우저를 열지 않습니다(API 처리)."}), 400
    try:
        controller.open_site(scenario.url)
        state.set_site(emp.name, emp.resign_date, site_id, "in_progress", "로그인 대기 중")
        return jsonify({"ok": True, "message": "브라우저에서 로그인 후 [자동 처리]를 누르세요."})
    except Exception as exc:  # noqa: BLE001
        state.set_site(emp.name, emp.resign_date, site_id, "error", str(exc))
        return jsonify({"error": str(exc)}), 500


@app.post("/api/site/<site_id>/run")
def api_run(site_id: str):
    scenario = registry.get(site_id)
    emp = _current_employee()
    if scenario is None:
        return jsonify({"error": "알 수 없는 사이트"}), 404
    if emp is None:
        return jsonify({"error": "먼저 퇴사자를 입력하세요."}), 400
    try:
        if scenario.kind == "api":
            result = scenario.run_api(emp)
        else:
            result = controller.run_scenario(scenario, emp)

        if not result.ok:
            status = "error"
        elif result.awaiting:
            status = "awaiting"
        else:
            status = "done"
        state.set_site(emp.name, emp.resign_date, site_id, status, result.message)
        return jsonify(
            {"ok": result.ok, "awaiting": result.awaiting, "message": result.message}
        )
    except Exception as exc:  # noqa: BLE001
        state.set_site(emp.name, emp.resign_date, site_id, "error", str(exc))
        return jsonify({"error": str(exc)}), 500


@app.post("/api/site/<site_id>/done")
def api_done(site_id: str):
    emp = _current_employee()
    if emp is None:
        return jsonify({"error": "먼저 퇴사자를 입력하세요."}), 400
    state.set_site(emp.name, emp.resign_date, site_id, "done", "완료 처리됨")
    return jsonify({"ok": True})


if __name__ == "__main__":
    # 로컬 전용. 회사 PC 한 대에서 사용하는 것을 전제로 한다.
    app.run(host="127.0.0.1", port=5000, debug=False)
