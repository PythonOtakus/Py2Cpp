"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ArchitectCanvasPanel = void 0;
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const planRunner_1 = require("./planRunner");
const util_1 = require("./util");
const ARCH_PLAN_SUFFIX = ".arch.json";
function shortName(moduleId) {
    const parts = moduleId.split("/");
    return parts.length <= 2 ? moduleId : parts.slice(-2).join("/");
}
class ArchitectCanvasPanel {
    static createOrShow(repoRoot, store, focusModule) {
        const column = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.One;
        if (ArchitectCanvasPanel.current) {
            ArchitectCanvasPanel.current.panel.reveal(column);
            ArchitectCanvasPanel.current.update(focusModule);
            return;
        }
        const panel = vscode.window.createWebviewPanel("py2cppArchitectCanvas", "Py2Cpp Architect", column, {
            enableScripts: true,
            retainContextWhenHidden: true,
            localResourceRoots: [],
        });
        ArchitectCanvasPanel.current = new ArchitectCanvasPanel(panel, repoRoot, store);
        ArchitectCanvasPanel.current.update(focusModule);
    }
    constructor(panel, repoRoot, store) {
        this.disposables = [];
        this.repoRoot = repoRoot;
        this.store = store;
        this.panel = panel;
        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
        this.panel.webview.onDidReceiveMessage(async (msg) => {
            try {
                await this.onMessage(msg);
            }
            catch (err) {
                void vscode.window.showErrorMessage(String(err?.message ?? err));
            }
        }, null, this.disposables);
    }
    dispose() {
        ArchitectCanvasPanel.current = undefined;
        while (this.disposables.length) {
            const d = this.disposables.pop();
            d?.dispose();
        }
    }
    async onMessage(msg) {
        if (msg.type === "openModule" && typeof msg.moduleId === "string") {
            await this.openModule(msg.moduleId);
        }
        if (msg.type === "focusModule" && typeof msg.moduleId === "string") {
            this.update(msg.moduleId, msg.view, msg.domain);
        }
        if (msg.type === "savePlan" && msg.plan) {
            await this.savePlan(msg.plan);
        }
        if (msg.type === "checkPlan" && msg.plan) {
            await this.checkPlan(msg.plan);
        }
        if (msg.type === "applyPlan" && msg.plan) {
            await this.applyPlan(msg.plan);
        }
    }
    async openModule(moduleId) {
        const abs = this.store.pyFileAbs(this.repoRoot, moduleId);
        const uri = vscode.Uri.file(abs);
        const doc = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(doc, { preview: true });
    }
    plansDir() {
        return path.join((0, util_1.getGeneratedDir)(this.repoRoot), ".cache", "architect", "plans");
    }
    async savePlan(plan) {
        const dir = this.plansDir();
        fs.mkdirSync(dir, { recursive: true });
        const id = plan.id || `refactor-${Date.now()}`;
        const file = path.join(dir, `${id}${ARCH_PLAN_SUFFIX}`);
        fs.writeFileSync(file, JSON.stringify(plan, null, 2), "utf8");
        void vscode.window.showInformationMessage(`已保存 ${path.basename(file)}`);
    }
    async checkPlan(plan) {
        const tmp = path.join(this.plansDir(), `_preview_${Date.now()}${ARCH_PLAN_SUFFIX}`);
        fs.mkdirSync(path.dirname(tmp), { recursive: true });
        fs.writeFileSync(tmp, JSON.stringify(plan, null, 2), "utf8");
        try {
            const diff = await (0, planRunner_1.checkRefactorPlan)(this.repoRoot, tmp);
            const doc = await vscode.workspace.openTextDocument({ content: diff || "(无 diff)", language: "diff" });
            await vscode.window.showTextDocument(doc, { preview: true });
        }
        finally {
            try {
                fs.unlinkSync(tmp);
            }
            catch { /* ignore */ }
        }
    }
    async applyPlan(plan) {
        const tmp = path.join(this.plansDir(), `_apply_${Date.now()}${ARCH_PLAN_SUFFIX}`);
        fs.mkdirSync(path.dirname(tmp), { recursive: true });
        fs.writeFileSync(tmp, JSON.stringify(plan, null, 2), "utf8");
        try {
            const diff = await (0, planRunner_1.checkRefactorPlan)(this.repoRoot, tmp);
            if (!diff.trim()) {
                void vscode.window.showInformationMessage("计划无变更。");
                return;
            }
            const doc = await vscode.workspace.openTextDocument({ content: diff, language: "diff" });
            await vscode.window.showTextDocument(doc, { preview: true });
            const ok = await vscode.window.showWarningMessage("应用 RefactorPlan 并写回源文件？", { modal: true }, "应用");
            if (ok !== "应用") {
                return;
            }
            await (0, planRunner_1.applyRefactorPlan)(this.repoRoot, tmp);
            void vscode.window.showInformationMessage("RefactorPlan 已应用。");
            this.store.reload(this.repoRoot);
            this.update(plan.visual?.module ?? undefined);
        }
        finally {
            try {
                fs.unlinkSync(tmp);
            }
            catch { /* ignore */ }
        }
    }
    update(focusModule, view, domain) {
        const modules = this.store.moduleIds();
        const center = focusModule && modules.includes(focusModule) ? focusModule : modules[0] ?? "";
        const meta = this.store.meta();
        const state = {
            focus: center,
            view: view ?? "module",
            domain: domain ?? (center ? this.store.domainPrefix(center) : "py2cpp"),
            scope: "focus",
        };
        this.panel.webview.html = this.renderHtml(meta, this.store.toJson(), state);
    }
    renderHtml(meta, graph, state) {
        const payload = JSON.stringify({ meta, graph, state });
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';" />
<style>
  :root { --node-w: 200px; --node-h: 52px; --field-h: 36px; }
  html, body { height: 100%; margin: 0; overflow: hidden; font-family: var(--vscode-font-family); font-size: 14px; color: var(--vscode-foreground); }
  .shell { display: grid; grid-template-rows: auto 1fr auto; grid-template-columns: 1fr 300px; height: 100%; }
  .toolbar { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--vscode-panel-border); background: var(--vscode-editor-background); }
  .toolbar button, .toolbar select, .toolbar input { font-size: 13px; padding: 5px 10px; background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); border: 1px solid var(--vscode-panel-border); border-radius: 4px; cursor: pointer; }
  .toolbar button:hover { background: var(--vscode-button-secondaryHoverBackground); }
  .toolbar .primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
  .toolbar .primary:hover { background: var(--vscode-button-hoverBackground); }
  .toolbar .sep { width: 1px; height: 22px; background: var(--vscode-panel-border); margin: 0 4px; }
  .canvas-wrap { position: relative; overflow: hidden; background: var(--vscode-editor-background); min-height: 0; }
  #viewport { width: 100%; height: 100%; display: block; cursor: grab; }
  #viewport.dragging { cursor: grabbing; }
  .inspector { border-left: 1px solid var(--vscode-panel-border); padding: 10px 12px; overflow: auto; min-height: 0; background: var(--vscode-sideBar-background); }
  .inspector h3 { margin: 0 0 8px; font-size: 14px; }
  .inspector .path { font-size: 12px; color: var(--vscode-descriptionForeground); word-break: break-all; margin-bottom: 10px; }
  .inspector label { display: block; font-size: 12px; margin: 8px 0 4px; color: var(--vscode-descriptionForeground); }
  .inspector input, .inspector select { width: 100%; box-sizing: border-box; padding: 6px 8px; font-size: 13px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; }
  .plan-bar { grid-column: 1 / -1; border-top: 1px solid var(--vscode-panel-border); padding: 8px 12px; max-height: 140px; overflow: auto; background: var(--vscode-editor-background); font-size: 13px; }
  .plan-bar h4 { margin: 0 0 6px; font-size: 13px; }
  .plan-op { padding: 4px 0; border-bottom: 1px solid var(--vscode-panel-border); }
  .muted { color: var(--vscode-descriptionForeground); }
  .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
  .stat { font-size: 12px; color: var(--vscode-descriptionForeground); }
