"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const architectCanvasPanel_1 = require("./architectCanvasPanel");
const graphStore_1 = require("./graphStore");
const planRunner_1 = require("./planRunner");
const util_1 = require("./util");
const ARCH_PLAN_SUFFIX = ".arch.json";
const graphStore = new graphStore_1.GraphStore();
function reloadGraph(repoRoot) {
    return graphStore.reload(repoRoot);
}
function showGraph(repoRoot, focusModule) {
    if (!reloadGraph(repoRoot)) {
        void vscode.window.showWarningMessage("未找到 graph.json。请先运行 bootstrap 或翻译任意 py2cpp/test .py。");
        return;
    }
    architectCanvasPanel_1.ArchitectCanvasPanel.createOrShow(repoRoot, graphStore, focusModule);
}
function activate(context) {
    const tryGraphReload = () => {
        const root = (0, util_1.findRepoRoot)();
        if (root) {
            reloadGraph(root);
        }
    };
    context.subscriptions.push(vscode.commands.registerCommand("py2cpp-architect.showModuleGraph", () => {
        const repoRoot = (0, util_1.findRepoRoot)();
        if (!repoRoot) {
            void vscode.window.showWarningMessage("未找到 Py2Cpp 仓库根（含 main.py）。");
            return;
        }
        const editor = vscode.window.activeTextEditor;
        let focus;
        if (editor && (0, util_1.isArchitectPythonDocument)(editor.document)) {
            focus = (0, util_1.moduleIdFromPythonFile)(repoRoot, editor.document.uri.fsPath);
        }
        showGraph(repoRoot, focus);
    }));
    const graphWatcher = vscode.workspace.createFileSystemWatcher("**/generated/.cache/architect/**");
    graphWatcher.onDidChange(tryGraphReload);
    graphWatcher.onDidCreate(tryGraphReload);
    context.subscriptions.push(graphWatcher);
    context.subscriptions.push(vscode.commands.registerCommand("py2cpp-architect.applyRefactorPlan", async () => {
        const repoRoot = (0, util_1.findRepoRoot)();
        if (!repoRoot) {
            void vscode.window.showWarningMessage("未找到 Py2Cpp 仓库根（含 main.py）。");
            return;
        }
        const pick = await vscode.window.showOpenDialog({
            canSelectMany: false,
            filters: { "Architect Plan": ["arch.json"], JSON: ["json"] },
            title: "选择 RefactorPlan（*.arch.json）",
        });
        if (!pick || pick.length === 0) {
            return;
        }
        const planPath = pick[0].fsPath;
        try {
            const diff = await (0, planRunner_1.checkRefactorPlan)(repoRoot, planPath);
            if (!diff.trim()) {
                void vscode.window.showInformationMessage("计划无变更。");
                return;
            }
            const doc = await vscode.workspace.openTextDocument({
                content: diff,
                language: "diff",
            });
            await vscode.window.showTextDocument(doc, { preview: true });
            const apply = await vscode.window.showWarningMessage("应用 RefactorPlan 并写回源文件？", { modal: true }, "应用");
            if (apply !== "应用") {
                return;
            }
            await (0, planRunner_1.applyRefactorPlan)(repoRoot, planPath);
            void vscode.window.showInformationMessage("RefactorPlan 已应用。");
            if ((0, util_1.getConfig)().get("autoValidate", "onApply") === "onApply") {
                const editor = vscode.window.activeTextEditor;
                if (editor && (0, util_1.isArchitectPythonDocument)(editor.document)) {
                    await (0, planRunner_1.translateCurrentFile)(repoRoot, editor.document.uri.fsPath);
                }
            }
        }
        catch (err) {
            void vscode.window.showErrorMessage(String(err?.message ?? err));
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand("py2cpp-architect.renameSymbol", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || !(0, util_1.isArchitectPythonDocument)(editor.document)) {
            void vscode.window.showWarningMessage("请在 py2cpp/、test/ 或 examples/ 下的 .py 中选中标识符。");
            return;
        }
        const repoRoot = (0, util_1.findRepoRoot)();
        if (!repoRoot) {
            void vscode.window.showWarningMessage("未找到 Py2Cpp 仓库根。");
            return;
        }
        const wordRange = editor.document.getWordRangeAtPosition(editor.selection.active, /[A-Za-z_][A-Za-z0-9_]*/);
        if (!wordRange) {
            void vscode.window.showWarningMessage("请将光标置于要重命名的标识符上。");
            return;
        }
        const oldName = editor.document.getText(wordRange);
        const newName = await vscode.window.showInputBox({
            prompt: `将 ${oldName} 重命名为`,
            value: oldName,
            validateInput: (v) => {
                if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(v)) {
                    return "非法标识符";
                }
                if (v === oldName) {
                    return "新名称须不同";
                }
                return undefined;
            },
        });
        if (!newName) {
            return;
        }
        const kind = await vscode.window.showQuickPick([
            { label: "field", description: "类字段（须指定 owner）" },
            { label: "method", description: "类方法（须指定 owner）" },
            { label: "class", description: "类名" },
            { label: "function", description: "模块级函数" },
        ], { title: "符号种类" });
        if (!kind) {
            return;
        }
        let owner;
        if (kind.label === "field" || kind.label === "method") {
            owner = await vscode.window.showInputBox({
                prompt: "所属类名 (owner)",
                validateInput: (v) => (!v?.trim() ? "必填" : undefined),
            });
            if (!owner) {
                return;
            }
        }
        const rel = (0, util_1.moduleIdFromPythonFile)(repoRoot, editor.document.uri.fsPath) ?? "";
        const op = {
            op: "rename_symbol",
            kind: kind.label,
            module: rel,
            from: oldName,
            to: newName,
        };
        if (owner) {
            op.owner = owner;
        }
        const plan = {
            version: 1,
            id: `rename-${oldName}-${Date.now()}`,
            kind: "architect_refactor",
            visual: {
                view: "symbol",
                module: rel,
                edges: [{ from: `${owner ?? ""}.${oldName}`, to: `${owner ?? ""}.${newName}`, kind: "rename" }],
            },
            ops: [op],
        };
        const cacheDir = path.join(repoRoot, (0, util_1.getConfig)().get("generatedDir", "generated"), ".cache", "architect", "plans");
        fs.mkdirSync(cacheDir, { recursive: true });
        const planPath = path.join(cacheDir, `${plan.id}${ARCH_PLAN_SUFFIX}`);
        fs.writeFileSync(planPath, JSON.stringify(plan, null, 2), "utf8");
        try {
            const diff = await (0, planRunner_1.checkRefactorPlan)(repoRoot, planPath);
            const doc = await vscode.workspace.openTextDocument({ content: diff || "(无 diff)", language: "diff" });
            await vscode.window.showTextDocument(doc, { preview: true });
            const apply = await vscode.window.showWarningMessage("应用重命名？", { modal: true }, "应用");
            if (apply === "应用") {
                await (0, planRunner_1.applyRefactorPlan)(repoRoot, planPath);
                await (0, planRunner_1.translateCurrentFile)(repoRoot, editor.document.uri.fsPath);
                void vscode.window.showInformationMessage(`已重命名 ${oldName} → ${newName}`);
            }
        }
        catch (err) {
            void vscode.window.showErrorMessage(String(err?.message ?? err));
        }
    }));
}
exports.activate = activate;
function deactivate() { }
exports.deactivate = deactivate;
