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

async function refresh() {
  const data = await api("/api/status");
  scenarios = data.scenarios;
  render(data.current);
}

function render(current) {
  const curEl = document.getElementById("current");
  const listEl = document.getElementById("checklist");

  if (!current) {
    curEl.textContent = "퇴사자 정보를 입력하고 [시작]을 누르세요.";
    listEl.innerHTML = "";
    return;
  }
  curEl.textContent = `대상: ${current.name} · 퇴사일 ${current.resign_date}`;

  listEl.innerHTML = "";
  scenarios.forEach((s, i) => {
    const site = current.sites[s.id] || { status: "pending", message: "" };
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

function btn(label, cls) {
  const b = document.createElement("button");
  b.textContent = label;
  if (cls) b.className = cls;
  return b;
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

document.getElementById("startBtn").onclick = async () => {
  const name = document.getElementById("name").value.trim();
  const resign_date = document.getElementById("resign_date").value.trim();
  try {
    await api("/api/target", "POST", { name, resign_date });
    await refresh();
  } catch (e) {
    alert(e.message);
  }
};

refresh();
