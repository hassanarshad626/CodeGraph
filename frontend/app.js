const COLORS = {
  file: "#ff6b8a",
  function: "#ffb347",
  class: "#ff5566",
  import: "#7be37b",
  module: "#7bd3ea",
};

let cy = null;
let lastGraphHash = "";
let currentLayout = "cose";
let visibleKinds = new Set(["file", "class", "function", "import"]);
let lastGraph = { nodes: [], edges: [] };
let activity = {};              // rel_path -> iso ts
let activityTick = 0;           // counter to force heatmap refresh
window.HEATMAP_WINDOW_MS = 5 * 60 * 1000;  // default; overwritten by settings

// --- animation state ---
let bobEnabled = true;
let bobRafId = null;
let bobStart = 0;
let pulseRafId = null;
let dashRafId = null;
let hoveredNode = null;

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

function layoutOpts(name) {
  const base = { animate: true, animationDuration: 400, fit: true, padding: 40 };
  if (name === "cose") {
    return {
      name: "cose", animate: false, fit: true, padding: 60,
      nodeRepulsion: () => 2000000,
      idealEdgeLength: () => 160,
      edgeElasticity: () => 80,
      gravity: 0.15,
      numIter: 2000,
      nodeDimensionsIncludeLabels: true,
      componentSpacing: 120,
    };
  }
  if (name === "concentric") {
    return {
      ...base, name: "concentric",
      concentric: (n) => {
        const k = n.data("kind");
        return k === "file" ? 3 : k === "class" ? 2 : k === "function" ? 1 : 0;
      },
      levelWidth: () => 1, minNodeSpacing: 24,
    };
  }
  if (name === "breadthfirst") {
    return {
      ...base, name: "breadthfirst",
      directed: true,
      circle: true,
      spacingFactor: 2.2,
      avoidOverlap: true,
      nodeDimensionsIncludeLabels: true,
      roots: cy && cy.nodes("[kind = 'file']").length
        ? cy.nodes("[kind = 'file']").map((n) => n.id())
        : undefined,
    };
  }
  if (name === "circle") return { ...base, name: "circle", spacingFactor: 1.8,
    avoidOverlap: true, nodeDimensionsIncludeLabels: true };
  if (name === "grid") return { ...base, name: "grid", spacingFactor: 1.5,
    avoidOverlap: true, nodeDimensionsIncludeLabels: true };
  return base;
}

