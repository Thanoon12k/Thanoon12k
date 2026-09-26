(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  let board = { goals: [], owner: false, colors: [], textures: [] };
  let openGoal = null;       // id of the goal shown in the detail dialog
  let editing = null;        // id of goal being edited, or null for a new one
  let pick = { color: "ember" };
  let refocus = null;        // selector to focus after re-render
  let justChecked = null;

  // ---------- storage-safe theme ----------
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
  };
  const theme = store.get("goals-theme");
  if (theme) document.documentElement.dataset.theme = theme;
  else if (matchMedia("(prefers-color-scheme: light)").matches) document.documentElement.dataset.theme = "light";
  $("#themeBtn").onclick = () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    store.set("goals-theme", next);
  };

  // ---------- api ----------
  async function api(method, url, data) {
    const res = await fetch(url, {
      method,
      headers: data !== undefined || method !== "GET" ? { "Content-Type": "application/json" } : {},
      body: method === "GET" ? undefined : JSON.stringify(data ?? {}),
      credentials: "same-origin",
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.error || `Request failed (${res.status})`);
    return json;
  }
  async function act(method, url, data) {
    const before = snapshot();
    try {
      board = await api(method, url, data);
      render();
      celebrate(before);
    } catch (e) {
      toast(e.message);
      if (/log in/i.test(e.message)) { board.owner = false; render(); }
    }
  }

  // ---------- progress math ----------
  const mStats = (m) => {
    const total = m.steps.length, done = m.steps.filter((s) => s.done).length;
    return { total, done, pct: total ? Math.round((done / total) * 100) : 0, complete: total > 0 && done === total };
  };
  const gStats = (g) => {
    let total = 0, done = 0, mDone = 0;
    g.missions.forEach((m) => { const s = mStats(m); total += s.total; done += s.done; if (s.complete) mDone++; });
    return {
      total, done, mDone, missions: g.missions.length,
      pct: total ? Math.round((done / total) * 100) : 0,
      complete: g.missions.length > 0 && mDone === g.missions.length,
    };
  };
  function snapshot() {
    const snap = {};
    board.goals.forEach((g) => {
      snap["g" + g.id] = gStats(g).complete;
      g.missions.forEach((m) => { snap["m" + m.id] = mStats(m).complete; });
    });
    return snap;
  }
  function celebrate(before) {
    for (const g of board.goals) {
      if (gStats(g).complete && before["g" + g.id] === false) {
        confetti(220); toast(`📦 Box sealed: “${g.title}” achieved!`); return;
      }
    }
    for (const g of board.goals) for (const m of g.missions) {
      if (mStats(m).complete && before["m" + m.id] === false) { confetti(90); toast(`✅ Mission done: ${m.title}`); return; }
    }
  }

  function deadlineText(d) {
    if (!d) return "";
    const days = Math.ceil((new Date(d + "T23:59:59") - new Date()) / 864e5);
    if (isNaN(days)) return "";
    if (days < 0) return `${-days}d overdue`;
    if (days === 0) return "due today";
    return days > 60 ? `${Math.round(days / 30)} mo left` : `${days}d left`;
  }

  // ---------- render ----------
  function render() {
    document.body.classList.toggle("owner", board.owner);
    $("#lockBtn").textContent = board.owner ? "🔓 Log out" : "🔒 Owner";
    renderGrid();
    renderProgress();
    if (openGoal != null) renderDetail();
    if (refocus) { const el = $(refocus); if (el) el.focus(); refocus = null; }
  }

  function boxHTML(g, i) {
    const s = gStats(g);
    const due = deadlineText(g.deadline);
    const segs = g.missions.map((m) => `<i style="--m:${mStats(m).pct}"></i>`).join("") || `<i style="--m:0"></i>`;
    return `<button class="box c-${esc(g.color)}" style="--i:${i};--p:${s.pct}" data-goal="${g.id}" aria-label="${esc(g.title)}, ${s.pct}% complete">
      <div class="fill"></div>
      <div class="lid-line"></div>
      <div class="tape"></div>
      ${s.complete ? `<div class="stamp">ACHIEVED</div>` : ""}
      <div class="inner">
        <div class="head"><span class="emoji">${esc(g.emoji)}</span><span class="pct">${s.pct}<small>%</small></span></div>
        <h3 dir="auto">${esc(g.title)}</h3>
        <div class="label">
          <div class="l1"><span dir="auto">${esc(g.category || "Goal")}</span><span class="due">${esc(due)}</span></div>
          <div class="segs">${segs}</div>
          <div class="l3"><span>${s.mDone}/${s.missions} missions</span><span>${s.done}/${s.total} steps</span></div>
        </div>
      </div>
    </button>`;
  }

  function renderGrid() {
    let html = board.goals.map(boxHTML).join("");
    if (board.owner) html += `<button class="box add" data-add><div><span>＋</span>New goal box</div></button>`;
    if (!html) html = `<div class="empty">No boxes here yet.</div>`;
    $("#grid").innerHTML = html;
  }

  // ---------- progress tab ----------
  function ring(pct, size = 128, stroke = 12) {
    const r = (size - stroke) / 2, c = 2 * Math.PI * r;
    return `<svg viewBox="0 0 ${size} ${size}">
      <defs><linearGradient id="rg" x1="0" x2="1"><stop offset="0" stop-color="#ff6b3d"/><stop offset="1" stop-color="#ffc93c"/></linearGradient></defs>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="var(--line)" stroke-width="${stroke}"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="url(#rg)" stroke-width="${stroke}" stroke-linecap="round"
        stroke-dasharray="${c}" stroke-dashoffset="${c}" style="transition:stroke-dashoffset 1s cubic-bezier(.2,.8,.2,1)"/>
    </svg>`;
  }
  const fmtDate = (iso) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });

  function renderProgress() {
    let total = 0, done = 0, missions = 0, mDone = 0, gDone = 0;
    board.goals.forEach((g) => {
      const s = gStats(g); total += s.total; done += s.done; missions += s.missions; mDone += s.mDone; if (s.complete) gDone++;
    });
    const pct = total ? Math.round((done / total) * 100) : 0;
    const ringEl = $("#bigRing");
    if (!ringEl.firstChild) ringEl.innerHTML = ring(0) + `<div class="lbl"><div><b>0%</b><span>overall</span></div></div>`;
    requestAnimationFrame(() => {
      const arc = ringEl.querySelectorAll("circle")[1];
      const c = parseFloat(arc.getAttribute("stroke-dasharray"));
      arc.setAttribute("stroke-dashoffset", view === "progress" ? c * (1 - pct / 100) : c);
      ringEl.querySelector("b").textContent = pct + "%";
    });
    $("#stats").innerHTML = [
      [board.goals.length, "goal boxes"],
      [`${gDone}`, "boxes sealed"],
      [`${mDone}/${missions}`, "missions done"],
      [`${done}/${total}`, "steps checked"],
    ].map(([b, t]) => `<div class="stat"><b>${esc(b)}</b><span>${t}</span></div>`).join("");

    $("#plist").innerHTML = board.goals.map((g) => {
      const s = gStats(g), due = deadlineText(g.deadline);
      return `<button class="prow c-${esc(g.color)}" data-goal="${g.id}">
        <span class="p-emoji">${esc(g.emoji)}</span>
        <span class="p-main">
          <span class="p-top"><b dir="auto">${esc(g.title)}</b><span class="p-pct">${s.complete ? "✅ " : ""}${s.pct}%</span></span>
          <span class="p-bar"><i style="width:${s.pct}%"></i></span>
          <span class="p-meta">${s.mDone}/${s.missions} missions · ${s.done}/${s.total} steps${due ? " · " + esc(due) : ""}</span>
        </span>
      </button>`;
    }).join("") || `<div class="empty">No goals yet.</div>`;

    const wins = [];
    board.goals.forEach((g) => g.missions.forEach((m) => m.steps.forEach((st) => {
      if (st.done && st.done_at) wins.push({ st, g });
    })));
    wins.sort((a, b) => b.st.done_at.localeCompare(a.st.done_at));
    $("#wins").innerHTML = wins.length ? `<h2>Recent wins 🏆</h2><ul>${wins.slice(0, 12).map(({ st, g }) =>
      `<li><b dir="auto">${esc(st.text)}</b><span>${esc(g.emoji)} ${esc(g.title)} · ${fmtDate(st.done_at)}</span></li>`).join("")}</ul>` : "";
  }

  // ---------- tabs ----------
  let view = "boxes";
  function showView() {
    view = location.hash === "#progress" ? "progress" : "boxes";
    $("#grid").hidden = view !== "boxes";
    $("#progressView").hidden = view !== "progress";
    $$(".tab").forEach((t) => t.classList.toggle("on", t.dataset.view === view));
    renderProgress();
  }
  addEventListener("hashchange", showView);
  showView();

  const checkSvg = `<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7"/></svg>`;

  function renderDetail() {
    const g = board.goals.find((x) => x.id === openGoal);
    const dlg = $("#goalDlg");
    if (!g) { if (dlg.open) dlg.close(); openGoal = null; return; }
    const s = gStats(g);
    const owner = board.owner;
    const due = deadlineText(g.deadline);
    const idx = board.goals.indexOf(g);
    const missions = g.missions.map((m, mi) => {
      const ms = mStats(m);
      const steps = m.steps.map((st, si) => `
        <li class="step ${st.done ? "done" : ""} ${justChecked === st.id ? "just" : ""}" data-step="${st.id}">
          <button class="check" data-toggle="${st.id}" ${owner ? "" : "disabled"} aria-pressed="${st.done}" aria-label="${st.done ? "Uncheck" : "Check"}: ${esc(st.text)}">${checkSvg}</button>
          <span class="txt" dir="auto">${esc(st.text)}</span>
          ${owner ? `<span class="mini-tools">
            ${si > 0 ? `<button data-step-move="${st.id}" data-dir="-1" title="Move up">↑</button>` : ""}
            ${si < m.steps.length - 1 ? `<button data-step-move="${st.id}" data-dir="1" title="Move down">↓</button>` : ""}
            <button data-step-edit="${st.id}" title="Rename">✎</button>
            <button data-step-del="${st.id}" title="Delete">✕</button></span>` : ""}
        </li>`).join("");
      return `<section class="mission ${ms.complete ? "complete" : ""}" data-mission="${m.id}">
        <div class="m-head">
          <span class="m-num">${mi + 1}</span>
          <h3 dir="auto">${esc(m.title)}</h3>
          ${owner ? `<span class="mini-tools">
            ${mi > 0 ? `<button data-m-move="${m.id}" data-dir="-1" title="Move up">↑</button>` : ""}
            ${mi < g.missions.length - 1 ? `<button data-m-move="${m.id}" data-dir="1" title="Move down">↓</button>` : ""}
            <button data-m-edit="${m.id}" title="Rename mission">✎</button>
            <button data-m-del="${m.id}" title="Delete mission">✕</button></span>` : ""}
        </div>
        <div class="m-prog"><span class="mini" style="--p:${ms.pct}"><i></i></span>${ms.done}/${ms.total} steps</div>
        <ul class="steps">${steps}</ul>
        ${owner ? `<form class="add-row" data-add-step="${m.id}"><input id="as-${m.id}" placeholder="Add a checklist step…" maxlength="200" dir="auto"><button class="btn">Add</button></form>` : ""}
      </section>`;
    }).join("");

    dlg.className = `dlg goal-dlg c-${g.color}`;
    dlg.innerHTML = `
      <div class="gd-head c-${esc(g.color)}" style="--p:${s.pct}">
          <div class="gd-top">
          <div class="gd-title"><span class="emoji">${esc(g.emoji)}</span>
            <div><h2 dir="auto">${esc(g.title)}</h2>
            <div class="meta">${esc(g.category || "Goal")}${due ? " · " + esc(due) : ""}${g.deadline ? " · " + esc(g.deadline) : ""} · ${s.pct}% · ${s.mDone}/${s.missions} missions</div></div>
          </div>
          <button class="icon-btn" data-close aria-label="Close">✕</button>
        </div>
        ${g.why ? `<p class="gd-why" dir="auto">“${esc(g.why)}”</p>` : ""}
        <div class="gd-bar"><i></i></div>
        ${owner ? `<div class="gd-tools">
          <button class="btn" data-goal-edit>✎ Edit box</button>
          ${idx > 0 ? `<button class="btn" data-goal-move="-1">← Move earlier</button>` : ""}
          ${idx < board.goals.length - 1 ? `<button class="btn" data-goal-move="1">Move later →</button>` : ""}
          <button class="btn" data-goal-del>🗑 Delete</button></div>` : ""}
      </div>
      <div class="gd-body">
        ${missions || `<div class="no-missions">No missions yet${owner ? " — add the first one below." : "."}</div>`}
        ${owner ? `<form class="add-row new-mission" data-add-mission><input id="am" placeholder="New mission (e.g. Build the portfolio)" maxlength="160" dir="auto"><button class="btn primary">＋ Mission</button></form>` : ""}
      </div>`;
    justChecked = null;
  }

  // ---------- events: grid ----------
  const openBox = (e) => {
    const add = e.target.closest("[data-add]");
    if (add) return openEditor(null);
    const box = e.target.closest("[data-goal]");
    if (box) {
      openGoal = Number(box.dataset.goal);
      renderDetail();
      $("#goalDlg").showModal();
      $("#goalDlg .gd-body").scrollTop = 0;
    }
  };
  $("#grid").addEventListener("click", openBox);
  $("#plist").addEventListener("click", openBox);

  // ---------- events: detail ----------
  const dlg = $("#goalDlg");
  dlg.addEventListener("close", () => { openGoal = null; });
  dlg.addEventListener("click", (e) => {
    if (e.target === dlg) return dlg.close(); // backdrop
    const t = e.target.closest("button");
    if (!t) return;
    const d = t.dataset;
    if ("close" in d) return dlg.close();
    if (d.toggle) {
      const id = Number(d.toggle);
      const st = findStep(id);
      justChecked = st && !st.done ? id : null;
      return act("PATCH", `/api/steps/${id}`, { done: !(st && st.done) });
    }
    if (d.stepDel) return confirm("Delete this step?") && act("DELETE", `/api/steps/${d.stepDel}`);
    if (d.stepMove) return act("PATCH", `/api/steps/${d.stepMove}`, { move: Number(d.dir) });
    if (d.stepEdit) return inlineEdit(t.closest(".step").querySelector(".txt"), (v) => act("PATCH", `/api/steps/${d.stepEdit}`, { text: v }), 200);
    if (d.mDel) return confirm("Delete this mission and all its steps?") && act("DELETE", `/api/missions/${d.mDel}`);
    if (d.mMove) return act("PATCH", `/api/missions/${d.mMove}`, { move: Number(d.dir) });
    if (d.mEdit) return inlineEdit(t.closest(".m-head").querySelector("h3"), (v) => act("PATCH", `/api/missions/${d.mEdit}`, { title: v }), 160);
    if ("goalEdit" in d) return openEditor(openGoal);
    if (d.goalMove) return act("PATCH", `/api/goals/${openGoal}`, { move: Number(d.goalMove) });
    if ("goalDel" in d) {
      const g = board.goals.find((x) => x.id === openGoal);
      if (confirm(`Delete the whole box “${g.title}” with all missions and steps?`)) {
        const id = openGoal; dlg.close(); act("DELETE", `/api/goals/${id}`);
      }
    }
  });
  dlg.addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const input = f.querySelector("input");
    const v = input.value.trim();
    if (!v) return;
    if (f.dataset.addStep) { refocus = `#as-${f.dataset.addStep}`; act("POST", `/api/missions/${f.dataset.addStep}/steps`, { text: v }); }
    else if ("addMission" in f.dataset) { refocus = "#am"; act("POST", `/api/goals/${openGoal}/missions`, { title: v }); }
  });

  function findStep(id) {
    for (const g of board.goals) for (const m of g.missions) for (const s of m.steps) if (s.id === id) return s;
    return null;
  }

  function inlineEdit(el, save, max) {
    const old = el.textContent;
    const input = document.createElement("input");
    input.value = old; input.maxLength = max; input.dir = "auto";
    input.style.cssText = "flex:1;min-width:0;font-size:15px;padding:6px 10px;border-radius:8px;border:1px solid var(--accent);background:var(--panel)";
    el.replaceWith(input);
    input.focus(); input.select();
    let finished = false;
    const done = (commit) => {
      if (finished) return; finished = true;
      const v = input.value.trim();
      if (commit && v && v !== old) save(v); else { input.replaceWith(el); }
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); done(true); }
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); done(false); }
    });
    input.addEventListener("blur", () => done(true));
  }

  // ---------- goal editor ----------
  const editDlg = $("#editDlg"), editForm = $("#editForm");
  function swatches() {
    $("#colorPick").innerHTML = board.colors.map((c) =>
      `<button type="button" class="swatch c-${c} ${pick.color === c ? "on" : ""}" data-color="${c}" title="${c}" aria-label="Color ${c}"></button>`).join("");
  }
  function openEditor(id) {
    editing = id;
    const g = board.goals.find((x) => x.id === id);
    $("#editTitle").textContent = g ? "Edit goal box" : "New goal box";
    editForm.reset();
    ["title", "emoji", "category", "deadline", "why"].forEach((k) => { editForm.elements[k].value = g ? g[k] : ""; });
    pick = { color: g ? g.color : board.colors[Math.floor(Math.random() * board.colors.length)] };
    swatches();
    editDlg.showModal();
  }
  editDlg.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.color) { pick.color = b.dataset.color; swatches(); }
    if ("close" in b.dataset) editDlg.close();
  });
  editForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(editForm));
    Object.assign(data, pick);
    if (editing == null) {
      await act("POST", "/api/goals", data);
      const newest = board.goals.reduce((a, b) => (a && a.id > b.id ? a : b), null);
      editDlg.close();
      if (newest) { openGoal = newest.id; renderDetail(); dlg.showModal(); setTimeout(() => $("#am")?.focus(), 50); }
    } else {
      await act("PATCH", `/api/goals/${editing}`, data);
      editDlg.close();
    }
  });

  // ---------- login ----------
  const loginDlg = $("#loginDlg");
  $("#lockBtn").onclick = () => {
    if (board.owner) return act("POST", "/api/logout");
    $("#loginErr").textContent = ""; $("#loginForm").reset(); loginDlg.showModal();
  };
  loginDlg.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) loginDlg.close(); });
  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      board = await api("POST", "/api/login", { password: e.target.elements.password.value });
      loginDlg.close(); render(); toast("Unlocked — edit away ✏️");
    } catch (err) { $("#loginErr").textContent = err.message; }
  });

  // ---------- toast ----------
  let toastTimer;
  function toast(msg) {
    const t = $("#toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 2800);
  }

  // ---------- confetti ----------
  function confetti(n) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const cv = $("#confetti"), ctx = cv.getContext("2d");
    const dpr = devicePixelRatio || 1;
    cv.width = innerWidth * dpr; cv.height = innerHeight * dpr; ctx.scale(dpr, dpr);
    const colors = ["#ff6b3d", "#ffc93c", "#3ddc97", "#38bdf8", "#c084fc", "#fb7185"];
    const ps = Array.from({ length: n }, () => ({
      x: innerWidth / 2 + (Math.random() - .5) * 120, y: innerHeight * .45,
      vx: (Math.random() - .5) * 16, vy: -Math.random() * 16 - 4,
      r: Math.random() * 6 + 4, a: Math.random() * 6, va: (Math.random() - .5) * .4,
      c: colors[(Math.random() * colors.length) | 0], life: 0,
    }));
    let frame = 0;
    (function tick() {
      ctx.clearRect(0, 0, innerWidth, innerHeight);
      ps.forEach((p) => {
        p.vy += .45; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.a += p.va;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.a); ctx.fillStyle = p.c;
        ctx.fillRect(-p.r / 2, -p.r / 4, p.r, p.r / 2); ctx.restore();
      });
      if (++frame < 150) requestAnimationFrame(tick); else ctx.clearRect(0, 0, innerWidth, innerHeight);
    })();
  }

  // ---------- boot ----------
  api("GET", "/api/board").then((b) => { board = b; render(); }).catch((e) => toast(e.message));
})();
