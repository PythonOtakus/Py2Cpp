"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DataclassSchemaPanel = void 0;
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const planRunner_1 = require("./planRunner");
const util_1 = require("./util");
const ARCH_PLAN_SUFFIX = ".arch.json";
class DataclassSchemaPanel {
    static createOrShow(repoRoot, store, moduleId, className) {
        const column = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.Beside;
        if (DataclassSchemaPanel.current) {
            DataclassSchemaPanel.current.panel.reveal(column);
            DataclassSchemaPanel.current.update(moduleId, className);
            return;
        }
        const panel = vscode.window.createWebviewPanel("py2cppDataclassSchema", "Py2Cpp Dataclass Schema", column, {
            enableScripts: true,
            retainContextWhenHidden: true,
            localResourceRoots: [],
        });
        DataclassSchemaPanel.current = new DataclassSchemaPanel(panel, repoRoot, store);
        DataclassSchemaPanel.current.update(moduleId, className);
    }
    constructor(panel, repoRoot, store) {
        this.disposables = [];
        this.repoRoot = repoRoot;
        this.store = store;
        this.moduleId = "";
        this.className = "";
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
        DataclassSchemaPanel.current = undefined;
        while (this.disposables.length) {
            const d = this.disposables.pop();
            d?.dispose();
        }
    }
    plansDir() {
        return path.join((0, util_1.getGeneratedDir)(this.repoRoot), ".cache", "architect", "plans");
    }
    async onMessage(msg) {
        if (msg.type === "openModule") {
            const abs = this.store.pyFileAbs(this.repoRoot, msg.moduleId);
            const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(abs));
            await vscode.window.showTextDocument(doc, { preview: true });
            return;
        }
        if (msg.type === "previewPlan" && msg.plan) {
            await this.checkPlan(msg.plan);
        }
        if (msg.type === "savePlan" && msg.plan) {
            await this.savePlan(msg.plan);
        }
        if (msg.type === "applyPlan" && msg.plan) {
            await this.applyPlan(msg.plan);
        }
    }
    async savePlan(plan) {
        const dir = this.plansDir();
        fs.mkdirSync(dir, { recursive: true });
        const id = plan.id || `schema-${Date.now()}`;
        const file = path.join(dir, `${id}${ARCH_PLAN_SUFFIX}`);
        fs.writeFileSync(file, JSON.stringify(plan, null, 2), "utf8");
        void vscode.window.showInformationMessage(`已保存 ${path.basename(file)}`);
    }
    async checkPlan(plan) {
        const tmp = path.join(this.plansDir(), `_schema_preview_${Date.now()}${ARCH_PLAN_SUFFIX}`);
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
        const tmp = path.join(this.plansDir(), `_schema_apply_${Date.now()}${ARCH_PLAN_SUFFIX}`);
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
            const ok = await vscode.window.showWarningMessage("应用字段变更并写回源文件？", { modal: true }, "应用");
            if (ok !== "应用") {
                return;
            }
            await (0, planRunner_1.applyRefactorPlan)(this.repoRoot, tmp);
            void vscode.window.showInformationMessage("Schema 变更已应用。");
            this.store.reload(this.repoRoot);
            this.update(this.moduleId, this.className);
        }
        finally {
            try {
                fs.unlinkSync(tmp);
            }
            catch { /* ignore */ }
        }
    }
    update(moduleId, className) {
        this.moduleId = moduleId;
        this.className = className;
        const fields = this.store.classFields(moduleId, className);
        const meta = this.store.meta();
        this.panel.webview.html = this.renderHtml(meta, moduleId, className, fields);
    }
    renderHtml(meta, moduleId, className, fields) {
        const payload = JSON.stringify({ meta, moduleId, className, fields });
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';" />
<style>
  html, body { height: 100%; margin: 0; font-family: var(--vscode-font-family); font-size: 14px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
  .wrap { display: flex; flex-direction: column; height: 100%; padding: 12px 16px; box-sizing: border-box; }
  h2 { margin: 0 0 4px; font-size: 16px; }
  .path { color: var(--vscode-descriptionForeground); font-size: 12px; margin-bottom: 12px; word-break: break-all; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { border-bottom: 1px solid var(--vscode-panel-border); padding: 8px 6px; text-align: left; vertical-align: middle; }
  th { color: var(--vscode-descriptionForeground); font-weight: 600; font-size: 12px; }
  input[type=text] { width: 100%; box-sizing: border-box; padding: 5px 8px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; }
  .toolbar { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
  button { padding: 6px 12px; font-size: 13px; border-radius: 4px; border: 1px solid var(--vscode-panel-border); cursor: pointer; background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); }
  button.primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
  button:hover { filter: brightness(1.05); }
  .plan { margin-top: 12px; padding: 10px; border: 1px solid var(--vscode-panel-border); border-radius: 6px; font-size: 12px; max-height: 120px; overflow: auto; }
  .muted { color: var(--vscode-descriptionForeground); }
</style>
</head>
<body>
<div class="wrap">
  <h2 id="title"></h2>
  <div class="path" id="path"></div>
  <table>
    <thead><tr><th>字段</th><th>类型</th><th>重命名为</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <div class="toolbar">
    <button class="primary" id="btnBuild">生成 rename 计划</button>
    <button id="btnPreview">预览 diff</button>
    <button id="btnSave">保存 .arch.json</button>
    <button class="primary" id="btnApply">应用</button>
    <button id="btnOpen">打开源文件</button>
  </div>
  <div class="plan muted" id="planBox">尚未生成计划。</div>
</div>
<script>
(function() {
  const vscode = acquireVsCodeApi();
  const DATA = ${payload};
  let plan = null;

  function esc(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  function post(type, extra) { vscode.postMessage(Object.assign({ type }, extra || {})); }

  document.getElementById("title").textContent = DATA.className;
  document.getElementById("path").textContent = DATA.moduleId + " · graph v" + DATA.meta.version;

  const tbody = document.getElementById("rows");
  if (!DATA.fields.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="muted">无字段（或 graph 未索引）</td></tr>';
  } else {
    tbody.innerHTML = DATA.fields.map((f, i) =>
      '<tr data-idx="' + i + '"><td><code>' + esc(f.name) + '</code></td><td class="muted">' + esc(f.typeAnn || "—") + '</td>'
      + '<td><input type="text" data-from="' + esc(f.name) + '" placeholder="留空表示不改" /></td></tr>'
    ).join("");
  }

  function buildPlan() {
    const ops = [];
    const edges = [];
    tbody.querySelectorAll("input[type=text]").forEach((inp) => {
      const from = inp.getAttribute("data-from");
      const to = inp.value.trim();
      if (!to || to === from) return;
      ops.push({
        op: "rename_symbol",
        kind: "field",
        module: DATA.moduleId,
        owner: DATA.className,
        from: from,
        to: to,
        update_select_literals: true,
      });
      edges.push({ from: DATA.className + "." + from, to: DATA.className + "." + to, kind: "rename" });
    });
    if (!ops.length) {
      document.getElementById("planBox").textContent = "无字段重命名。";
      plan = null;
      return;
    }
    plan = {
      version: 1,
      id: "schema-" + DATA.className + "-" + Date.now(),
      kind: "architect_refactor",
      visual: { view: "schema", module: DATA.moduleId, class: DATA.className, edges },
      ops,
    };
    document.getElementById("planBox").innerHTML = ops.map((op, i) =>
      (i + 1) + ". " + esc(op.owner) + "." + esc(op.from) + " → " + esc(op.to)
    ).join("<br>");
  }

  document.getElementById("btnBuild").onclick = buildPlan;
  document.getElementById("btnPreview").onclick = () => { buildPlan(); if (plan) post("previewPlan", { plan }); };
  document.getElementById("btnSave").onclick = () => { buildPlan(); if (plan) post("savePlan", { plan }); };
  document.getElementById("btnApply").onclick = () => { buildPlan(); if (plan) post("applyPlan", { plan }); };
  document.getElementById("btnOpen").onclick = () => post("openModule", { moduleId: DATA.moduleId });
})();
</script>
</body>
</html>`;
    }
}
exports.DataclassSchemaPanel = DataclassSchemaPanel;
DataclassSchemaPanel.current = undefined;