function initCy() {
  cy = cytoscape({
    container: $("cy"),
    wheelSensitivity: 0.5,
    minZoom: 0.05, maxZoom: 6,
    boxSelectionEnabled: false,
    autoungrabify: false,
    style: [
      {
        selector: "node",
        style: {
          "background-color": (e) => COLORS[e.data("kind")] || "#888",
          label: "data(label)",
          color: "#f2f4fa",
          "font-size": 14,
          "font-weight": 600,
          "text-valign": "bottom",
          "text-halign": "center",
          "text-margin-y": 4,
          "text-outline-color": "#0f1117",
          "text-outline-width": 3,
          "text-wrap": "ellipsis",
          "text-max-width": "140px",
          width: 50, height: 50,
          "border-width": 1,
          "border-color": "rgba(255,255,255,0.2)",
          "overlay-padding": 8,
        },
      },
      {
        selector: "node[kind = 'file']",
        style: {
          width: 80, height: 80, "font-size": 16, "font-weight": 800,
          "border-width": 3, "border-color": "rgba(255,255,255,0.45)",
          "text-valign": "center",
          "text-margin-y": 0,
          "text-outline-width": 4,
        },
      },
      {
        selector: "node[kind = 'class']",
        style: { width: 64, height: 64, "font-size": 15, "font-weight": 700,
                 "text-valign": "center", "text-margin-y": 0 },
      },
      {
        selector: "node[kind = 'import']",
        style: { width: 40, height: 40, "font-size": 12 },
      },
      {
        selector: "edge",
        style: {
          width: 1.8,
          "line-color": "rgba(180,190,210,0.3)",
          "curve-style": "bezier",
          "target-arrow-shape": "triangle",
          "target-arrow-color": "rgba(180,190,210,0.5)",
          "arrow-scale": 0.8,
        },
      },
      { selector: "edge[kind = 'imports']", style: {
          "line-style": "dashed",
          "line-color": "rgba(123,227,123,0.45)",
          "line-dash-pattern": [6, 4],
          "line-dash-offset": 0,
      } },
      {
        selector: "node.hot",
        style: {
          "border-color": "#ffd27a",
          "border-width": 4,
          "overlay-color": "#ffd27a",
          "overlay-padding": 10,
        },
      },
      {
        selector: "node.hover",
        style: {
          "border-color": "#7bd3ea",
          "border-width": 4,
          "overlay-color": "#7bd3ea",
          "overlay-opacity": 0.25,
          "overlay-padding": 12,
          "z-compound-depth": "top",
        },
      },
      { selector: ".dim", style: { opacity: 0.12 } },
      { selector: ".highlight", style: { "border-width": 3, "border-color": "#7bd3ea",
         "text-outline-color": "#1a2230", "z-compound-depth": "top" } },
      { selector: "edge.highlight", style: { width: 2.4, "line-color": "#7bd3ea",
         "target-arrow-color": "#7bd3ea", opacity: 1 } },
      { selector: "node.hidden-kind", style: { display: "none" } },
      { selector: "node:selected", style: { "border-width": 3, "border-color": "#ffb347" } },
    ],
    layout: layoutOpts("cose"),
    elements: [],
  });

  cy.on("dblclick", "node", (e) => openInEditor(e.target));
  cy.on("mouseover", "node", (e) => {
    showTooltip(e.target, e.renderedPosition);
    hoverHighlight(e.target);
  });
  cy.on("mousemove", (e) => {
    const tt = $("tooltip");
    if (!tt.classList.contains("hidden")) {
      tt.style.left = (e.renderedPosition.x + 14) + "px";
      tt.style.top = (e.renderedPosition.y + 14) + "px";
    }
  });
  cy.on("mouseout", "node", () => {
    $("tooltip").classList.add("hidden");
    hoverClear();
  });
  cy.on("tap", "node", (e) => selectNode(e.target));
  cy.on("tap", (e) => { if (e.target === cy) clearSelection(); });

  // Re-capture base positions whenever the layout finishes or user drags a node.
  cy.on("layoutstop", captureBasePositions);
  cy.on("dragfree", "node", (e) => {
    const p = e.target.position();
    e.target.scratch("_base", { x: p.x, y: p.y, phase: Math.random() * Math.PI * 2 });
  });
}

function hoverHighlight(node) {
  if (hoveredNode === node) return;
  hoveredNode = node;
  // Don't disturb a click-selection
  if ($("nodeInfo") && !$("nodeInfo").classList.contains("hidden")) return;
  cy.batch(() => {
    cy.elements().addClass("dim");
    const nh = node.closedNeighborhood();
    nh.removeClass("dim");
    node.addClass("hover");
  });
}

function hoverClear() {
  hoveredNode = null;
  if ($("nodeInfo") && !$("nodeInfo").classList.contains("hidden")) return;
  cy.batch(() => {
    cy.elements().removeClass("dim");
    cy.nodes().removeClass("hover");
  });
}

function captureBasePositions() {
  cy.nodes().forEach((n) => {
    const p = n.position();
    n.scratch("_base", { x: p.x, y: p.y, phase: Math.random() * Math.PI * 2 });
  });
}

function startBobbing() {
  cancelAnimationFrame(bobRafId);
  bobStart = performance.now();
  let last = 0;
  const TARGET_FPS = 30;
  const FRAME_MS = 1000 / TARGET_FPS;

  function frame(now) {
    if (!bobEnabled) { bobRafId = null; return; }
    if (now - last >= FRAME_MS) {
      last = now;
      const t = (now - bobStart) / 1000;
      cy.nodes().positions((n) => {
        const b = n.scratch("_base");
        if (!b || n.grabbed()) return n.position();
        const amp = n.data("kind") === "file" ? 1.2 : 1.8;
        return {
          x: b.x + Math.sin(t * 0.9 + b.phase) * amp,
          y: b.y + Math.cos(t * 1.1 + b.phase) * amp,
        };
      });
    }
    bobRafId = requestAnimationFrame(frame);
  }
  bobRafId = requestAnimationFrame(frame);
}

