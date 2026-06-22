"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode = require("vscode");
const macroDocumentHighlight_1 = require("./macroDocumentHighlight");
const macroFolding_1 = require("./macroFolding");
const macroHighlight_1 = require("./macroHighlight");
const hoverProvider_1 = require("./hoverProvider");
const lintRunner_1 = require("./lintRunner");
const util_1 = require("./util");
const DIAGNOSTIC_SOURCE = "py2cpp-template";
let diagnosticCollection;
let macroPairHighlight;
let lintTimer;
let lintVersion = 0;
function activate(context) {
    diagnosticCollection = vscode.languages.createDiagnosticCollection(DIAGNOSTIC_SOURCE);
    context.subscriptions.push(diagnosticCollection);
    const selector = [
        { scheme: "file", pattern: "**/templates/**/*.h" },
        { scheme: "file", pattern: "**/templates/**/*.inl" },
    ];
    context.subscriptions.push(vscode.languages.registerHoverProvider(selector, new hoverProvider_1.TemplateHoverProvider()));
    macroPairHighlight = new macroHighlight_1.MacroPairHighlightManager();
    context.subscriptions.push(macroPairHighlight);
    context.subscriptions.push(vscode.languages.registerDocumentHighlightProvider(selector, new macroDocumentHighlight_1.MacroDocumentHighlightProvider()));
    context.subscriptions.push(vscode.languages.registerFoldingRangeProvider(selector, new macroFolding_1.MacroFoldingProvider()));
    context.subscriptions.push(vscode.workspace.onDidOpenTextDocument((doc) => {
        if ((0, util_1.isTemplateDocument)(doc)) {
            macroPairHighlight?.refreshAllVisible();
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand("py2cpp-template.lintCurrentFile", () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || !(0, util_1.isTemplateDocument)(editor.document)) {
            void vscode.window.showWarningMessage("当前文件不是 templates/ 下的 .h/.inl 模板。");
            return;
        }
        void lintDocument(editor.document, true);
    }));
    context.subscriptions.push(vscode.commands.registerCommand("py2cpp-template.lintWorkspace", () => {
        void lintAllTemplates(true);
    }));
    context.subscriptions.push(vscode.workspace.onDidOpenTextDocument((doc) => {
        if (shouldLint(doc)) {
            scheduleLint(doc);
        }
    }));
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument((event) => {
        if (shouldLint(event.document)) {
            scheduleLint(event.document);
        }
    }));
    context.subscriptions.push(vscode.workspace.onDidSaveTextDocument((doc) => {
        if (shouldLint(doc)) {
            void lintDocument(doc, false);
        }
    }));
    context.subscriptions.push(vscode.workspace.onDidCloseTextDocument((doc) => {
        diagnosticCollection.delete(doc.uri);
    }));
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration("py2cpp-template")) {
            void refreshAllOpenTemplates();
        }
    }));
    for (const doc of vscode.workspace.textDocuments) {
        if (shouldLint(doc)) {
            scheduleLint(doc);
        }
    }
}
exports.activate = activate;
function deactivate() {
    if (lintTimer) {
        clearTimeout(lintTimer);
    }
    macroPairHighlight?.dispose();
    macroPairHighlight = undefined;
    diagnosticCollection?.clear();
}
exports.deactivate = deactivate;
function shouldLint(doc) {
    if (!(0, util_1.getConfig)().get("enableDiagnostics", true)) {
        return false;
    }
    return (0, util_1.isTemplateDocument)(doc);
}
function scheduleLint(doc) {
    if (lintTimer) {
        clearTimeout(lintTimer);
    }
    lintTimer = setTimeout(() => {
        lintTimer = undefined;
        void lintDocument(doc, false);
    }, 500);
}
async function refreshAllOpenTemplates() {
    const docs = vscode.workspace.textDocuments.filter(shouldLint);
    for (const doc of docs) {
        await lintDocument(doc, false);
    }
}
async function lintDocument(doc, showErrors) {
    const repoRoot = (0, util_1.findRepoRoot)();
    if (!repoRoot) {
        if (showErrors) {
            void vscode.window.showErrorMessage("未找到 Py2Cpp 仓库根（需含 main.py 与 templates/）。可在设置中指定 py2cpp-template.repoRoot。");
        }
        return;
    }
    const version = ++lintVersion;
    try {
        const result = await (0, lintRunner_1.runTemplateLint)(repoRoot, doc.uri.fsPath);
        if (version !== lintVersion) {
            return;
        }
        const diagnostics = (0, lintRunner_1.violationsToDiagnostics)(result.violations, doc);
        diagnosticCollection.set(doc.uri, diagnostics);
    }
    catch (err) {
        if (version !== lintVersion) {
            return;
        }
        diagnosticCollection.set(doc.uri, []);
        const message = err instanceof Error ? err.message : String(err);
        if (showErrors) {
            void vscode.window.showErrorMessage(`Py2Cpp 模板 lint 失败: ${message}`);
        }
    }
}
async function lintAllTemplates(showSummary) {
    const repoRoot = (0, util_1.findRepoRoot)();
    if (!repoRoot) {
        void vscode.window.showErrorMessage("未找到 Py2Cpp 仓库根。请打开 Py2Cpp 工作区或设置 py2cpp-template.repoRoot。");
        return;
    }
    await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Py2Cpp: 正在检查 templates/ …",
        cancellable: false,
    }, async () => {
        try {
            const result = await (0, lintRunner_1.runTemplateLint)(repoRoot);
            const openDocs = new Map(vscode.workspace.textDocuments
                .filter(shouldLint)
                .map((doc) => [doc.uri.fsPath.replace(/\\/g, "/").toLowerCase(), doc]));
            for (const doc of openDocs.values()) {
                diagnosticCollection.delete(doc.uri);
            }
            const grouped = new Map();
            for (const v of result.violations) {
                const key = v.file.replace(/\\/g, "/").toLowerCase();
                const bucket = grouped.get(key) ?? [];
                bucket.push(v);
                grouped.set(key, bucket);
            }
            for (const [fileKey, violations] of grouped) {
                const doc = openDocs.get(fileKey);
                if (!doc) {
                    continue;
                }
                diagnosticCollection.set(doc.uri, (0, lintRunner_1.violationsToDiagnostics)(violations, doc));
            }
            const errors = result.violations.filter((v) => v.severity === "error");
            const warnings = result.violations.filter((v) => v.severity === "warning");
            if (showSummary) {
                void vscode.window.showInformationMessage(`模板检查完成：${errors.length} 个 error，${warnings.length} 个 warning（已打开文件已更新诊断）。`);
            }
        }
        catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            void vscode.window.showErrorMessage(`Py2Cpp 模板 lint 失败: ${message}`);
        }
    });
}
