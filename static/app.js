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

async function refresh() {
  const data = await api("/api/status");
  scenarios = data.scenarios;
  enabledSites = data.enabled_sites || scenarios.map((s) => s.id);
  renderTargetList(data.targets);
  renderChecklist(data.targets);
  const tm = document.getElementById("testMode");
  if (tm) tm.checked = !!data.test_mode;
}

// 앱 시작 후 1회: 메일에서 퇴사자 자동 불러오기
async function autoImport() {
  if (autoImportTried) return;
  autoImportTried = true;
  let r;
  try {
    r = await api("/api/mail/auto-start", "POST");
  } catch (e) {
    return; // 미설정/오류는 조용히
  }
  if (!r || !r.started) return; // 설정 안 됐거나 이미 함
  // 백그라운드 작업이 시작됐으니, 수동 때와 똑같이 진행바를 띄우고 폴링한다.
  await pollMailJob("import", { auto: true });
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
  const left = document.createElement("label");
  left.className = "muted selall";
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

  const right = document.createElement("div");
  right.className = "bulk-actions";
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

    // 체크(선택)하면 그 사람을 '처리 중'으로 만들어 아래 체크리스트가 바뀐다.
    async function toggleRow(on) {
      if (on) {
        selectedKeys.add(tg.key);
        try {
          await api("/api/target/active", "POST", { key: tg.key });
        } catch (e) {
          /* 무시 */
        }
        await refresh();
      } else {
        selectedKeys.delete(tg.key);
        renderTargetList(t);
      }
    }
    cb.onchange = () => toggleRow(cb.checked);

    // 행(바) 아무 곳이나 클릭해도 체크가 토글되도록(버튼/체크박스 클릭은 제외)
    row.onclick = (e) => {
      if (e.target.closest("button") || e.target === cb) return;
      toggleRow(!selectedKeys.has(tg.key));
    };

    const info = document.createElement("span");
    info.className = "mmain";
    info.innerHTML =
      `<b>${tg.name}</b> <span class="muted">${tg.resign_date || ""}</span>` +
      ` &nbsp;<span class="tag">${progressText(tg.sites || {})}</span>`;

    const actions = document.createElement("span");
    actions.className = "target-actions";

    const resetBtn = btn("초기화", "ghost");
    resetBtn.title = "이 사람의 진행 기록을 대기 상태로 되돌립니다";
    resetBtn.onclick = () => run(() => api("/api/target/reset", "POST", { key: tg.key }));

    const delBtn = btn("삭제", "ghost");
    delBtn.onclick = () => {
      if (confirm(`'${tg.name}' 을(를) 목록에서 삭제할까요?`))
        run(() => api("/api/target/remove", "POST", { key: tg.key }));
    };

    actions.appendChild(resetBtn);
    actions.appendChild(delBtn);
    row.appendChild(cb);
    row.appendChild(info);
    row.appendChild(actions);
    el.appendChild(row);
  });
}

// 대상자가 없을 때 '대상 시스템' 패널이 휑하지 않게 미리보기(데모) 4건을 보여준다.
function renderChecklistPreview(listEl) {
  listEl.innerHTML = "";
  // 실제 등록된 사이트를 우선 보여주고, 4건이 안 되면 데모로 채운다.
  const demo = [
    { name: "더존 그룹웨어", kind: "browser" },
    { name: "Accio", kind: "browser" },
    { name: "VPN", kind: "browser" },
    { name: "M365 (직접 처리)", kind: "api" },
    { name: "업무 사이트", kind: "browser" },
  ];
  const rows = (scenarios && scenarios.length ? scenarios.slice() : []).map((s) => ({
    name: s.name,
    kind: s.kind,
  }));
  for (const d of demo) {
    if (rows.length >= 4) break;
    if (!rows.some((r) => r.name === d.name)) rows.push(d);
  }
  rows.slice(0, 4).forEach((s, i) => {
    const row = document.createElement("div");
    row.className = "site demo";
    row.innerHTML = `
      <div class="idx">${i + 1}</div>
      <div class="body">
        <div class="title">${s.name}
          <span class="tag">${s.kind === "api" ? "API" : "브라우저"}</span>
          <span class="badge pending">미리보기</span>
        </div>
        <div class="msg">대상자를 선택하면 [열기]·[자동 처리]·[완료]가 여기 표시돼요.</div>
      </div>`;
    listEl.appendChild(row);
  });
}