function stopBobbing() {
  cancelAnimationFrame(bobRafId);
  bobRafId = null;
  // restore base positions
  cy.nodes().positions((n) => {
    const b = n.scratch("_base");
    return b ? { x: b.x, y: b.y } : n.position();
  });
}

function startPulse() {
  cancelAnimationFrame(pulseRafId);
  const start = performance.now();
  function frame(now) {
    const t = (now - start) / 600;
    const opacity = 0.25 + 0.25 * (1 + Math.sin(t)) / 2;  // 0.25 .. 0.50
    cy.nodes(".hot").style("overlay-opacity", opacity);
    pulseRafId = requestAnimationFrame(frame);
  }
  pulseRafId = requestAnimationFrame(frame);
}

function startDashFlow() {
  cancelAnimationFrame(dashRafId);
  let offset = 0;
  function frame() {
    offset = (offset + 0.4) % 100;
    cy.edges("[kind = 'imports']").style("line-dash-offset", -offset);
    dashRafId = requestAnimationFrame(frame);
  }
  dashRafId = requestAnimationFrame(frame);
}

function showTooltip(node, pos) {
  const tt = $("tooltip");
  const d = node.data();
  tt.innerHTML = `
    <div class="tt-kind">${d.kind}</div>
    <div class="tt-name">${escapeHtml(d.fullName || d.label)}</div>
    ${d.path ? `<div class="tt-path">${escapeHtml(d.path)}${d.line ? ":" + d.line : ""}</div>` : ""}
  `;
  tt.style.left = (pos.x + 14) + "px";
  tt.style.top = (pos.y + 14) + "px";
  tt.classList.remove("hidden");
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

async function openInEditor(node) {
  const d = node.data();
  if (!d.path) return;
  try {
    await api("/api/open", {
      method: "POST",
      body: JSON.stringify({ path: d.path, line: d.line || 1 }),
    });
  } catch (e) {
    alert(`Open failed: ${e.message || e}`);
  }
}

function applyHeatmap() {
  if (!cy) return;
  const now = Date.now();
  cy.batch(() => {
    cy.nodes().forEach((n) => {
      const d = n.data();
      if (d.kind !== "file") { n.removeClass("hot"); return; }
      const ts = activity[d.path];
      if (!ts) { n.removeClass("hot"); return; }
      const t = Date.parse(ts.replace(" ", "T"));
      const age = now - t;
      if (age >= 0 && age < window.HEATMAP_WINDOW_MS) n.addClass("hot");
      else n.removeClass("hot");
    });
  });
}

function selectNode(node) {
  cy.elements().addClass("dim").removeClass("highlight");
  const nhood = node.closedNeighborhood();
  nhood.removeClass("dim").addClass("highlight");

  const d = node.data();
  const incoming = node.incomers("edge").map((e) => e.source().data());
  const outgoing = node.outgoers("edge").map((e) => e.target().data());

  $("niKind").textContent = d.kind;
  $("niName").textContent = d.fullName || d.label;
  const pathEl = $("niPath");
  pathEl.innerHTML = "";
  if (d.path) {
    const loc = document.createElement("span");
    loc.textContent = `${d.path}${d.line ? ":" + d.line : ""}`;
    pathEl.appendChild(loc);
    const openBtn = document.createElement("button");
    openBtn.id = "niOpen";
    openBtn.textContent = "Open in editor ↗";
    openBtn.onclick = () => openInEditor(node);
    pathEl.appendChild(openBtn);
  }
  const mkList = (arr, label) => arr.length
    ? `<div><b>${label} (${arr.length}):</b></div>` +
      arr.slice(0, 30).map((x) =>
        `<div class="ni-item" data-id="${escapeHtml(x.id)}">• ${escapeHtml(x.fullName || x.label || x.name)} <span style="opacity:0.5">(${x.kind})</span></div>`
      ).join("")
    : "";
  $("niNeighbors").innerHTML = mkList(incoming, "Referenced by") + mkList(outgoing, "References");
  $("niNeighbors").querySelectorAll(".ni-item").forEach((el) => {
    el.onclick = () => {
      const n = cy.getElementById(el.dataset.id);
      if (n && n.length) { selectNode(n); cy.animate({ center: { eles: n }, zoom: 1.2 }, { duration: 300 }); }
    };
  });
  $("nodeInfo").classList.remove("hidden");
}

function clearSelection() {
  cy.elements().removeClass("dim").removeClass("highlight");
  $("nodeInfo").classList.add("hidden");
}

function shortLabel(name, kind) {
  if (!name) return "";
  if (kind === "file") {
    const base = name.split(/[\\/]/).pop();
    return base.length > 28 ? base.slice(0, 26) + "…" : base;
  }
  return name.length > 24 ? name.slice(0, 22) + "…" : name;
}

function applyKindFilter() {
  if (!cy) return;
  cy.batch(() => {
    cy.nodes().forEach((n) => {
      const k = n.data("kind");
      if (visibleKinds.has(k)) n.removeClass("hidden-kind");
      else n.addClass("hidden-kind");
    });
  });
}

function runLayout() {
  if (!cy) return;
  const layout = cy.layout(layoutOpts(currentLayout));
  layout.one("layoutstop", () => {
    // Always fit after layout finishes, regardless of layout mode.
    cy.animate({ fit: { padding: 50 } }, { duration: 250 });
  });
  layout.run();
}

async function refreshGraph(forceRelayout = false) {
  if (!cy) initCy();
  const g = await api("/api/graph");
  const hash = `${g.nodes.length}:${g.edges.length}:${g.nodes.map((n) => n.id).join("|").length}`;
  if (!forceRelayout && hash === lastGraphHash) return;
  lastGraphHash = hash;
  lastGraph = g;

  const elems = [
    ...g.nodes.map((n) => ({
      data: {
        id: n.id,
        label: shortLabel(n.name, n.kind),
        fullName: n.name,
        kind: n.kind,
        path: n.path,
        line: n.line,
      },
    })),
    ...g.edges.map((e, i) => ({
      data: { id: `e${i}`, source: e.src, target: e.dst, kind: e.kind },
    })),
  ];
  cy.elements().remove();
  cy.add(elems);
  applyKindFilter();
  runLayout();
}

async function refreshChanges() {
  const list = await api("/api/changes?limit=30");
  $("changes").innerHTML = list
    .map((c) => `<li><b>${c.kind[0].toUpperCase()}</b> ${c.path}<br><span style="color:#555">${c.ts}</span></li>`)
    .join("");
}

async function refreshStats() {
  const s = await api("/api/stats");
  const k = s.by_kind || {};
  $("stats").innerHTML = `
    <div><b>${s.total || 0}</b> nodes</div>
    <div>Files: <b>${k.file || 0}</b></div>
    <div>Classes: <b>${k.class || 0}</b></div>
    <div>Functions: <b>${k.function || 0}</b></div>
    <div>Imports: <b>${k.import || 0}</b></div>
  `;
}

async function refreshContext() {
  const md = await api("/api/context");
  $("contextBody").innerHTML = window.marked ? marked.parse(md || "_no context yet_") : md;
}

async function refreshStatus() {
  const s = await api("/api/status");
  $("status").textContent = s.active ? `viewing: ${s.active}  (${s.projects.length} watched)` : "no folder watched";
  updateEmptyHint(!!s.active);
  const ul = $("projects");
  ul.innerHTML = (s.projects || [])
    .map((p) => {
      const act = p.path === s.active ? "active" : "";
      return `<li class="${act}" data-path="${p.path}">
          <span class="proj-name">${p.name}</span>
          <span class="proj-path">${p.path}</span>
          <button class="stop" data-path="${p.path}">✕</button>
        </li>`;
    })
    .join("");
  ul.querySelectorAll("li").forEach((li) => {
    li.addEventListener("click", async (e) => {
      if (e.target.classList.contains("stop")) return;
      await api("/api/select", { method: "POST", body: JSON.stringify({ path: li.dataset.path }) });
      lastGraphHash = "";
      await tick();
      await refreshStatus();
    });
  });
  ul.querySelectorAll("button.stop").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await api("/api/unwatch", { method: "POST", body: JSON.stringify({ path: btn.dataset.path }) });
      lastGraphHash = "";
      await refreshStatus();
      await tick();
    });
  });
}