</style>
</head>
<body>
<div class="shell">
  <div class="toolbar">
    <button id="btnBack" title="返回模块图">← 模块</button>
    <button id="btnDrill" title="展开符号图">符号图 ↗</button>
    <span class="sep"></span>
    <button id="btnZoomIn">＋</button>
    <button id="btnZoomOut">－</button>
    <button id="btnFit">适配</button>
    <span class="sep"></span>
    <select id="scope">
      <option value="focus">焦点 2-hop</option>
      <option value="domain">当前域</option>
      <option value="all">全部模块</option>
    </select>
    <input id="filter" type="search" placeholder="筛选节点…" style="min-width:160px" />
    <span class="stat" id="stat"></span>
    <span style="flex:1"></span>
    <button id="btnPreview" class="primary">预览 diff</button>
    <button id="btnSave">保存 .arch.json</button>
    <button id="btnApply" class="primary">应用计划</button>
  </div>
  <div class="canvas-wrap">
    <svg id="viewport"></svg>
  </div>
  <div class="inspector" id="inspector">
    <div class="muted">选择节点查看详情；符号图中拖线连接两个字段引脚可加入重命名计划。</div>
  </div>
  <div class="plan-bar">
    <h4>重构计划 <span class="badge" id="planCount">0</span></h4>
    <div id="planList" class="muted">暂无操作。在符号图中将字段引脚拖到目标引脚，或在检视器中添加 rename。</div>
  </div>
