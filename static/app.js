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
    renderTargets(data.targets);
  } catch (e) {
    alert(e.message);
  }
};

function renderTargets(targets) {
  const el = document.getElementById("targets");
  el.innerHTML = "";
  if (!targets || !targets.length) return;

  const title = document.createElement("div");
  title.className = "muted";
  title.style.margin = "6px 0";
  title.textContent = `엑셀에서 ${targets.length}명 불러옴 — 처리할 대상을 선택하세요:`;
  el.appendChild(title);

  targets.forEach((t) => {
    const row = document.createElement("div");
    row.className = "target-row";
    const info = document.createElement("span");
    info.innerHTML = `<b>${t.name}</b> <span class="muted">${t.resign_date || "(퇴사일 없음)"}</span>`;
    const b = btn("선택", "ghost");
    b.onclick = async () => {
      document.getElementById("name").value = t.name;
      document.getElementById("resign_date").value = t.resign_date || "";
      try {
        await api("/api/target", "POST", { name: t.name, resign_date: t.resign_date });
        await refresh();
      } catch (e) {
        alert(e.message);
      }
    };
    row.appendChild(info);
    row.appendChild(b);
    el.appendChild(row);
  });
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