async function doWatch() {
  const path = $("folderInput").value.trim();
  if (!path) return;
  $("status").textContent = "starting…";
  try {
    await api("/api/watch", { method: "POST", body: JSON.stringify({ path }) });
    $("folderInput").value = "";
    lastGraphHash = "";
    await Promise.all([refreshStatus(), refreshGraph(true), refreshChanges(), refreshStats(), refreshContext()]);
  } catch (e) {
    $("status").textContent = `error: ${e.message}`;
  }
}

async function doPick() {
  if (!window.electronAPI || !window.electronAPI.pickFolder) {
    const inElectron = navigator.userAgent.toLowerCase().includes("electron");
    alert(inElectron
      ? "Running in Electron, but preload bridge didn't load. Open DevTools (Ctrl+Shift+I) → Console for the error."
      : "Folder picker only available in the Electron app. Paste a path instead.");
    return;
  }
  try {
    const p = await window.electronAPI.pickFolder();
    if (p) {
      $("folderInput").value = p;
      await doWatch();
    }
  } catch (e) {
    alert(`Pick folder failed: ${e.message || e}`);
  }
}

// ---------- onboarding / handoff ----------
function openModal(id) { $(id).classList.remove("hidden"); }
function closeModal(id) { $(id).classList.add("hidden"); }