</div>
<script>
(function() {
  const vscode = acquireVsCodeApi();
  const DATA = ${payload};
  const NS = "http://www.w3.org/2000/svg";
  const NODE_W = 200, NODE_H = 52, FIELD_H = 34, GAP_X = 80, GAP_Y = 24;

  let view = DATA.state.view || "module";
  let focus = DATA.state.focus || "";
  let scope = DATA.state.scope || "focus";
  let filterQ = "";
  let zoom = 1, panX = 40, panY = 40;
  let selected = null;
  let dragPin = null;
  let dragLine = null;
  let draft = { version: 1, id: "draft-" + Date.now(), kind: "architect_refactor", visual: { view: "module", edges: [] }, ops: [] };

  const modules = DATA.graph.modules || {};
  const allRefs = DATA.graph.refs || [];
  const moduleIds = Object.keys(modules).sort();

  function post(type, extra) { vscode.postMessage(Object.assign({ type }, extra || {})); }

  function outgoing(id) { return (modules[id] && modules[id].imports) || []; }
  function incoming(id) {
    const out = [];
    for (const mid of moduleIds) { if (outgoing(mid).includes(id)) out.push(mid); }
    return out.sort();
  }
  function domainPrefix(id) {
    const p = id.split("/");
    if (p[0] === "py2cpp" && p.length >= 2) return "py2cpp/" + p[1];
    return p[0] || id;
  }
  function neighborhood(id, hops) {
    const nodes = new Set([id]);
    let frontier = [id];
    for (let h = 0; h < hops; h++) {
      const next = [];
      for (const n of frontier) {
        for (const d of outgoing(n)) if (!nodes.has(d)) { nodes.add(d); next.push(d); }
        for (const s of incoming(n)) if (!nodes.has(s)) { nodes.add(s); next.push(s); }
      }
      frontier = next;
    }
    return [...nodes].sort();
  }
  function modulesInScope() {
    let ids;
    if (scope === "all") ids = moduleIds.slice();
    else if (scope === "domain") {
      const dom = domainPrefix(focus);
      ids = moduleIds.filter(id => id === dom || id.startsWith(dom + "/"));
    } else {
      ids = focus ? neighborhood(focus, 2) : moduleIds.slice(0, 40);
    }
    if (filterQ) {
      const q = filterQ.toLowerCase();
      ids = ids.filter(id => id.toLowerCase().includes(q));
    }
    return ids;
  }
  function shortName(id) {
    const p = id.split("/");
    return p.length <= 2 ? id : p.slice(-2).join("/");
  }
  function symKey(ep) {
    if (!ep) return "";
    if (typeof ep === "string") return ep;
    const o = ep.owner ? ep.owner + "." : "";
    return (ep.module || "") + ":" + o + ep.symbol;
  }
  function symbolNodes(modId) {
    const syms = (modules[modId] && modules[modId].symbols) || [];
    const nodes = [];
    const classes = syms.filter(s => s.kind === "class");
    for (const cls of classes) {
      nodes.push({ id: symKey({ module: modId, symbol: cls.name, kind: "class" }), module: modId, kind: "class", name: cls.name, owner: null, w: NODE_W, h: NODE_H });
      const fields = syms.filter(s => s.kind === "field" && s.owner === cls.name);
      fields.forEach((f, i) => {
        nodes.push({
          id: symKey({ module: modId, owner: cls.name, symbol: f.name, kind: "field" }),
          module: modId, kind: "field", name: f.name, owner: cls.name,
          w: NODE_W - 20, h: FIELD_H, parentClass: cls.name, pinIndex: i
        });
      });
    }
    for (const fn of syms.filter(s => s.kind === "function")) {
      nodes.push({ id: symKey({ module: modId, symbol: fn.name, kind: "function" }), module: modId, kind: "function", name: fn.name, owner: null, w: NODE_W, h: FIELD_H });
    }
    return nodes;
  }
  function symbolEdges(modId) {
    return allRefs.filter(r => {
      if (r.kind === "import") return false;
      const f = r.from, t = r.to;
      const fm = typeof f === "object" ? f.module : null;
      const tm = typeof t === "object" ? t.module : null;
      return fm === modId || tm === modId;
    });
  }

  function layeredLayout(ids) {
    const idSet = new Set(ids);
    const layer = new Map();
    ids.forEach(id => layer.set(id, 0));
    for (let iter = 0; iter < ids.length + 2; iter++) {
      let changed = false;
      for (const id of ids) {
        let maxPred = 0;
        for (const dep of outgoing(id)) {
          if (idSet.has(dep)) maxPred = Math.max(maxPred, (layer.get(dep) || 0) + 1);
        }
        if (maxPred > (layer.get(id) || 0)) { layer.set(id, maxPred); changed = true; }
      }
      if (!changed) break;
    }
    const buckets = new Map();
    for (const id of ids) {
      const L = layer.get(id) || 0;
      if (!buckets.has(L)) buckets.set(L, []);
      buckets.get(L).push(id);
    }
    const positions = new Map();
    const layers = [...buckets.keys()].sort((a,b) => a-b);
    layers.forEach((L, li) => {
      const row = buckets.get(L).sort();
      const totalH = row.length * (NODE_H + GAP_Y);
      row.forEach((id, ri) => {
        positions.set(id, {
          x: li * (NODE_W + GAP_X),
          y: ri * (NODE_H + GAP_Y) - totalH / 2 + NODE_H / 2
        });
      });
    });
    return positions;
  }

  function layoutSymbolGraph(modId) {
    const nodes = symbolNodes(modId);
    const positions = new Map();
    const classes = nodes.filter(n => n.kind === "class");
    classes.forEach((c, i) => {
      positions.set(c.id, { x: 0, y: i * (NODE_H + 80) });
      const fields = nodes.filter(n => n.kind === "field" && n.owner === c.name);
      fields.forEach((f, fi) => {
        positions.set(f.id, { x: NODE_W + 40, y: i * (NODE_H + 80) + fi * (FIELD_H + 8) });
      });
    });
    const fns = nodes.filter(n => n.kind === "function");
    fns.forEach((f, i) => {
      positions.set(f.id, { x: -NODE_W - 40, y: i * (FIELD_H + 12) });
    });
    return { nodes, positions };
  }

  const svg = document.getElementById("viewport");
  const gRoot = el("g", { id: "root" });
  const gEdges = el("g", { id: "edges" });
  const gNodes = el("g", { id: "nodes" });
  const gDraft = el("g", { id: "draft" });
  gRoot.appendChild(gEdges);
  gRoot.appendChild(gDraft);
  gRoot.appendChild(gNodes);
  svg.appendChild(gRoot);

  function el(name, attrs) {
    const n = document.createElementNS(NS, name);
    if (attrs) Object.entries(attrs).forEach(([k,v]) => n.setAttribute(k, String(v)));
    return n;
  }

  function applyTransform() {
    gRoot.setAttribute("transform", "translate(" + panX + "," + panY + ") scale(" + zoom + ")");
  }

  function clearG(g) { while (g.firstChild) g.removeChild(g.firstChild); }

  function drawModuleGraph() {
    clearG(gEdges); clearG(gNodes); clearG(gDraft);
    const ids = modulesInScope();
    const pos = layeredLayout(ids);
    const idSet = new Set(ids);
    for (const id of ids) {
      for (const dep of outgoing(id)) {
        if (!idSet.has(dep)) continue;
        const pDep = pos.get(dep), pId = pos.get(id);
        if (!pDep || !pId) continue;
        const x1 = pDep.x + NODE_W, y1 = pDep.y;
        const x2 = pId.x, y2 = pId.y;
        const path = el("path", {
          d: "M" + x1 + "," + y1 + " C" + (x1+40) + "," + y1 + " " + (x2-40) + "," + y2 + " " + x2 + "," + y2,
          fill: "none", stroke: "var(--vscode-textLink-foreground)", "stroke-width": 1.5, opacity: 0.75
        });
        gEdges.appendChild(path);
      }
    }
    for (const id of ids) {
      const p = pos.get(id);
      if (!p) continue;
      drawModuleNode(id, p.x, p.y, id === focus);
    }
    drawDraftEdges();
    fitIfNeeded();
    document.getElementById("stat").textContent = "模块 " + ids.length + " · graph v" + DATA.meta.version;
  }

  function drawModuleNode(id, x, y, isFocus) {
    const g = el("g", { class: "node", "data-id": id, transform: "translate(" + x + "," + (y - NODE_H/2) + ")" });
    const rect = el("rect", {
      width: NODE_W, height: NODE_H, rx: 8,
      fill: isFocus ? "var(--vscode-button-background)" : "var(--vscode-editor-inactiveSelectionBackground)",
      stroke: selected === id ? "var(--vscode-focusBorder)" : "var(--vscode-panel-border)",
      "stroke-width": selected === id ? 2.5 : 1
    });
    const t1 = el("text", { x: 10, y: 22, fill: isFocus ? "var(--vscode-button-foreground)" : "var(--vscode-foreground)", "font-size": 13, "font-weight": 600 });
    t1.textContent = shortName(id).slice(0, 24);
    const t2 = el("text", { x: 10, y: 40, fill: "var(--vscode-descriptionForeground)", "font-size": 10 });
    t2.textContent = id.length > 32 ? id.slice(0, 30) + "…" : id;
    g.appendChild(rect);
    g.appendChild(t1);
    g.appendChild(t2);
    g.onclick = (e) => { e.stopPropagation(); selectModule(id); };
    g.ondblclick = (e) => { e.stopPropagation(); focus = id; view = "symbol"; render(); };
    gNodes.appendChild(g);
  }

  function drawSymbolGraph() {
    clearG(gEdges); clearG(gNodes); clearG(gDraft);
    if (!focus) { drawModuleGraph(); return; }
    const { nodes, positions } = layoutSymbolGraph(focus);
    const edges = symbolEdges(focus);
    for (const r of edges) {
      const fk = symKey(r.from), tk = symKey(r.to);
      const p1 = positions.get(fk), p2 = positions.get(tk);
      if (!p1 || !p2) continue;
      const color = r.kind === "inherit" ? "var(--vscode-charts-purple)"
        : r.kind === "field_type" ? "var(--vscode-charts-blue)"
        : "var(--vscode-descriptionForeground)";
      const dash = r.kind === "field_type" ? "4 3" : "";
      const path = el("path", {
        d: edgePath(p1.x + (nodes.find(n=>n.id===fk)?.w||NODE_W), p1.y, p2.x, p2.y),
        fill: "none", stroke: color, "stroke-width": 1.2, "stroke-dasharray": dash, opacity: 0.85
      });
      gEdges.appendChild(path);
    }
    for (const n of nodes) {
      const p = positions.get(n.id);
      if (!p) continue;
      drawSymbolNode(n, p.x, p.y - n.h/2);
    }
    drawDraftEdges();
    document.getElementById("stat").textContent = "符号图 " + focus + " · " + nodes.length + " 节点";
  }

  function edgePath(x1, y1, x2, y2) {
    const mx = (x1 + x2) / 2;
    return "M" + x1 + "," + y1 + " C" + mx + "," + y1 + " " + mx + "," + y2 + " " + x2 + "," + y2;
  }

  function drawSymbolNode(n, x, y) {
    const sel = selected && selected.id === n.id;
    const g = el("g", { class: "node", transform: "translate(" + x + "," + y + ")" });
    const rect = el("rect", {
      width: n.w, height: n.h, rx: 6,
      fill: n.kind === "class" ? "var(--vscode-button-secondaryBackground)" : "var(--vscode-editor-inactiveSelectionBackground)",
      stroke: sel ? "var(--vscode-focusBorder)" : "var(--vscode-panel-border)",
      "stroke-width": sel ? 2.5 : 1
    });
    const label = n.kind === "field" ? (n.owner + "." + n.name) : n.name;
    const t = el("text", { x: 8, y: n.h/2 + 4, fill: "var(--vscode-foreground)", "font-size": 12 });
    t.textContent = label.slice(0, 28);
    g.appendChild(rect);
    g.appendChild(t);
    if (n.kind === "field") {
      const pin = el("circle", { cx: n.w, cy: n.h/2, r: 5, fill: "var(--vscode-charts-orange)", stroke: "#fff", "stroke-width": 1, class: "pin", "data-pin-for": n.id });
      pin.onmousedown = (e) => {
        e.stopPropagation();
        dragPin = { node: n, sx: x + n.w, sy: y + n.h/2 };
        dragLine = el("line", { x1: dragPin.sx, y1: dragPin.sy, x2: dragPin.sx, y2: dragPin.sy, stroke: "var(--vscode-charts-orange)", "stroke-width": 2, "stroke-dasharray": "5 4" });
        gDraft.appendChild(dragLine);
      };
      g.appendChild(pin);
    }
    g.onclick = (e) => { e.stopPropagation(); selectSymbol(n); };
    g.ondblclick = (e) => { e.stopPropagation(); if (n.kind !== "field") post("openModule", { moduleId: n.module }); };
    gNodes.appendChild(g);
  }

  function drawDraftEdges() {
    clearG(gDraft);
    for (const e of draft.visual.edges || []) {
      if (!e.fromPos || !e.toPos) continue;
      const path = el("path", {
        d: edgePath(e.fromPos.x, e.fromPos.y, e.toPos.x, e.toPos.y),
        fill: "none", stroke: "var(--vscode-charts-orange)", "stroke-width": 2.5, "stroke-dasharray": "6 4"
      });
      gDraft.appendChild(path);
    }
  }

  function selectModule(id) {
    selected = id;
    focus = id;
    renderInspectorModule(id);
    render();
  }

  function selectSymbol(n) {
    selected = n;
    renderInspectorSymbol(n);
    render();
  }

  function renderInspectorModule(id) {
    const el = document.getElementById("inspector");
    const imp = outgoing(id);
    const dep = incoming(id);
    el.innerHTML = '<h3>' + esc(shortName(id)) + '</h3><div class="path">' + esc(id) + '</div>'
      + '<div class="stat">imports ' + imp.length + ' · used by ' + dep.length + '</div>'
      + '<button class="primary" style="margin:8px 0;width:100%" id="inspOpen">打开源文件</button>'
      + '<button style="margin:4px 0;width:100%" id="inspSym">进入符号图</button>';
    document.getElementById("inspOpen").onclick = () => post("openModule", { moduleId: id });
    document.getElementById("inspSym").onclick = () => { view = "symbol"; render(); };
  }

  function renderInspectorSymbol(n) {
    const el = document.getElementById("inspector");
    let html = '<h3>' + esc(n.name) + '</h3><div class="path">' + esc(n.module) + ' · ' + esc(n.kind) + '</div>';
    if (n.kind === "field") {
      html += '<label>重命名为</label><input id="renameTo" placeholder="新字段名" />'
        + '<button class="primary" style="margin-top:8px;width:100%" id="addRename">加入 rename 计划</button>';
    }
    html += '<button style="margin-top:8px;width:100%" id="inspOpen">打开源文件</button>';
    el.innerHTML = html;
    document.getElementById("inspOpen").onclick = () => post("openModule", { moduleId: n.module });
    const btn = document.getElementById("addRename");
    if (btn) btn.onclick = () => {
      const to = document.getElementById("renameTo").value.trim();
      if (!to || to === n.name) return;
      addRenameOp(n.module, n.owner, n.name, to);
    };
  }

  function addRenameOp(moduleId, owner, from, to) {
    draft.ops.push({ op: "rename_symbol", kind: "field", module: moduleId, owner: owner, from: from, to: to });
    draft.visual.edges.push({ from: owner + "." + from, to: owner + "." + to, kind: "rename" });
    draft.visual.module = moduleId;
    draft.visual.view = view;
    renderPlanBar();
    render();
  }

  function renderPlanBar() {
    document.getElementById("planCount").textContent = String(draft.ops.length);
    const list = document.getElementById("planList");
    if (!draft.ops.length) {
      list.innerHTML = '<span class="muted">暂无操作</span>';
      return;
    }
    list.innerHTML = draft.ops.map((op, i) =>
      '<div class="plan-op">' + (i+1) + '. rename ' + esc(op.owner || "") + '.' + esc(op.from) + ' → ' + esc(op.to) + '</div>'
    ).join("");
  }

  function esc(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

  let fitPending = false;
  function fitIfNeeded() {
    if (!fitPending) return;
    fitPending = false;
    fitView();
  }

  function fitView() {
    const bb = gRoot.getBBox();
    if (!bb.width || !bb.height) return;
    const pad = 40;
    const rw = svg.clientWidth, rh = svg.clientHeight;
    zoom = Math.min((rw - pad*2) / bb.width, (rh - pad*2) / bb.height, 1.5);
    panX = (rw - bb.width * zoom) / 2 - bb.x * zoom;
    panY = (rh - bb.height * zoom) / 2 - bb.y * zoom;
    applyTransform();
  }

  function render() {
    draft.visual.view = view;
    if (view === "symbol") drawSymbolGraph();
    else drawModuleGraph();
    applyTransform();
    renderPlanBar();
  }

  // pan zoom
  let dragging = false, dragSx = 0, dragSy = 0, dragPx = 0, dragPy = 0;
  svg.addEventListener("mousedown", (e) => {
    if (e.target.classList && e.target.classList.contains("pin")) return;
    dragging = true;
    dragSx = e.clientX; dragSy = e.clientY;
    dragPx = panX; dragPy = panY;
    svg.classList.add("dragging");
  });
  window.addEventListener("mousemove", (e) => {
    if (dragPin && dragLine) {
      const pt = svgPoint(e.clientX, e.clientY);
      dragLine.setAttribute("x2", pt.x);
      dragLine.setAttribute("y2", pt.y);
    }
    if (!dragging) return;
    panX = dragPx + (e.clientX - dragSx);
    panY = dragPy + (e.clientY - dragSy);
    applyTransform();
  });
  function svgPoint(cx, cy) {
    const pt = svg.createSVGPoint();
    pt.x = cx; pt.y = cy;
    const ctm = gRoot.getScreenCTM();
    if (!ctm) return { x: cx, y: cy };
    const inv = ctm.inverse();
    const p = pt.matrixTransform(inv);
    return { x: p.x, y: p.y };
  }
  window.addEventListener("mouseup", (e) => {
    if (dragPin) {
      const target = document.elementFromPoint(e.clientX, e.clientY);
      const pinEl = target && target.closest ? target.closest("[data-pin-for]") : null;
      if (pinEl && dragPin.node.kind === "field") {
        const toId = pinEl.getAttribute("data-pin-for");
        const toNode = symbolNodes(focus).find(n => n.id === toId);
        if (toNode && toNode.kind === "field" && toNode.owner === dragPin.node.owner && toNode.name !== dragPin.node.name) {
          addRenameOp(dragPin.node.module, dragPin.node.owner, dragPin.node.name, toNode.name);
        } else if (toNode && toNode.kind === "field" && toNode.name !== dragPin.node.name) {
          const newName = prompt("重命名字段 " + dragPin.node.owner + "." + dragPin.node.name + " 为:", toNode.name);
          if (newName && newName !== dragPin.node.name) {
            addRenameOp(dragPin.node.module, dragPin.node.owner, dragPin.node.name, newName);
          }
        }
      } else if (dragPin.node.kind === "field") {
        const newName = prompt("重命名字段 " + dragPin.node.owner + "." + dragPin.node.name + " 为:");
        if (newName && newName !== dragPin.node.name) {
          addRenameOp(dragPin.node.module, dragPin.node.owner, dragPin.node.name, newName);
        }
      }
      if (dragLine && dragLine.parentNode) dragLine.parentNode.removeChild(dragLine);
      dragLine = null;
      dragPin = null;
    }
    dragging = false;
    svg.classList.remove("dragging");
  });
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    zoom = Math.max(0.15, Math.min(3, zoom * factor));
    applyTransform();
  }, { passive: false });

  document.getElementById("btnZoomIn").onclick = () => { zoom = Math.min(3, zoom * 1.2); applyTransform(); };
  document.getElementById("btnZoomOut").onclick = () => { zoom = Math.max(0.15, zoom / 1.2); applyTransform(); };
  document.getElementById("btnFit").onclick = () => fitView();
  document.getElementById("btnBack").onclick = () => { view = "module"; render(); };
  document.getElementById("btnDrill").onclick = () => { if (focus) { view = "symbol"; render(); } };
  document.getElementById("scope").value = scope;
  document.getElementById("scope").onchange = (e) => { scope = e.target.value; fitPending = true; render(); };
  document.getElementById("filter").oninput = (e) => { filterQ = e.target.value.trim(); render(); };
  document.getElementById("btnSave").onclick = () => post("savePlan", { plan: draft });
  document.getElementById("btnPreview").onclick = () => post("checkPlan", { plan: draft });
  document.getElementById("btnApply").onclick = () => post("applyPlan", { plan: draft });

  if (focus) renderInspectorModule(focus);
  fitPending = true;
  render();
})();
</script>
</body>
</html>`;
    }
}
exports.ArchitectCanvasPanel = ArchitectCanvasPanel;
ArchitectCanvasPanel.current = undefined;
