"use strict";

const STATUS_LABEL = {
  pending: "대기",
  in_progress: "진행 중",
  awaiting: "확인 필요",
  done: "완료",
  error: "오류",
  blocked: "퇴사일 전",
};

let enabledSites = null; // null = 아직 모름(전체로 취급)
const selectedKeys = new Set(); // 다중선택된 대상자 key
let autoImportTried = false;

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
  enabledSites = data.enabled_sites || scenarios.map((s) => s.id);
  renderTargetList(data.targets);
  renderChecklist(data.targets);
  maybePromptRestore(data.restorable);
  const tm = document.getElementById("testMode");
  if (tm) tm.checked = !!data.test_mode;
}

// 앱 시작 후 1회: 메일에서 퇴사자 자동 불러오기
async function autoImport() {
  if (autoImportTried) return;
  autoImportTried = true;
  try {
    const r = await api("/api/mail/auto-import", "POST");
    if (r && r.message) {
      await refresh();
      alert("🔔 " + r.message);
    }
  } catch (e) {
    /* 미설정/오류는 조용히 */
  }
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

  // 살아있는 key 만 선택 유지
  const liveKeys = new Set(list.map((x) => x.key));
  [...selectedKeys].forEach((k) => { if (!liveKeys.has(k)) selectedKeys.delete(k); });

  const bar = document.createElement("div");
  bar.className = "bulk-bar";
  const left = document.createElement("span");
  left.className = "muted";
  const selAll = document.createElement("input");
  selAll.type = "checkbox";
  selAll.checked = list.length > 0 && list.every((x) => selectedKeys.has(x.key));
  selAll.onchange = () => {
    if (selAll.checked) list.forEach((x) => selectedKeys.add(x.key));
    else selectedKeys.clear();
    renderTargetList(t);
  };
  left.appendChild(selAll);
  left.appendChild(document.createTextNode(` 전체선택 (${selectedKeys.size}명 선택)`));

  const right = document.createElement("span");
  right.className = "target-actions";
  const runSel = btn("▶ 선택 순차 처리", "");
  runSel.disabled = selectedKeys.size === 0;
  runSel.onclick = () => runAllWith([...selectedKeys]);
  const delSel = btn("선택 삭제", "ghost");
  delSel.disabled = selectedKeys.size === 0;
  delSel.onclick = async () => {
    if (!confirm(`선택한 ${selectedKeys.size}명을 삭제할까요?`)) return;
    for (const k of [...selectedKeys]) await api("/api/target/remove", "POST", { key: k });
    await refresh();
  };
  const clearAll = btn("전체 비우기", "ghost");
  clearAll.onclick = () => {
    if (confirm("대상자 목록을 전부 비울까요?"))
      run(() => api("/api/targets/clear", "POST"));
  };
  right.appendChild(runSel);
  right.appendChild(delSel);
  right.appendChild(clearAll);
  bar.appendChild(left);
  bar.appendChild(right);
  el.appendChild(bar);

  list.forEach((tg) => {
    const row = document.createElement("div");
    row.className = "target-row" + (tg.key === t.active ? " active" : "");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = selectedKeys.has(tg.key);
    cb.onchange = () => {
      if (cb.checked) selectedKeys.add(tg.key);
      else selectedKeys.delete(tg.key);
      renderTargetList(t);
    };

    const info = document.createElement("span");
    info.className = "mmain";
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
    row.appendChild(cb);
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

  const enabled = new Set(enabledSites || scenarios.map((s) => s.id));

  scenarios.forEach((s, i) => {
    const site = active.sites[s.id] || { status: "pending", message: "" };
    const row = document.createElement("div");
    row.className = "site" + (enabled.has(s.id) ? "" : " off");

    const isApi = s.kind === "api";
    const canOpen = !isApi && ["pending", "error", "blocked"].includes(site.status);
    const canRun = isApi
      ? ["pending", "error", "blocked"].includes(site.status)
      : ["in_progress", "awaiting", "error", "blocked"].includes(site.status);

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

    // 포함/제외 토글 (제외하면 순차 처리에서 빠짐)
    const inc = document.createElement("label");
    inc.className = "inc";
    const incCb = document.createElement("input");
    incCb.type = "checkbox";
    incCb.checked = enabled.has(s.id);
    incCb.title = "순차 처리에 포함";
    incCb.onchange = async () => {
      if (incCb.checked) enabled.add(s.id);
      else enabled.delete(s.id);
      try {
        await api("/api/sites/enabled", "POST", { ids: [...enabled] });
        await refresh();
      } catch (e) {
        alert(e.message);
      }
    };
    inc.appendChild(incCb);
    row.insertBefore(inc, row.firstChild);

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

    if (!isApi) {
      const credBtn = btn(s.has_credentials ? "🔑 저장됨" : "🔑 로그인정보", "ghost");
      credBtn.onclick = () => toggleCredForm(row, s);
      actions.appendChild(credBtn);
    }

    listEl.appendChild(row);
  });
}

function toggleCredForm(row, s) {
  const existing = row.querySelector(".cred-form");
  if (existing) {
    existing.remove();
    return;
  }
  const form = document.createElement("div");
  form.className = "cred-form";
  const user = document.createElement("input");
  user.type = "text";
  user.placeholder = "아이디";
  const pass = document.createElement("input");
  pass.type = "password";
  pass.placeholder = "비밀번호";
  const save = btn("저장", "");
  save.onclick = async () => {
    try {
      await api(`/api/site/${s.id}/credentials`, "POST", {
        username: user.value.trim(),
        password: pass.value,
      });
      form.remove();
      await refresh();
    } catch (e) {
      alert(e.message);
    }
  };
  const hint = document.createElement("span");
  hint.className = "muted";
  hint.textContent =
    "Windows 계정으로 암호화되어 이 PC에만 저장됩니다(평문 노출 없음). 아이디를 비우고 저장하면 삭제.";
  form.appendChild(user);
  form.appendChild(pass);
  form.appendChild(save);
  form.appendChild(hint);
  row.appendChild(form);
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

// 순차 처리 실행(keys 없으면 전체). run-all 버튼과 '선택 순차 처리'가 공용으로 쓴다.
async function runAllWith(keys) {
  const b = document.getElementById("runAllBtn");
  const who = keys && keys.length ? `${keys.length}명` : "전체";
  const msg =
    `${who} 대상을 순서대로 처리합니다.\n` +
    "먼저 [열기]로 브라우저를 열고 로그인해 두어야 합니다.\n계속할까요?";
  if (!confirm(msg)) return;
  await busy(b, "처리 중…", async () => {
    try {
      const r = await api("/api/run-all", "POST", keys ? { keys } : {});
      await refresh();
      if (r && r.message) alert(r.message);
    } catch (e) {
      alert(e.message);
      await refresh();
    }
  });
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

// ----- 모달 -----
function showModal(title, bodyNode) {
  document.getElementById("modalTitle").textContent = title;
  const body = document.getElementById("modalBody");
  body.innerHTML = "";
  body.appendChild(bodyNode);
  document.getElementById("modal").style.display = "flex";
}
document.getElementById("modalClose").onclick = () => {
  document.getElementById("modal").style.display = "none";
};

// 버튼을 처리 중 상태로 잠그고 실행
async function busy(btn, label, fn) {
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = label;
  try {
    return await fn();
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

document.getElementById("mailListBtn").onclick = (e) =>
  busy(e.target, "읽는 중…", async () => {
    let data;
    try {
      data = await api("/api/mail/list", "POST");
    } catch (err) {
      alert(err.message);
      return;
    }
    const rows = data.messages || [];
    const wrap = document.createElement("div");
    const summary = document.createElement("div");
    summary.className = "muted";
    summary.style.margin = "4px 6px 10px";
    const hit = rows.filter((r) => r.in_window && r.subject_match).length;
    const got = rows.filter((r) => r.parsed).length;
    summary.textContent = `받은편지함 최근 ${rows.length}건 · 조건 매칭 ${hit}건 · 추출 성공 ${got}건`;
    wrap.appendChild(summary);
    rows.forEach((r, i) => {
      const row = document.createElement("div");
      row.className = "mrow";
      let pill;
      if (r.parsed)
        pill = `<span class="pill ok">✓ ${r.parsed}</span>`;
      else if (r.in_window && r.subject_match)
        pill = `<span class="pill hit">제목매칭·추출실패</span>`;
      else if (!r.in_window)
        pill = `<span class="pill no">기간밖</span>`;
      else pill = `<span class="pill no">제목불일치</span>`;
      row.innerHTML =
        `<span class="num">${i + 1}</span>` +
        `<span class="mmain"><div class="msub">${r.subject || "(제목없음)"}</div>` +
        `<div class="mmeta">${r.sender} · ${r.received}</div></span>` +
        pill;
      wrap.appendChild(row);
    });
    if (!rows.length) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "받은편지함에서 읽은 메일이 없습니다.";
      wrap.appendChild(p);
    }
    showModal("읽은 메일 목록 (받은편지함)", wrap);
  });

document.getElementById("mailBtn").onclick = (e) =>
  busy(e.target, "메일 읽는 중…", async () => {
    let r;
    try {
      r = await api("/api/mail/import", "POST");
    } catch (err) {
      alert(err.message);
      return;
    }
    await refresh();
    // 중복(이미 목록에 있는 사람)은 한 명씩 물어본다.
    for (const d of r.duplicates || []) {
      const ok = confirm(
        `'${d.name}' (퇴사일 ${d.resign_date})은 이미 목록에 있습니다.\n` +
          `메일의 정보로 추가/갱신할까요?`
      );
      if (ok) {
        try {
          await api("/api/target", "POST", { name: d.name, resign_date: d.resign_date });
        } catch (err) {
          alert(err.message);
        }
      }
    }
    await refresh();
    if (r && r.message) alert(r.message);
  });

document.getElementById("historyBtn").onclick = toggleHistory;

document.getElementById("runAllBtn").onclick = () => runAllWith(null);

document.getElementById("testMode").onchange = (e) => {
  api("/api/testmode", "POST", { on: e.target.checked }).catch((err) =>
    alert(err.message)
  );
};

refresh().then(autoImport);