function updateEmptyHint(hasActive) {
  const el = $("emptyHint");
  if (!el) return;
  if (hasActive) el.classList.add("hidden");
  else el.classList.remove("hidden");
}

function buildHandoffPrompt(status, changes, contextMd, note) {
  const name = status.active ? status.active.split(/[\\/]/).pop() : "this project";
  const path = status.active || "";
  const lines = [];
  lines.push(`Hi! I'm continuing work on **${name}** that was started with another AI assistant.`);
  lines.push("");
  lines.push(`Please read the context below carefully before making any changes. The project lives at:`);
  lines.push(`  \`${path}\``);
  lines.push("");
  lines.push(`A live, auto-updated summary is in \`${path}\\CONTEXT.md\` (also mirrored into \`CLAUDE.md\` and \`AGENTS.md\`) — but here is the current snapshot inline so you have everything you need:`);
  lines.push("");
  lines.push("---");
  lines.push("");
  lines.push(contextMd || "_(no context available yet)_");
  lines.push("");
  lines.push("---");
  lines.push("");
  if (note && note.trim()) {
    lines.push(`## What I was working on`);
    lines.push("");
    lines.push(note.trim());
    lines.push("");
  }
  if (changes && changes.length) {
    lines.push(`## Most recent file changes`);
    lines.push("");
    changes.slice(0, 10).forEach((c) => {
      lines.push(`- \`${c.ts}\`  ${c.kind}  ${c.path}`);
    });
    lines.push("");
  }
  lines.push(`## Please do next`);
  lines.push("");
  lines.push(`1. Confirm you understand the project layout by summarizing it back in 2-3 sentences.`);
  lines.push(`2. Ask me any clarifying questions before writing code.`);
  lines.push(`3. Then continue the work described above.`);
  lines.push("");
  lines.push(`Note: CodeGraph is running on my machine and will keep \`CONTEXT.md\` updated as you edit files — re-read it any time you need fresh state.`);
  return lines.join("\n");
}

