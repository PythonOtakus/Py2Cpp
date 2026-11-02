"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MacroPairHighlightManager = void 0;
const vscode = require("vscode");
const macroPairs_1 = require("./macroPairs");
const util_1 = require("./util");
const LEVEL_COUNT = 3;
/** 由外向内：黄 → 紫 → 蓝（depth % 3） */
const MACRO_LEVEL_STYLES = [
    { border: "#CCA700", background: "rgba(204, 167, 0, 0.20)", color: "#E5C07B" },
    { border: "#9B59B6", background: "rgba(155, 89, 182, 0.20)", color: "#C586C0" },
    { border: "#3794FF", background: "rgba(55, 148, 255, 0.20)", color: "#569CD6" },
];
const MACRO_ACTIVE_STYLES = [
    { border: "#FFD700", background: "rgba(204, 167, 0, 0.38)", color: "#FFE566" },
    { border: "#BB86FC", background: "rgba(155, 89, 182, 0.38)", color: "#E1BEE7" },
    { border: "#61AFEF", background: "rgba(55, 148, 255, 0.38)", color: "#9CDCFE" },
];
class MacroPairHighlightManager {
    constructor() {
        this.disposables = [];
        this.levelDecorations = [];
        this.activeDecorations = [];
        for (let level = 0; level < LEVEL_COUNT; level += 1) {
            const style = MACRO_LEVEL_STYLES[level];
            this.levelDecorations.push(vscode.window.createTextEditorDecorationType({
                borderWidth: "0 0 0 3px",
                borderStyle: "solid",
                borderColor: style.border,
                backgroundColor: style.background,
                color: style.color,
            }));
            const active = MACRO_ACTIVE_STYLES[level];
            this.activeDecorations.push(vscode.window.createTextEditorDecorationType({
                borderWidth: "1px",
                borderStyle: "solid",
                borderColor: active.border,
                backgroundColor: active.background,
                color: active.color,
                fontWeight: "600",
                overviewRulerColor: active.border,
                overviewRulerLane: vscode.OverviewRulerLane.Center,
            }));
        }
        this.disposables.push(vscode.window.onDidChangeActiveTextEditor(() => this.scheduleRefresh()), vscode.window.onDidChangeTextEditorSelection(() => this.scheduleRefresh()), vscode.workspace.onDidChangeTextDocument((event) => {
            const editor = vscode.window.activeTextEditor;
            if (editor && event.document === editor.document) {
                this.scheduleRefresh();
            }
        }), vscode.workspace.onDidChangeConfiguration((event) => {
            if (event.affectsConfiguration("py2cpp-template.enableMacroPairs")) {
                this.scheduleRefresh();
            }
        }), ...this.levelDecorations, ...this.activeDecorations);
        this.scheduleRefresh();
    }
    dispose() {
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer);
        }
        for (const item of this.disposables) {
            item.dispose();
        }
    }
    refreshEditor(editor) {
        if (!editor || !this.isEnabled() || !(0, util_1.isTemplateDocument)(editor.document)) {
            return;
        }
        const pairs = (0, macroPairs_1.parseMacroPairs)(editor.document.getText());
        const activeLine = editor.selection.active.line;
        const activePair = (0, macroPairs_1.findEnclosingPair)(pairs, activeLine);
        const byLevel = [[], [], []];
        const activeByLevel = [[], [], []];
        for (const pair of pairs) {
            const level = pair.depth % LEVEL_COUNT;
            for (const line of [pair.openLine, pair.closeLine]) {
                const token = (0, macroPairs_1.macroTokenRange)(editor.document.lineAt(line).text, line);
                if (!token) {
                    continue;
                }
                const range = new vscode.Range(line, token.start, line, token.end);
                const isActivePair = activePair === pair;
                const isActiveDelimiter = !activePair &&
                    (0, macroPairs_1.lineIsMacroDelimiter)(pairs, activeLine) &&
                    (line === activeLine);
                if (isActivePair || isActiveDelimiter) {
                    activeByLevel[level].push(range);
                }
                else {
                    byLevel[level].push(range);
                }
            }
        }
        for (let level = 0; level < LEVEL_COUNT; level += 1) {
            editor.setDecorations(this.levelDecorations[level], byLevel[level]);
            editor.setDecorations(this.activeDecorations[level], activeByLevel[level]);
        }
    }
    refreshAllVisible() {
        if (!this.isEnabled()) {
            return;
        }
        for (const editor of vscode.window.visibleTextEditors) {
            this.refreshEditor(editor);
        }
    }
    isEnabled() {
        return (0, util_1.getConfig)().get("enableMacroPairs", true);
    }
    scheduleRefresh() {
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer);
        }
        this.refreshTimer = setTimeout(() => {
            this.refreshTimer = undefined;
            this.refreshAllVisible();
        }, 50);
    }
}
exports.MacroPairHighlightManager = MacroPairHighlightManager;
