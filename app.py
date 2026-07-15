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


@app.get("/api/status")
def api_status():
    return jsonify({"scenarios": _scenario_list(), "current": state.current()})


@app.post("/api/target")
def api_target():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    resign_date = (data.get("resign_date") or "").strip()
    if not name or not resign_date:
        return jsonify({"error": "이름과 퇴사일을 모두 입력하세요."}), 400
    site_ids = [s.id for s in registry.all_scenarios()]
    entry = state.start_target(name, resign_date, site_ids)
    return jsonify({"current": entry})


def _current_employee() -> Employee | None:
    cur = state.current()
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