function buildSuggestions(status, changes, contextMd) {
  const tips = [];
  const ctx = contextMd || "";
  // Parse uncommitted count from the git section.
  const m = ctx.match(/\*\*Uncommitted \((\d+)\)/);
  if (m) tips.push(`You have <b>${m[1]} uncommitted file${m[1] === "1" ? "" : "s"}</b>. Consider asking the new AI to review and commit them first.`);
  else if (/Working tree:\*\*\s*clean/.test(ctx)) tips.push(`Your working tree is clean — a good moment to hand off.`);
  if (/Upstream:\*\*.*behind/.test(ctx)) tips.push(`You're behind your upstream branch — the new AI might want to pull/rebase before editing.`);
  if (!changes || !changes.length) tips.push(`No file changes have been logged yet. The new AI will rely on your note above — describe what you want it to do.`);
  else tips.push(`${changes.length} file change${changes.length === 1 ? "" : "s"} are tracked; the new AI will see them in the prompt.`);
  if (!/Git/.test(ctx)) tips.push(`This folder isn't a git repo — consider <code>git init</code> so your work is safe across handoffs.`);
  if (!tips.length) return "";
  return `<b>Tips for a smooth handoff:</b><ul>${tips.map((t) => `<li>${t}</li>`).join("")}</ul>`;
}

async function openSettings() {
  try {
    const s = await api("/api/settings");
    $("setEditor").value = s.editor_command || "";
    $("setIgnore").value = Array.isArray(s.extra_ignore_dirs)
      ? s.extra_ignore_dirs.join(", ") : (s.extra_ignore_dirs || "");
    $("setHeatmap").value = s.heatmap_minutes || 5;
    $("setAutostart").checked = !!s.autostart;
    $("setBobbing").checked = s.enable_bobbing !== false;
    openModal("settings");
  } catch (e) {
    alert(`Could not load settings: ${e.message || e}`);
  }
}

async function saveSettings() {
  const patch = {
    editor_command: $("setEditor").value.trim(),
    extra_ignore_dirs: $("setIgnore").value
      .split(",").map((x) => x.trim()).filter(Boolean),
    heatmap_minutes: Math.max(1, Math.min(60, parseInt($("setHeatmap").value, 10) || 5)),
    autostart: $("setAutostart").checked,
    enable_bobbing: $("setBobbing").checked,
  };
  try {
    const s = await api("/api/settings", { method: "POST", body: JSON.stringify(patch) });
    // Apply immediately in the UI.
    window.HEATMAP_WINDOW_MS = (s.heatmap_minutes || 5) * 60 * 1000;
    bobEnabled = !!s.enable_bobbing;
    $("bobBtn").classList.toggle("active", bobEnabled);
    if (bobEnabled) startBobbing(); else stopBobbing();
    if (window.electronAPI && window.electronAPI.setAutostart) {
      try { await window.electronAPI.setAutostart(s.autostart); } catch {}
    }
    applyHeatmap();
    closeModal("settings");
  } catch (e) {
    alert(`Save failed: ${e.message || e}`);
  }
}

async function openHandoff() {
  try {
    const [status, changes, contextMd] = await Promise.all([
      api("/api/status"), api("/api/changes?limit=15"), api("/api/context"),
    ]);
    if (!status.active) {
      alert("Pick a folder first — there's nothing to hand off yet.");
      return;
    }
    const regen = () => {
      const note = $("handoffNote").value;
      $("handoffPrompt").value = buildHandoffPrompt(status, changes, contextMd, note);
    };
    $("handoffNote").oninput = regen;
    regen();
    $("handoffSuggestions").innerHTML = buildSuggestions(status, changes, contextMd);
    openModal("handoff");
  } catch (e) {
    alert(`Could not build handoff: ${e.message || e}`);
  }
}