// ----- 활성 대상자의 사이트 체크리스트 -----
function renderChecklist(t) {
  const titleEl = document.getElementById("activeTitle");
  const listEl = document.getElementById("checklist");
  const active = (t.targets || []).find((x) => x.key === t.active);

  if (!active) {
    titleEl.textContent = "대상자를 선택하면 여기서 처리해요. (아래는 미리보기)";
    renderChecklistPreview(listEl);
    return;
  }
  titleEl.textContent = `처리 중: ${active.name} · 퇴사일 ${active.resign_date}`;
  listEl.innerHTML = "";

  const enabled = new Set(enabledSites || scenarios.map((s) => s.id));

  // 사이트 전체 선택/해제 바
  const sbar = document.createElement("div");
  sbar.className = "bulk-bar";
  const sleft = document.createElement("label");
  sleft.className = "muted selall";
  const sAll = document.createElement("input");
  sAll.type = "checkbox";
  sAll.checked = scenarios.length > 0 && scenarios.every((s) => enabled.has(s.id));
  sAll.onchange = async () => {
    const ids = sAll.checked ? scenarios.map((s) => s.id) : [];
    try {
      await api("/api/sites/enabled", "POST", { ids });
      await refresh();
    } catch (e) {
      alert(e.message);
    }
  };
  sleft.appendChild(sAll);
  sleft.appendChild(
    document.createTextNode(` 사이트 전체 선택 (${enabled.size}/${scenarios.length}개 포함)`)
  );
  sbar.appendChild(sleft);
  listEl.appendChild(sbar);

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
      if (r && r.message) notice("순차 처리 결과", r.message);
    } catch (e) {
      await refresh();
      notice("순차 처리 오류", e.message);
    }
  });
}

// ----- 수동추가 모달 -----
function openManual() {
  document.getElementById("manualModal").style.display = "flex";
  document.getElementById("name").focus();
}
function closeManual() {
  document.getElementById("manualModal").style.display = "none";
}
document.getElementById("manualAddBtn").onclick = openManual;
document.getElementById("manualClose").onclick = closeManual;

