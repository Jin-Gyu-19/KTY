"use strict";

const STATUS_LABEL = {
  pending: "대기",
  in_progress: "진행 중",
  awaiting: "확인 필요",
  done: "완료",
  error: "오류",
};

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "요청 실패");
  return data;
}

let scenarios = [];

let restorePrompted = false;

async function refresh() {
  const data = await api("/api/status");
  scenarios = data.scenarios;
  renderTargetList(data.targets);
  renderChecklist(data.targets);
  maybePromptRestore(data.restorable);
  const tm = document.getElementById("testMode");
  if (tm) tm.checked = !!data.test_mode;
}

// 앱을 열 때 이전 작업이 있으면 한 번 물어본다.
function maybePromptRestore(r) {
  if (restorePrompted || !r || !r.available) return;
  restorePrompted = true;
  const names = (r.names || []).slice(0, 5).join(", ");
  const more = r.count > 5 ? " 외" : "";
  const msg = `이전 작업내용이 있습니다 (${r.count}명: ${names}${more}).\n불러올까요?`;
  if (confirm(msg)) {
    api("/api/history/restore", "POST", {})
      .then(refresh)
      .catch((e) => alert(e.message));
  }
}

async function toggleHistory() {
  const el = document.getElementById("history");
  if (el.dataset.open === "1") {
    el.innerHTML = "";
    el.dataset.open = "0";
    return;
  }
  let data;
  try {
    data = await api("/api/history");
  } catch (e) {
    alert(e.message);
    return;
  }
  el.dataset.open = "1";
  el.innerHTML = "";
  const list = data.history || [];
  if (!list.length) {
    el.innerHTML = '<p class="muted">저장된 최근 처리내용이 없습니다.</p>';
    return;
  }
  list.forEach((s) => {
    const row = document.createElement("div");
    row.className = "target-row";
    const names = (s.names || []).slice(0, 6).join(", ");
    const info = document.createElement("span");
    info.innerHTML =
      `<span class="muted">${(s.saved_at || "").replace("T", " ").slice(0, 16)}</span> · ` +
      `<b>${s.count}명</b> <span class="muted">${names}${s.count > 6 ? " 외" : ""}</span>`;
    const b = btn("불러오기", "ghost");
    b.onclick = () =>
      run(async () => {
        const r = await api("/api/history/restore", "POST", { id: s.id });
        el.dataset.open = "0";
        el.innerHTML = "";
        return r;
      });
    row.appendChild(info);
    row.appendChild(b);
    el.appendChild(row);
  });
}

function btn(label, cls) {
  const b = document.createElement("button");
  b.textContent = label;
  if (cls) b.className = cls;
  return b;
}

function progressText(sites) {
  const ids = scenarios.map((s) => s.id);
  const total = ids.length;
  const done = ids.filter((id) => (sites[id] || {}).status === "done").length;
  const hasErr = ids.some((id) => (sites[id] || {}).status === "error");
  const hasWait = ids.some((id) =>
    ["awaiting", "in_progress"].includes((sites[id] || {}).status)
  );
  let mark = "";
  if (done === total) mark = "✅";
  else if (hasErr) mark = "⚠️";
  else if (hasWait) mark = "…";
  return `${done}/${total} ${mark}`;
}

// ----- 대상자 목록 -----
function renderTargetList(t) {
  const el = document.getElementById("targetList");
  el.innerHTML = "";
  const list = (t && t.targets) || [];
  if (!list.length) {
    el.innerHTML = '<p class="muted">대상자를 추가하거나 엑셀을 올려주세요.</p>';
    return;
  }

  const bar = document.createElement("div");
  bar.style.textAlign = "right";
  bar.style.marginBottom = "6px";
  const clearAll = btn("전체 비우기", "ghost");
  clearAll.onclick = () => {
    if (confirm("대상자 목록을 전부 비울까요?"))
      run(() => api("/api/targets/clear", "POST"));
  };
  bar.appendChild(clearAll);
  el.appendChild(bar);

  list.forEach((tg) => {
    const row = document.createElement("div");
    row.className = "target-row" + (tg.key === t.active ? " active" : "");

    const info = document.createElement("span");
    info.innerHTML =
      `<b>${tg.name}</b> <span class="muted">${tg.resign_date || ""}</span>` +
      ` &nbsp;<span class="tag">${progressText(tg.sites || {})}</span>`;

    const actions = document.createElement("span");
    actions.className = "target-actions";

    const selBtn = btn(tg.key === t.active ? "선택됨" : "선택", "ghost");
    selBtn.disabled = tg.key === t.active;
    selBtn.onclick = () => run(() => api("/api/target/active", "POST", { key: tg.key }));

    const resetBtn = btn("초기화", "ghost");
    resetBtn.title = "이 사람의 진행 기록을 대기 상태로 되돌립니다";
    resetBtn.onclick = () => run(() => api("/api/target/reset", "POST", { key: tg.key }));

    const delBtn = btn("삭제", "ghost");
    delBtn.onclick = () => {
      if (confirm(`'${tg.name}' 을(를) 목록에서 삭제할까요?`))
        run(() => api("/api/target/remove", "POST", { key: tg.key }));
    };

    actions.appendChild(selBtn);
    actions.appendChild(resetBtn);
    actions.appendChild(delBtn);
    row.appendChild(info);
    row.appendChild(actions);
    el.appendChild(row);
  });
}