function bindModals() {
  document.querySelectorAll("[data-close]").forEach((b) => {
    b.onclick = () => closeModal(b.dataset.close);
  });
  document.querySelectorAll(".modal").forEach((m) => {
    m.addEventListener("click", (e) => { if (e.target === m) m.classList.add("hidden"); });
  });
  $("helpBtn").onclick = () => openModal("onboarding");
  $("settingsBtn").onclick = openSettings;
  $("saveSettings").onclick = saveSettings;
  $("handoffBtn").onclick = openHandoff;
  $("emptyHintPick").onclick = doPick;
  $("emptyHintHelp").onclick = () => openModal("onboarding");
  $("copyHandoff").onclick = async () => {
    await navigator.clipboard.writeText($("handoffPrompt").value);
    $("copyHandoff").textContent = "Copied ✓";
    setTimeout(() => ($("copyHandoff").textContent = "Copy prompt"), 1400);
  };
  // Show onboarding on first run.
  if (!localStorage.getItem("codegraph_seen_intro")) {
    openModal("onboarding");
    localStorage.setItem("codegraph_seen_intro", "1");
  }
  // Escape closes any open modal.
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") document.querySelectorAll(".modal:not(.hidden)").forEach((m) => m.classList.add("hidden"));
  });
}

function bindUI() {
  bindModals();
  $("watchBtn").onclick = doWatch;
  $("pickBtn").onclick = doPick;
  $("folderInput").addEventListener("keydown", (e) => { if (e.key === "Enter") doWatch(); });
  $("copyCtx").onclick = async () => {
    const md = await api("/api/context");
    await navigator.clipboard.writeText(md);
    $("copyCtx").textContent = "Copied";
    setTimeout(() => ($("copyCtx").textContent = "Copy"), 1200);
  };
  $("search").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    if (!cy) return;
    if (!q) { cy.elements().removeClass("dim").removeClass("highlight"); return; }
    cy.elements().addClass("dim").removeClass("highlight");
    const matches = cy.nodes().filter((n) =>
      (n.data("fullName") || "").toLowerCase().includes(q) ||
      (n.data("path") || "").toLowerCase().includes(q)
    );
    matches.removeClass("dim").addClass("highlight");
    matches.connectedEdges().removeClass("dim");
  });

  $("layoutSel").addEventListener("change", (e) => {
    currentLayout = e.target.value;
    runLayout();
  });
  $("fitBtn").onclick = () => cy && cy.animate({ fit: { padding: 40 } }, { duration: 300 });
  $("relayoutBtn").onclick = () => runLayout();
  $("bobBtn").onclick = () => {
    bobEnabled = !bobEnabled;
    $("bobBtn").classList.toggle("active", bobEnabled);
    if (bobEnabled) startBobbing();
    else stopBobbing();
  };
  $("niClose").onclick = clearSelection;

  document.querySelectorAll(".kind-filter").forEach((btn) => {
    btn.onclick = () => {
      const k = btn.dataset.kind;
      if (visibleKinds.has(k)) { visibleKinds.delete(k); btn.classList.remove("active"); }
      else { visibleKinds.add(k); btn.classList.add("active"); }
      applyKindFilter();
    };
  });
}

async function refreshActivity() {
  try { activity = await api("/api/activity"); } catch { activity = {}; }
  applyHeatmap();
}

async function tick() {
  try {
    await Promise.all([refreshGraph(), refreshChanges(), refreshStats(),
                       refreshContext(), refreshActivity()]);
  } catch {}
}

window.addEventListener("error", (e) => console.error("[app error]", e.error || e.message));

(async function () {
  try { bindUI(); } catch (e) { console.error("bindUI failed:", e); }
  try { initCy(); } catch (e) { console.error("initCy failed:", e); }
  try {
    const s = await api("/api/settings");
    window.HEATMAP_WINDOW_MS = (s.heatmap_minutes || 5) * 60 * 1000;
    bobEnabled = s.enable_bobbing !== false;
    $("bobBtn").classList.toggle("active", bobEnabled);
  } catch (e) { console.error("settings load failed:", e); }
  try { await refreshStatus(); } catch (e) { console.error("refreshStatus failed:", e); }
  try { await tick(); } catch (e) { console.error("tick failed:", e); }
  setInterval(async () => {
    try { await refreshStatus(); await tick(); } catch (e) { console.error("poll failed:", e); }
  }, 2500);
  // Refresh heatmap every 15s so glow fades smoothly without refetching graph.
  setInterval(() => { applyHeatmap(); }, 15000);

  // Start continuous animations.
  if (bobEnabled) startBobbing();
  startPulse();
  startDashFlow();
})();