// ----- 입력 핸들러 -----
document.getElementById("addBtn").onclick = async () => {
  const name = document.getElementById("name").value.trim();
  const resign_date = document.getElementById("resign_date").value.trim();
  try {
    await api("/api/target", "POST", { name, resign_date });
    document.getElementById("name").value = "";
    document.getElementById("resign_date").value = "";
    closeManual();
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
    closeManual();
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

// ----- 알림 모달(알림창 대신) -----
function notice(title, text) {
  const n = document.createElement("div");
  n.className = "notice-body";
  n.textContent = text || "";
  showModal(title, n);
}

// ----- 읽은 메일 목록 노드 만들기 -----
function buildMailListNode(rows) {
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
    if (r.parsed) pill = `<span class="pill ok">✓ ${r.parsed}</span>`;
    else if (r.in_window && r.subject_match)
      pill = `<span class="pill hit">제목매칭·추출실패</span>`;
    else if (!r.in_window) pill = `<span class="pill no">기간밖</span>`;
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
  return wrap;
}

// ----- 중복 사용자 한 번에 확인하는 모달 -----
function showDuplicatesModal(dups, message) {
  const wrap = document.createElement("div");
  const info = document.createElement("p");
  info.className = "muted";
  info.style.margin = "4px 6px 10px";
  info.textContent =
    `아래 ${dups.length}명은 이미 목록에 있습니다. ` +
    "메일 정보로 추가/갱신할 사람을 선택한 뒤 [선택 적용]을 누르세요.";
  wrap.appendChild(info);

  const boxes = [];
  dups.forEach((d) => {
    const row = document.createElement("label");
    row.className = "mrow";
    row.style.cursor = "pointer";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = true;
    cb.style.width = "auto";
    boxes.push({ cb, d });
    const main = document.createElement("span");
    main.className = "mmain";
    main.innerHTML =
      `<div class="msub">${d.name} <span class="muted">${d.resign_date || ""}</span></div>` +
      `<div class="mmeta">${d.subject || ""}</div>`;
    row.appendChild(cb);
    row.appendChild(main);
    wrap.appendChild(row);
  });

  const bar = document.createElement("div");
  bar.className = "bulk-bar";
  bar.style.marginTop = "12px";
  const left = document.createElement("span");
  left.className = "muted";
  const right = document.createElement("div");
  right.className = "bulk-actions";
  const apply = btn("선택 적용", "");
  apply.onclick = async () => {
    const chosen = boxes.filter((b) => b.cb.checked);
    for (const b of chosen) {
      try {
        await api("/api/target", "POST", {
          name: b.d.name,
          resign_date: b.d.resign_date,
        });
      } catch (e) {
        /* 개별 실패는 건너뜀 */
      }
    }
    await refresh();
    notice("중복 확인", `${chosen.length}명을 추가/갱신했습니다.`);
  };
  const close = btn("닫기", "ghost");
  close.onclick = () => {
    document.getElementById("modal").style.display = "none";
  };
  right.appendChild(apply);
  right.appendChild(close);
  bar.appendChild(left);
  bar.appendChild(right);
  wrap.appendChild(bar);

  showModal(`중복 확인 (${dups.length}명)`, wrap);
}

// ----- 진행상황 바 노드 -----
function buildProgress(labelText) {
  const w = document.createElement("div");
  w.style.padding = "14px 6px";
  const lab = document.createElement("div");
  lab.className = "muted";
  lab.textContent = labelText;
  lab.style.marginBottom = "10px";
  const barWrap = document.createElement("div");
  barWrap.className = "progress";
  const bar = document.createElement("div");
  bar.className = "progress-fill";
  barWrap.appendChild(bar);
  const pctLab = document.createElement("div");
  pctLab.className = "muted";
  pctLab.style.marginTop = "8px";
  pctLab.textContent = "0%";
  w.appendChild(lab);
  w.appendChild(barWrap);
  w.appendChild(pctLab);
  return { node: w, bar, pctLab, lab };
}

// ----- 메일 읽기(백그라운드) + 진행상황 폴링 -----
let mailPollTimer = null;

function closeMainModal() {
  document.getElementById("modal").style.display = "none";
}

// 진행바 모달을 띄우고 /api/mail/progress 를 폴링한다. (작업은 이미 시작돼 있어야 함)
async function pollMailJob(kind, opts) {
  opts = opts || {};
  if (mailPollTimer) {
    clearTimeout(mailPollTimer);
    mailPollTimer = null;
  }
  const title = kind === "list" ? "읽은 메일 불러오는 중…" : "메일에서 퇴사자 찾는 중…";
  const p = buildProgress("받은편지함을 읽는 중입니다…");
  showModal(title, p.node);

  const tick = async () => {
    let s;
    try {
      s = await api("/api/mail/progress");
    } catch (e) {
      p.lab.textContent = "진행상황 확인 실패: " + e.message;
      return;
    }
    const pct = s.percent || 0;
    p.bar.style.width = pct + "%";
    p.pctLab.textContent = pct + "%" + (s.fetched ? ` · ${s.fetched}건 읽음` : "");
    if (!s.running && s.error) {
      if (opts.auto) closeMainModal();
      else notice("메일 읽기 오류", s.error);
      return;
    }
    if (!s.running && s.result !== null) {
      p.bar.style.width = "100%";
      p.pctLab.textContent = "100% · 완료";
      await finishMailJob(kind, s.result, opts);
      return;
    }
    mailPollTimer = setTimeout(tick, 400);
  };
  tick();
}

async function runMailJob(kind) {
  try {
    await api("/api/mail/start", "POST", { kind });
  } catch (e) {
    notice("메일 읽기", e.message);
    return;
  }
  await pollMailJob(kind, {});
}

async function finishMailJob(kind, result, opts) {
  opts = opts || {};
  if (kind === "list") {
    showModal("읽은 메일 목록 (받은편지함)", buildMailListNode(result.messages || []));
    return;
  }
  // import
  await refresh();
  const dups = result.duplicates || [];
  const added = result.added || [];
  if (dups.length) {
    showDuplicatesModal(dups, result.message);
    return;
  }
  // 자동 불러오기인데 새로 등록된 게 없으면 조용히 닫는다(방해 X).
  if (opts.auto && added.length === 0) {
    closeMainModal();
    return;
  }
  notice(
    opts.auto ? "🔔 메일에서 자동으로 불러왔습니다" : "메일에서 퇴사자 가져오기",
    result.message || "새로 등록된 퇴사자가 없습니다."
  );
}

document.getElementById("mailListBtn").onclick = () => runMailJob("list");
document.getElementById("mailBtn").onclick = () => runMailJob("import");

document.getElementById("historyBtn").onclick = toggleHistory;

document.getElementById("runAllBtn").onclick = () => runAllWith(null);

document.getElementById("testMode").onchange = (e) => {
  api("/api/testmode", "POST", { on: e.target.checked }).catch((err) =>
    alert(err.message)
  );
};

refresh().then(autoImport);
