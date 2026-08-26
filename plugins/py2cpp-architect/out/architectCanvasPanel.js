"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ArchitectCanvasPanel = void 0;
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const planRunner_1 = require("./planRunner");
const dataclassSchemaPanel_1 = require("./dataclassSchemaPanel");
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
        if (msg.type === "editSchema" && msg.moduleId && msg.className) {
            dataclassSchemaPanel_1.DataclassSchemaPanel.createOrShow(this.repoRoot, this.store, msg.moduleId, msg.className);
        }
        if (msg.type === "requestLoadPlan") {
            await this.loadPlanIntoCanvas();
        }
        if (msg.type === "copyText" && typeof msg.text === "string") {
            await vscode.env.clipboard.writeText(msg.text);
            void vscode.window.showInformationMessage("已复制到剪贴板。");
        }
    }
    async loadPlanIntoCanvas() {
        const pick = await vscode.window.showOpenDialog({
            canSelectMany: false,
            filters: { "Architect Plan": ["arch.json"], JSON: ["json"] },
            title: "加载 RefactorPlan 到画布",
        });
        if (!pick || pick.length === 0) {
            return;
        }
        try {
            const plan = JSON.parse(fs.readFileSync(pick[0].fsPath, "utf8"));
            this.panel.webview.postMessage({ type: "loadPlan", plan });
        }
        catch (err) {
            void vscode.window.showErrorMessage(String(err?.message ?? err));
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
  :root {
    --node-w: 200px; --class-hdr: 22px; --field-row: 24px;
    --tb-h: 38px;
    --accent: var(--vscode-textLink-foreground);
    --node-bg: var(--vscode-editorWidget-background, var(--vscode-editor-inactiveSelectionBackground));
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; overflow: hidden; font-family: var(--vscode-font-family); font-size: 13px; color: var(--vscode-foreground); }
  .shell { display: grid; grid-template-rows: var(--tb-h) 1fr; grid-template-columns: 1fr; height: 100%; }
  .toolbar {
    grid-column: 1 / -1; display: flex; align-items: center; gap: 2px; padding: 0 6px;
    border-bottom: 1px solid var(--vscode-panel-border);
    background: var(--vscode-titleBar-activeBackground, var(--vscode-editor-background));
    min-height: var(--tb-h); user-select: none;
  }
  .tb-group { display: flex; align-items: center; gap: 2px; }
  .tb-sep { width: 1px; height: 20px; background: var(--vscode-panel-border); margin: 0 6px; flex-shrink: 0; }
  .icon-btn {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; padding: 0; border: none; border-radius: 4px;
    background: transparent; color: var(--vscode-foreground); cursor: pointer;
  }
  .icon-btn:hover { background: var(--vscode-toolbar-hoverBackground, rgba(127,127,127,.25)); }
  .icon-btn.active { background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
  .icon-btn.primary { color: var(--vscode-textLink-activeForeground, var(--vscode-textLink-foreground)); }
  .icon-btn svg { width: 16px; height: 16px; fill: currentColor; pointer-events: none; }
  .tb-select {
    height: 26px; font-size: 11px; padding: 0 6px; border-radius: 4px;
    background: var(--vscode-input-background); color: var(--vscode-input-foreground);
    border: 1px solid var(--vscode-input-border, transparent);
  }
  .tb-search {
    width: 108px; height: 26px; font-size: 11px; padding: 0 8px; border-radius: 4px;
    background: var(--vscode-input-background); color: var(--vscode-input-foreground);
    border: 1px solid var(--vscode-input-border, transparent);
  }
  .tb-spacer { flex: 1; min-width: 8px; }
  .select-chip {
    font-family: var(--vscode-editor-font-family, monospace); font-size: 11px;
    max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    padding: 2px 8px; border-radius: 4px;
    background: var(--vscode-badge-background); color: var(--vscode-badge-foreground);
  }
  .canvas-wrap {
    position: relative; overflow: hidden; min-height: 0;
    background-color: var(--vscode-editor-background);
    background-image: radial-gradient(circle, color-mix(in srgb, var(--vscode-foreground) 12%, transparent) 1px, transparent 1px);
    background-size: 18px 18px;
  }
  #viewport { width: 100%; height: 100%; display: block; cursor: grab; }
  #viewport.dragging { cursor: grabbing; }
  .canvas-status {
    position: absolute; left: 10px; top: 8px; z-index: 2; pointer-events: none;
    font-size: 11px; color: var(--vscode-descriptionForeground);
    padding: 4px 10px; border-radius: 4px;
    background: color-mix(in srgb, var(--vscode-editor-background) 85%, transparent);
    border: 1px solid var(--vscode-panel-border);
  }
  .plan-drawer {
    position: absolute; left: 10px; right: 10px; bottom: 10px; z-index: 3;
    max-height: 28px; overflow: hidden; transition: max-height .2s ease;
    border-radius: 6px; border: 1px solid var(--vscode-panel-border);
    background: color-mix(in srgb, var(--vscode-editor-background) 92%, transparent);
    backdrop-filter: blur(4px);
  }
  .plan-drawer.expanded { max-height: 132px; }
  .plan-drawer.has-ops:not(.expanded) { border-color: var(--vscode-charts-orange); }
  .plan-header {
    display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 8px;
    cursor: pointer; font-size: 11px; color: var(--vscode-descriptionForeground);
  }
  .plan-header .badge {
    padding: 1px 6px; border-radius: 8px; font-size: 10px;
    background: var(--vscode-badge-background); color: var(--vscode-badge-foreground);
  }
  .plan-header .chev { margin-left: auto; opacity: .7; }
  .plan-body { padding: 0 8px 8px; max-height: 96px; overflow: auto; font-size: 11px; }
  .plan-op { padding: 3px 0; border-bottom: 1px solid var(--vscode-panel-border); display: flex; align-items: center; gap: 6px; }
  .plan-op .rm { margin-left: auto; cursor: pointer; color: var(--vscode-errorForeground); border: none; background: transparent; font-size: 13px; line-height: 1; }
  .ctx-menu {
    position: fixed; z-index: 100; min-width: 168px; display: none;
    background: var(--vscode-menu-background); color: var(--vscode-menu-foreground);
    border: 1px solid var(--vscode-menu-border); border-radius: 4px;
    padding: 4px 0; box-shadow: 0 4px 14px rgba(0,0,0,.35);
  }
  .ctx-menu.show { display: block; }
  .ctx-item { padding: 5px 14px; font-size: 12px; cursor: pointer; white-space: nowrap; }
  .ctx-item:hover { background: var(--vscode-list-hoverBackground); }
  .ctx-item.disabled { opacity: .45; pointer-events: none; }
  .ctx-sep { height: 1px; margin: 4px 0; background: var(--vscode-menu-separatorBackground); }
  .muted { color: var(--vscode-descriptionForeground); font-size: 11px; line-height: 1.45; }
  .ghost .field-row { opacity: .75; }
  .pin-hot { filter: brightness(1.35); }
</style>
</head>
<body>
<div class="shell" id="shell">
  <div class="toolbar">
    <div class="tb-group">
      <button class="icon-btn" id="btnBack" title="模块图 (Module DAG)"><svg viewBox="0 0 16 16"><path d="M2 3h5v5H2V3zm7 0h5v5H9V3zM2 9h5v5H2V9zm7 0h5v5H9V9z"/></svg></button>
      <button class="icon-btn" id="btnDrill" title="符号图 (Symbol Graph)"><svg viewBox="0 0 16 16"><circle cx="4" cy="8" r="2.5"/><circle cx="12" cy="4" r="2"/><circle cx="12" cy="12" r="2"/><path d="M6.2 7.2L10 5M6.2 8.8L10 11" stroke="currentColor" fill="none" stroke-width="1.2"/></svg></button>
    </div>
    <span class="tb-sep"></span>
    <div class="tb-group">
      <button class="icon-btn" id="btnZoomIn" title="放大"><svg viewBox="0 0 16 16"><path d="M7 3v10M3 7h8" stroke="currentColor" stroke-width="1.5" fill="none"/></svg></button>
      <button class="icon-btn" id="btnZoomOut" title="缩小"><svg viewBox="0 0 16 16"><path d="M3 7h8" stroke="currentColor" stroke-width="1.5" fill="none"/></svg></button>
      <button class="icon-btn" id="btnFit" title="适配视图"><svg viewBox="0 0 16 16"><path d="M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3" stroke="currentColor" fill="none" stroke-width="1.3"/></svg></button>
    </div>
    <span class="tb-sep"></span>
    <select class="tb-select" id="scope" title="显示范围">
      <option value="focus">2-hop</option>
      <option value="domain">域</option>
      <option value="all">全部</option>
    </select>
    <input class="tb-search" id="filter" type="search" placeholder="筛选…" title="筛选节点" />
    <button class="icon-btn" id="btnToggleFns" title="显示模块函数（默认隐藏）"><svg viewBox="0 0 16 16"><path d="M3 4h10M3 8h10M3 12h6" stroke="currentColor" fill="none"/></svg></button>
    <span class="tb-spacer"></span>
    <div class="tb-group">
      <button class="icon-btn" id="btnPreview" title="预览 diff"><svg viewBox="0 0 16 16"><path d="M2 8s2.5-4 6-4 6 4 6 4-2.5 4-6 4-6-4-6-4z" stroke="currentColor" fill="none"/><circle cx="8" cy="8" r="2"/></svg></button>
      <button class="icon-btn" id="btnLoad" title="加载计划"><svg viewBox="0 0 16 16"><path d="M3 2h7l3 3v9H3V2z" stroke="currentColor" fill="none"/><path d="M10 2v3h3M6 9l2 2 3-3" stroke="currentColor" fill="none"/></svg></button>
      <button class="icon-btn" id="btnSave" title="保存 .arch.json"><svg viewBox="0 0 16 16"><path d="M3 2h8l3 3v9H3V2z" stroke="currentColor" fill="none"/><rect x="5" y="2" width="5" height="4" stroke="currentColor" fill="none"/><rect x="5" y="10" width="6" height="4" fill="currentColor" opacity=".5"/></svg></button>
      <button class="icon-btn primary" id="btnApply" title="应用计划"><svg viewBox="0 0 16 16"><path d="M3 8.5l3.5 3.5L13 4" stroke="currentColor" fill="none" stroke-width="1.8"/></svg></button>
    </div>
    <span class="tb-sep"></span>
    <span class="select-chip" id="selectPath" title="select 路径">—</span>
    <button class="icon-btn" id="btnCopySelect" title="复制 select 路径"><svg viewBox="0 0 16 16"><rect x="5" y="5" width="8" height="9" rx="1" stroke="currentColor" fill="none"/><path d="M3 11V3h8" stroke="currentColor" fill="none"/></svg></button>
    <button class="icon-btn" id="btnClearSelect" title="清空路径"><svg viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.4"/></svg></button>
  </div>
  <div class="canvas-wrap">
    <svg id="viewport"></svg>
    <div class="canvas-status" id="stat"></div>
    <div id="ctxMenu" class="ctx-menu"></div>
    <div class="plan-drawer" id="planDrawer">
      <div class="plan-header" id="planToggle">
        <span>重构计划</span><span class="badge" id="planCount">0</span>
        <button class="icon-btn" id="btnClearPlan" title="清空计划" style="width:22px;height:22px;margin-left:4px"><svg viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.3"/></svg></button>
        <span class="chev" id="planChev">▲</span>
      </div>
      <div class="plan-body" id="planList"><span class="muted">从字段右侧引脚拖到左侧引脚以 rename；右键节点打开菜单</span></div>
    </div>
  </div>
</div>
<script>
(function() {
  const vscode = acquireVsCodeApi();
  const DATA = ${payload};
  const NS = "http://www.w3.org/2000/svg";
  const NODE_W = 200, NODE_H = 48, GAP_X = 100, GAP_Y = 28;
  const CLASS_HDR = 22, FIELD_ROW = 24, CLASS_PAD = 6, CLASS_GAP = 40, FN_H = 26, HDR_H = 18;
  let showFunctions = false;
  let symbolLayout = null;

  let view = DATA.state.view || "module";
  let focus = DATA.state.focus || "";
  let scope = DATA.state.scope || "focus";
  let filterQ = "";
  let zoom = 1, panX = 40, panY = 40;
  let selected = null;
  let dragPin = null;
  let dragLine = null;
  let draft = { version: 1, id: "draft-" + Date.now(), kind: "architect_refactor", visual: { view: "module", edges: [] }, ops: [] };
  let selectPathParts = [];

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || msg.type !== "loadPlan" || !msg.plan) return;
    draft = msg.plan;
    if (!draft.visual) draft.visual = { view: "module", edges: [] };
    if (draft.visual.module) {
      focus = draft.visual.module;
      view = draft.visual.view === "symbol" ? "symbol" : "module";
    }
    fitPending = true;
    if (draft.ops.length) expandPlanDrawer();
    renderPlanBar();
    render();
  });

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
  function classBoxHeight(fieldCount) { return CLASS_HDR + CLASS_PAD + fieldCount * FIELD_ROW + CLASS_PAD; }
  function fieldKey(owner, name) { return owner + "." + name; }

  function buildSymbolLayout(modId) {
    const syms = (modules[modId] && modules[modId].symbols) || [];
    const classBoxes = [];
    const fnNodes = [];
    const fieldPins = new Map();
    const classByName = new Map();
    let yTop = 0;

    for (const cls of syms.filter(s => s.kind === "class")) {
      const fields = syms.filter(s => s.kind === "field" && s.owner === cls.name).map(f => ({
        name: f.name, typeAnn: f.typeAnn || "", ghost: false
      }));
      for (const op of draft.ops) {
        if (op.op !== "rename_symbol" || op.kind !== "field" || op.module !== modId || op.owner !== cls.name) continue;
        if (!fields.some(f => f.name === op.to)) fields.push({ name: op.to, typeAnn: "", ghost: true });
      }
      const h = classBoxHeight(fields.length);
      const box = {
        id: symKey({ module: modId, symbol: cls.name, kind: "class" }),
        module: modId, name: cls.name, role: cls.role || "", fields,
        x: 0, y: yTop, w: NODE_W, h
      };
      classBoxes.push(box);
      classByName.set(cls.name, box);
      fields.forEach((f, fi) => {
        const rowY = yTop + CLASS_HDR + CLASS_PAD + fi * FIELD_ROW + FIELD_ROW / 2;
        fieldPins.set(fieldKey(cls.name, f.name), {
          inX: 0, inY: rowY, outX: NODE_W, outY: rowY,
          module: modId, owner: cls.name, field: f.name
        });
      });
      yTop += h + CLASS_GAP;
    }

    if (showFunctions) {
      const fns = syms.filter(s => s.kind === "function");
      if (fns.length) yTop += 12;
      fns.forEach((fn, i) => {
        fnNodes.push({
          id: symKey({ module: modId, symbol: fn.name, kind: "function" }),
          module: modId, name: fn.name, kind: "function",
          x: 0, y: yTop + i * (FN_H + 8), w: NODE_W, h: FN_H
        });
      });
    }
    return { classBoxes, fnNodes, fieldPins, classByName, fnCount: syms.filter(s => s.kind === "function").length };
  }

  function isFieldPlanned(owner, name) {
    return draft.ops.some((op) =>
      op.op === "rename_symbol" && op.kind === "field" && op.owner === owner
      && (op.from === name || op.to === name));
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
  function refAnchor(ep, layout, side) {
    if (!ep || typeof ep !== "object") return null;
    if (ep.kind === "field" && ep.owner) {
      const pin = layout.fieldPins.get(fieldKey(ep.owner, ep.symbol));
      if (!pin) return null;
      return side === "in" ? { x: pin.inX, y: pin.inY } : { x: pin.outX, y: pin.outY };
    }
    if (ep.kind === "class") {
      const box = layout.classByName.get(ep.symbol);
      if (!box) return null;
      return side === "in"
        ? { x: box.x, y: box.y + box.h / 2 }
        : { x: box.x + box.w, y: box.y + box.h / 2 };
    }
    return null;
  }
  function smoothEdge(x1, y1, x2, y2) {
    const dx = Math.abs(x2 - x1);
    const dy = Math.abs(y2 - y1);
    if (dx > dy * 1.2) {
      const c = Math.max(48, dx * 0.42);
      return "M" + x1 + "," + y1 + " C" + (x1 + c) + "," + y1 + " " + (x2 - c) + "," + y2 + " " + x2 + "," + y2;
    }
    const c = Math.max(36, dy * 0.38);
    return "M" + x1 + "," + y1 + " C" + x1 + "," + (y1 + c) + " " + x2 + "," + (y2 - c) + " " + x2 + "," + y2;
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
    symbolLayout = buildSymbolLayout(modId);
    return symbolLayout;
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
    fitIfNeeded();
    document.getElementById("stat").textContent = "模块 " + ids.length + " · graph v" + DATA.meta.version;
  }

  function drawModuleNode(id, x, y, isFocus) {
    const g = el("g", { class: "node", "data-id": id, transform: "translate(" + x + "," + (y - NODE_H/2) + ")" });
    const hdrFill = isFocus ? "var(--vscode-textLink-foreground)" : "var(--vscode-button-secondaryBackground)";
    const body = el("rect", {
      y: HDR_H - 1, width: NODE_W, height: NODE_H - HDR_H + 1, rx: 6,
      fill: "var(--node-bg)",
      stroke: (selected && selected.kind === "module" && selected.id === id) ? "var(--vscode-focusBorder)" : "var(--vscode-panel-border)",
      "stroke-width": (selected && selected.kind === "module" && selected.id === id) ? 2 : 1
    });
    const hdr = el("rect", { width: NODE_W, height: HDR_H, rx: 6, fill: hdrFill });
    const t1 = el("text", {
      x: 8, y: 13, fill: isFocus ? "var(--vscode-button-foreground)" : "var(--vscode-foreground)",
      "font-size": 11, "font-weight": 600
    });
    t1.textContent = shortName(id).slice(0, 22);
    const impN = outgoing(id).length;
    if (impN) {
      const badge = el("text", {
        x: NODE_W - 8, y: 13, "text-anchor": "end",
        fill: isFocus ? "var(--vscode-button-foreground)" : "var(--vscode-descriptionForeground)", "font-size": 9
      });
      badge.textContent = "↓" + impN;
      g.appendChild(badge);
    }
    const t2 = el("text", { x: 8, y: HDR_H + 15, fill: "var(--vscode-descriptionForeground)", "font-size": 9 });
    t2.textContent = id.length > 30 ? id.slice(0, 28) + "…" : id;
    g.appendChild(body);
    g.appendChild(hdr);
    g.appendChild(t1);
    g.appendChild(t2);
    g.onclick = (e) => { e.stopPropagation(); selectModule(id); };
    g.oncontextmenu = (e) => {
      e.preventDefault(); e.stopPropagation();
      showContextMenu(e.clientX, e.clientY, moduleMenuItems(id));
    };
    g.ondblclick = (e) => { e.stopPropagation(); focus = id; view = "symbol"; render(); };
    gNodes.appendChild(g);
  }

  function drawSymbolGraph() {
    clearG(gEdges); clearG(gNodes); clearG(gDraft);
    if (!focus) { drawModuleGraph(); return; }
    const layout = layoutSymbolGraph(focus);
    const edges = symbolEdges(focus);
    for (const r of edges) {
      if (r.kind === "select_path") continue;
      const a = refAnchor(r.from, layout, "out");
      const b = refAnchor(r.to, layout, "in");
      if (!a || !b) continue;
      const color = r.kind === "inherit" ? "var(--vscode-charts-purple)"
        : r.kind === "field_type" ? "var(--vscode-charts-blue)"
        : "var(--vscode-descriptionForeground)";
      const path = el("path", {
        d: smoothEdge(a.x, a.y, b.x, b.y),
        fill: "none", stroke: color, "stroke-width": 1.4,
        "stroke-dasharray": r.kind === "field_type" ? "5 4" : "",
        opacity: 0.8
      });
      gEdges.appendChild(path);
    }
    for (const box of layout.classBoxes) drawClassBox(box);
    if (showFunctions) {
      for (const fn of layout.fnNodes) drawFunctionNode(fn);
      if (layout.fnNodes.length) {
        const labelY = layout.fnNodes[0].y - 10;
        const t = el("text", { x: 0, y: labelY, fill: "var(--vscode-descriptionForeground)", "font-size": 10 });
        t.textContent = "模块函数";
        gNodes.appendChild(t);
      }
    }
    drawDraftEdges(layout);
    let stat = "符号图 " + focus + " · " + layout.classBoxes.length + " 类";
    if (layout.fnCount && !showFunctions) stat += " · " + layout.fnCount + " 函数已隐藏";
    document.getElementById("stat").textContent = stat;
  }

  function drawClassBox(box) {
    const sel = selected && selected.kind === "class" && selected.name === box.name;
    const g = el("g", { class: "node class-box", transform: "translate(" + box.x + "," + box.y + ")" });
    const body = el("rect", {
      width: box.w, height: box.h, rx: 6,
      fill: "var(--node-bg)",
      stroke: sel ? "var(--vscode-focusBorder)" : "var(--vscode-panel-border)",
      "stroke-width": sel ? 2 : 1
    });
    const hdr = el("rect", { width: box.w, height: CLASS_HDR, rx: 6, fill: "var(--vscode-textLink-foreground)" });
    const title = el("text", { x: 8, y: 15, fill: "var(--vscode-button-foreground)", "font-size": 11, "font-weight": 600 });
    title.textContent = box.name.slice(0, 26);
    g.appendChild(body);
    g.appendChild(hdr);
    g.appendChild(title);
    if (box.role === "dataclass") {
      const tag = el("text", { x: box.w - 6, y: 15, "text-anchor": "end", fill: "var(--vscode-button-foreground)", "font-size": 8 });
      tag.textContent = "dc";
      g.appendChild(tag);
    }
    box.fields.forEach((f, fi) => {
      const rowY = CLASS_HDR + CLASS_PAD + fi * FIELD_ROW;
      const row = el("g", { class: "field-row" + (f.ghost ? " ghost" : "") });
      const planned = isFieldPlanned(box.name, f.name);
      const fsel = selected && selected.kind === "field" && selected.owner === box.name && selected.name === f.name;
      const rowBg = el("rect", {
        x: 4, y: rowY, width: box.w - 8, height: FIELD_ROW - 2, rx: 3,
        fill: f.ghost ? "var(--vscode-inputValidation-warningBackground)" : "transparent",
        stroke: fsel ? "var(--vscode-focusBorder)" : planned ? "var(--vscode-charts-orange)" : "transparent",
        "stroke-width": fsel || planned ? 1.5 : 0
      });
      const label = el("text", { x: 12, y: rowY + FIELD_ROW / 2 + 3, fill: "var(--vscode-foreground)", "font-size": 10 });
      label.textContent = f.name.slice(0, 22);
      const typeT = el("text", { x: box.w - 18, y: rowY + FIELD_ROW / 2 + 3, "text-anchor": "end", fill: "var(--vscode-descriptionForeground)", "font-size": 8 });
      if (f.typeAnn) typeT.textContent = f.typeAnn.slice(0, 14);
      const fk = fieldKey(box.name, f.name);
      const pinIn = el("circle", {
        cx: 0, cy: rowY + FIELD_ROW / 2, r: 4,
        fill: "var(--vscode-charts-blue)", stroke: "#fff", "stroke-width": 1,
        class: "pin pin-in", "data-pin-in": fk
      });
      const pinOut = el("circle", {
        cx: box.w, cy: rowY + FIELD_ROW / 2, r: 4,
        fill: "var(--vscode-charts-orange)", stroke: "#fff", "stroke-width": 1,
        class: "pin pin-out", "data-pin-out": fk
      });
      pinOut.onmousedown = (e) => startPinDrag(e, box.module, box.name, f.name, box.x + box.w, box.y + rowY + FIELD_ROW / 2);
      const fieldObj = { kind: "field", module: box.module, owner: box.name, name: f.name, id: symKey({ module: box.module, owner: box.name, symbol: f.name, kind: "field" }) };
      row.onclick = (e) => { e.stopPropagation(); selectSymbol(fieldObj); };
      row.oncontextmenu = (e) => {
        e.preventDefault(); e.stopPropagation();
        showContextMenu(e.clientX, e.clientY, fieldMenuItems(fieldObj));
      };
      row.appendChild(rowBg);
      row.appendChild(label);
      if (f.typeAnn) row.appendChild(typeT);
      row.appendChild(pinIn);
      row.appendChild(pinOut);
      g.appendChild(row);
    });
    g.onclick = (e) => { e.stopPropagation(); selectSymbol({ kind: "class", module: box.module, name: box.name, role: box.role, id: box.id }); };
    g.oncontextmenu = (e) => {
      e.preventDefault(); e.stopPropagation();
      showContextMenu(e.clientX, e.clientY, classMenuItems(box));
    };
    g.ondblclick = (e) => { e.stopPropagation(); post("openModule", { moduleId: box.module }); };
    gNodes.appendChild(g);
  }

  function drawFunctionNode(fn) {
    const g = el("g", { class: "node fn-node", transform: "translate(" + fn.x + "," + fn.y + ")" });
    const rect = el("rect", {
      width: fn.w, height: fn.h, rx: 4,
      fill: "var(--node-bg)", stroke: "var(--vscode-panel-border)", "stroke-width": 1
    });
    const t = el("text", { x: 8, y: fn.h / 2 + 3, fill: "var(--vscode-descriptionForeground)", "font-size": 10 });
    t.textContent = fn.name.slice(0, 28);
    g.appendChild(rect);
    g.appendChild(t);
    g.oncontextmenu = (e) => {
      e.preventDefault(); e.stopPropagation();
      showContextMenu(e.clientX, e.clientY, [
        { label: "打开源文件", action: () => post("openModule", { moduleId: fn.module }) }
      ]);
    };
    gNodes.appendChild(g);
  }

  function startPinDrag(e, moduleId, owner, field, sx, sy) {
    e.stopPropagation();
    dragPin = { module: moduleId, owner: owner, field: field, sx: sx, sy: sy };
    dragLine = el("line", { x1: sx, y1: sy, x2: sx, y2: sy, stroke: "var(--vscode-charts-orange)", "stroke-width": 2, "stroke-dasharray": "5 4" });
    gDraft.appendChild(dragLine);
    document.querySelectorAll("[data-pin-in]").forEach((pin) => {
      if (pin.getAttribute("data-pin-in").split(".")[0] === owner) pin.classList.add("pin-hot");
    });
  }

  function drawDraftEdges(layout) {
    if (!layout) return;
    for (const op of draft.ops) {
      if (op.op !== "rename_symbol" || op.kind !== "field") continue;
      const fromPin = layout.fieldPins.get(fieldKey(op.owner, op.from));
      const toPin = layout.fieldPins.get(fieldKey(op.owner, op.to));
      if (!fromPin || !toPin) continue;
      const path = el("path", {
        d: smoothEdge(fromPin.outX, fromPin.outY, toPin.inX, toPin.inY),
        fill: "none", stroke: "var(--vscode-charts-orange)", "stroke-width": 2.5, "stroke-dasharray": "6 4"
      });
      gDraft.appendChild(path);
    }
  }

  function hideContextMenu() {
    const menu = document.getElementById("ctxMenu");
    if (menu) menu.classList.remove("show");
  }
  function showContextMenu(x, y, items) {
    const menu = document.getElementById("ctxMenu");
    if (!menu) return;
    menu.innerHTML = items.map((it, i) => it.sep
      ? '<div class="ctx-sep"></div>'
      : '<div class="ctx-item' + (it.disabled ? " disabled" : "") + '" data-i="' + i + '">' + esc(it.label) + '</div>').join("");
    menu.style.left = Math.min(x, window.innerWidth - 180) + "px";
    menu.style.top = Math.min(y, window.innerHeight - items.length * 28) + "px";
    menu.classList.add("show");
    menu.querySelectorAll(".ctx-item").forEach((el) => {
      const it = items[Number(el.getAttribute("data-i"))];
      if (it.disabled) return;
      el.onclick = () => { hideContextMenu(); it.action(); };
    });
  }
  function moduleMenuItems(id) {
    return [
      { label: "进入符号图", action: () => { focus = id; view = "symbol"; render(); } },
      { label: "打开源文件", action: () => post("openModule", { moduleId: id }) },
      { sep: true },
      { label: "imports " + outgoing(id).length + " · used by " + incoming(id).length, disabled: true }
    ];
  }
  function classMenuItems(box) {
    const items = [
      { label: "打开源文件", action: () => post("openModule", { moduleId: box.module }) }
    ];
    if (box.role === "dataclass") {
      items.push({ label: "编辑 Dataclass Schema", action: () => post("editSchema", { moduleId: box.module, className: box.name }) });
    }
    return items;
  }
  function fieldMenuItems(f) {
    return [
      { label: "重命名…", action: () => {
        const to = prompt("重命名字段 " + f.owner + "." + f.name + " 为:");
        if (to && to !== f.name) addRenameOp(f.module, f.owner, f.name, to);
      }},
      { label: "追加到 select 路径", action: () => { selectPathParts.push("." + f.name); updateSelectPathBar(); } },
      { sep: true },
      { label: "打开源文件", action: () => post("openModule", { moduleId: f.module }) }
    ];
  }

  function selectModule(id) {
    selected = { kind: "module", id: id };
    focus = id;
    render();
  }

  function selectSymbol(n) {
    selected = n;
    render();
  }

  function updateSelectPathBar() {
    const chip = document.getElementById("selectPath");
    if (!chip) return;
    const path = selectPathParts.length ? selectPathParts.join("") : "—";
    chip.textContent = path;
    chip.title = selectPathParts.length ? path : "在符号图中追加字段到 select 路径";
  }

  let planExpanded = false;

  function removeRenameOp(index) {
    draft.ops.splice(index, 1);
    if (draft.visual.edges) draft.visual.edges.splice(index, 1);
    renderPlanBar();
    render();
  }

  function clearPlan() {
    draft = { version: 1, id: "draft-" + Date.now(), kind: "architect_refactor", visual: { view, module: focus, edges: [] }, ops: [] };
    planExpanded = false;
    const drawer = document.getElementById("planDrawer");
    if (drawer) drawer.classList.remove("expanded");
    const chev = document.getElementById("planChev");
    if (chev) chev.textContent = "▲";
    renderPlanBar();
    render();
  }

  function expandPlanDrawer() {
    if (planExpanded) return;
    planExpanded = true;
    const drawer = document.getElementById("planDrawer");
    if (drawer) drawer.classList.add("expanded");
    const chev = document.getElementById("planChev");
    if (chev) chev.textContent = "▼";
  }

  function addRenameOp(moduleId, owner, from, to) {
    draft.ops.push({ op: "rename_symbol", kind: "field", module: moduleId, owner: owner, from: from, to: to, update_select_literals: true });
    draft.visual.edges.push({ from: owner + "." + from, to: owner + "." + to, kind: "rename" });
    draft.visual.module = moduleId;
    draft.visual.view = view;
    expandPlanDrawer();
    renderPlanBar();
    render();
  }

  function renderPlanBar() {
    const drawer = document.getElementById("planDrawer");
    const count = draft.ops.length;
    document.getElementById("planCount").textContent = String(count);
    if (drawer) {
      drawer.classList.toggle("has-ops", count > 0);
    }
    const list = document.getElementById("planList");
    if (!count) {
      list.innerHTML = '<span class="muted">从字段右侧橙色引脚拖到左侧蓝色引脚以 rename；右键节点打开菜单</span>';
      return;
    }
    list.innerHTML = draft.ops.map((op, i) => {
      let label = esc(op.op || "?");
      if (op.op === "rename_symbol") {
        label = "rename " + esc(op.owner || "") + "." + esc(op.from) + " → " + esc(op.to);
      } else if (op.op === "update_select_path") {
        label = "select " + esc(op.from) + " → " + esc(op.to);
      }
      return '<div class="plan-op">' + label
        + '<button class="rm" data-i="' + i + '" title="移除">×</button></div>';
    }).join("");
    list.querySelectorAll(".rm").forEach((btn) => {
      btn.onclick = (e) => { e.stopPropagation(); removeRenameOp(Number(btn.getAttribute("data-i"))); };
    });
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
    document.getElementById("btnBack").classList.toggle("active", view === "module");
    document.getElementById("btnDrill").classList.toggle("active", view === "symbol");
    document.getElementById("btnToggleFns").classList.toggle("active", showFunctions);
    if (view === "symbol") drawSymbolGraph();
    else drawModuleGraph();
    applyTransform();
    renderPlanBar();
  }

  // pan zoom
  let dragging = false, dragSx = 0, dragSy = 0, dragPx = 0, dragPy = 0;
  svg.addEventListener("mousedown", (e) => {
    if (e.target.classList && (e.target.classList.contains("pin") || e.target.classList.contains("pin-in") || e.target.classList.contains("pin-out"))) return;
    hideContextMenu();
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
      const pinIn = target && target.closest ? target.closest("[data-pin-in]") : null;
      if (pinIn && dragPin.owner) {
        const parts = pinIn.getAttribute("data-pin-in").split(".");
        const toOwner = parts[0], toField = parts.slice(1).join(".");
        if (toOwner === dragPin.owner && toField !== dragPin.field) {
          addRenameOp(dragPin.module, dragPin.owner, dragPin.field, toField);
        }
      } else if (dragPin.owner) {
        const newName = prompt("重命名字段 " + dragPin.owner + "." + dragPin.field + " 为:");
        if (newName && newName !== dragPin.field) {
          addRenameOp(dragPin.module, dragPin.owner, dragPin.field, newName);
        }
      }
      document.querySelectorAll(".pin-hot").forEach((p) => p.classList.remove("pin-hot"));
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
  document.getElementById("btnLoad").onclick = () => post("requestLoadPlan");
  document.getElementById("btnClearPlan").onclick = (e) => { e.stopPropagation(); clearPlan(); };
  document.getElementById("planToggle").onclick = (e) => {
    if (e.target.closest("#btnClearPlan")) return;
    planExpanded = !planExpanded;
    document.getElementById("planDrawer").classList.toggle("expanded", planExpanded);
    document.getElementById("planChev").textContent = planExpanded ? "▼" : "▲";
  };
  window.addEventListener("click", () => hideContextMenu());
  document.getElementById("btnToggleFns").onclick = () => { showFunctions = !showFunctions; fitPending = true; render(); };
  document.getElementById("btnCopySelect").onclick = () => {
    if (!selectPathParts.length) return;
    post("copyText", { text: selectPathParts.join("") });
  };
  document.getElementById("btnClearSelect").onclick = () => { selectPathParts = []; updateSelectPathBar(); };
  updateSelectPathBar();
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
