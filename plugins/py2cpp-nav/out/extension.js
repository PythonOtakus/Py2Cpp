"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode = require("vscode");
const definitionProvider_1 = require("./definitionProvider");
const indexStore_1 = require("./indexStore");
const translateRunner_1 = require("./translateRunner");
const util_1 = require("./util");
const store = new indexStore_1.NavIndexStore();
let translateTimer;
let translateVersion = 0;
function activate(context) {
    const repoRoot = (0, util_1.findRepoRoot)();
    if (repoRoot) {
        store.reload(repoRoot);
    }
    const selector = [
        { scheme: "file", pattern: "**/generated/**/*.h" },
        { scheme: "file", pattern: "**/generated/**/*.hpp" },
        { scheme: "file", pattern: "**/generated/**/*.cpp" },
        { scheme: "file", pattern: "**/generated/**/*.inl" },
        { scheme: "file", pattern: "**/py2cpp/**/*.py" },
        { scheme: "file", pattern: "**/test/**/*.py" },
        { scheme: "file", pattern: "**/examples/**/*.py" },
    ];
    context.subscriptions.push(vscode.languages.registerDefinitionProvider(selector, new definitionProvider_1.Py2CppDefinitionProvider(store)));
    const navWatcher = vscode.workspace.createFileSystemWatcher("**/generated/.cache/nav/**");
    navWatcher.onDidChange(() => {
        const root = (0, util_1.findRepoRoot)();
        if (root) {
            store.reload(root);
        }
    });
    navWatcher.onDidCreate(() => {
        const root = (0, util_1.findRepoRoot)();
        if (root) {
            store.reload(root);
        }
    });
    context.subscriptions.push(navWatcher);
    context.subscriptions.push(vscode.workspace.onDidSaveTextDocument((doc) => {
        if ((0, util_1.getConfig)().get("autoTranslate", "onSave") !== "onSave") {
            return;
        }
        if (!(0, util_1.isNavPythonDocument)(doc)) {
            return;
        }
        scheduleTranslate(doc);
    }));
    context.subscriptions.push(vscode.commands.registerCommand("py2cpp-nav.translateCurrentFile", () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || !(0, util_1.isNavPythonDocument)(editor.document)) {
            void vscode.window.showWarningMessage("当前文件不是可翻译的 Py2Cpp Python 源。");
            return;
        }
        void runTranslate(editor.document, true);
    }));
    context.subscriptions.push(vscode.commands.registerCommand("py2cpp-nav.rebuildIndex", () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || !(0, util_1.isNavPythonDocument)(editor.document)) {
            void vscode.window.showWarningMessage("请打开 py2cpp/、test/ 或 examples/ 下的 .py 文件。");
            return;
        }
        void runTranslate(editor.document, true);
    }));
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration("py2cpp-nav.repoRoot") ||
            event.affectsConfiguration("py2cpp-nav.generatedDir")) {
            const root = (0, util_1.findRepoRoot)();
            if (root) {
                store.reload(root);
            }
        }
    }));
}
exports.activate = activate;
function deactivate() {
    if (translateTimer) {
        clearTimeout(translateTimer);
    }
}
exports.deactivate = deactivate;
function scheduleTranslate(doc) {
    if (translateTimer) {
        clearTimeout(translateTimer);
    }
    const debounce = (0, util_1.getConfig)().get("translateDebounceMs", 1000);
    translateTimer = setTimeout(() => {
        translateTimer = undefined;
        void runTranslate(doc, false);
    }, debounce);
}
async function runTranslate(doc, showErrors) {
    const repoRoot = (0, util_1.findRepoRoot)();
    if (!repoRoot) {
        if (showErrors) {
            void vscode.window.showErrorMessage("未找到 Py2Cpp 仓库根。请设置 py2cpp-nav.repoRoot。");
        }
        return;
    }
    const version = ++translateVersion;
    try {
        await (0, translateRunner_1.translatePythonFile)(repoRoot, doc.uri.fsPath);
        if (version !== translateVersion) {
            return;
        }
        store.reload(repoRoot);
    }
    catch (err) {
        if (version !== translateVersion) {
            return;
        }
        const message = err instanceof Error ? err.message : String(err);
        if (showErrors) {
            void vscode.window.showErrorMessage(`Py2Cpp 翻译失败: ${message}`);
        }
    }
}