// ----- 활성 대상자의 사이트 체크리스트 -----
function renderChecklist(t) {
  const titleEl = document.getElementById("activeTitle");
  const listEl = document.getElementById("checklist");
  const active = (t.targets || []).find((x) => x.key === t.active);

  if (!active) {
    titleEl.textContent = "";
    listEl.innerHTML = "";
    return;
  }
  titleEl.textContent = `처리 중: ${active.name} · 퇴사일 ${active.resign_date}`;
  listEl.innerHTML = "";

  scenarios.forEach((s, i) => {
    const site = active.sites[s.id] || { status: "pending", message: "" };
    const row = document.createElement("div");
    row.className = "site";

    const isApi = s.kind === "api";
    const canOpen = !isApi && ["pending", "error"].includes(site.status);
    const canRun = isApi
      ? ["pending", "error"].includes(site.status)
      : ["in_progress", "awaiting", "error"].includes(site.status);

    row.innerHTML = `
      <div class="idx">${i + 1}</div>
      <div class="body">
        <div class="title">${s.name}
          <span class="tag">${isApi ? "API" : "브라우저"}</span>
          <span class="badge ${site.status}">${STATUS_LABEL[site.status] || site.status}</span>
        </div>
        <div class="msg">${site.message || ""}</div>
      </div>
      <div class="actions"></div>`;

    const actions = row.querySelector(".actions");
    if (!isApi) {
      const openBtn = btn("열기", canOpen ? "" : "ghost");
      openBtn.disabled = !canOpen;
      openBtn.onclick = () => run(() => api(`/api/site/${s.id}/open`, "POST"));
      actions.appendChild(openBtn);
    }
    const runBtn = btn("자동 처리", "");
    runBtn.disabled = !canRun;
    runBtn.onclick = () => run(() => api(`/api/site/${s.id}/run`, "POST"));
    actions.appendChild(runBtn);

    const doneBtn = btn("완료", "ghost");
    doneBtn.disabled = site.status === "done";
    doneBtn.onclick = () => run(() => api(`/api/site/${s.id}/done`, "POST"));
    actions.appendChild(doneBtn);

    listEl.appendChild(row);
  });
}

async function run(fn) {
  try {
    const r = await fn();
    if (r && r.message) console.log(r.message);
  } catch (e) {
    alert(e.message);
  }
  await refresh();
}

// ----- 입력 핸들러 -----
document.getElementById("addBtn").onclick = async () => {
  const name = document.getElementById("name").value.trim();
  const resign_date = document.getElementById("resign_date").value.trim();
  try {
    await api("/api/target", "POST", { name, resign_date });
    document.getElementById("name").value = "";
    await refresh();
  } catch (e) {
    alert(e.message);
  }
};

document.getElementById("uploadBtn").onclick = async () => {
  const fileEl = document.getElementById("excel");
  if (!fileEl.files.length) {
    alert("엑셀 파일을 먼저 선택하세요.");
    return;
  }
  const fd = new FormData();
  fd.append("file", fileEl.files[0]);
  try {
    const res = await fetch("/api/target/excel", { method: "POST", body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "업로드 실패");
    fileEl.value = "";
    await refresh();
  } catch (e) {
    alert(e.message);
  }
};

document.getElementById("historyBtn").onclick = toggleHistory;

document.getElementById("runAllBtn").onclick = async () => {
  const msg =
    "목록의 모든 대상자를 순서대로 처리합니다.\n" +
    "먼저 [열기]로 브라우저를 열고 로그인해 두어야 합니다.\n계속할까요?";
  if (!confirm(msg)) return;
  try {
    const r = await api("/api/run-all", "POST");
    await refresh();
    if (r && r.message) alert(r.message);
  } catch (e) {
    alert(e.message);
    await refresh();
  }
};

document.getElementById("testMode").onchange = (e) => {
  api("/api/testmode", "POST", { on: e.target.checked }).catch((err) =>
    alert(err.message)
  );
};

refresh();
