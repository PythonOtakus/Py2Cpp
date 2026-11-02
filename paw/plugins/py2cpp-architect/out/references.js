"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.openReference = exports.collectReferences = void 0;
const vscode = require("vscode");
const path = require("path");
function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
async function findTextUsages(repoRoot, symbol) {
    const pattern = new RegExp(`\\b${escapeRegExp(symbol)}\\b`, "g");
    const roots = ["py2cpp", "test", "examples"];
    const hits = [];
    for (const rel of roots) {
        const rootPath = path.join(repoRoot, rel);
        const glob = new vscode.RelativePattern(vscode.Uri.file(rootPath), "**/*.py");
        const files = await vscode.workspace.findFiles(glob, "**/generated/**", 500);
        for (const uri of files) {
            const doc = await vscode.workspace.openTextDocument(uri);
            const text = doc.getText();
            for (const match of text.matchAll(pattern)) {
                const offset = match.index ?? 0;
                const pos = doc.positionAt(offset);
                hits.push({
                    direction: "text",
                    kind: "text_match",
                    moduleId: path.relative(repoRoot, uri.fsPath).replace(/\\/g, "/").replace(/\.py$/, ""),
                    detail: `行 ${pos.line + 1}`,
                    uri,
                    position: pos,
                });
            }
        }
    }
    return hits;
}
async function collectReferences(repoRoot, store, moduleId, symbol, kind, owner) {
    const graphHits = store.refsForSymbol(moduleId, symbol, kind, owner);
    const seen = new Set();
    const items = [];
    const push = (item) => {
        const key = `${item.label}|${item.description}|${item.detail}`;
        if (seen.has(key)) {
            return;
        }
        seen.add(key);
        items.push(item);
    };
    for (const hit of graphHits) {
        push({
            label: hit.moduleId || "(unknown)",
            description: `${hit.kind} · ${hit.direction}`,
            detail: hit.detail,
            hit,
        });
    }
    const textHits = await findTextUsages(repoRoot, symbol);
    for (const hit of textHits) {
        push({
            label: hit.moduleId,
            description: `${hit.kind} · ${hit.direction}`,
            detail: hit.detail,
            hit,
        });
    }
    return items;
}
exports.collectReferences = collectReferences;
async function openReference(repoRoot, store, hit) {
    if (hit.uri && hit.position) {
        const doc = await vscode.workspace.openTextDocument(hit.uri);
        const editor = await vscode.window.showTextDocument(doc, { preview: true });
        const range = new vscode.Range(hit.position, hit.position);
        editor.selection = new vscode.Selection(range.start, range.end);
        editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
        return;
    }
    const moduleId = hit.moduleId;
    if (!moduleId) {
        return;
    }
    const abs = store.pyFileAbs(repoRoot, moduleId);
    const uri = vscode.Uri.file(abs);
    const doc = await vscode.workspace.openTextDocument(uri);
    const editor = await vscode.window.showTextDocument(doc, { preview: true });
    const text = doc.getText();
    const needle = hit.ref?.kind === "select_path"
        ? ".select("
        : (hit.detail?.split(".").pop() ?? "");
    if (!needle) {
        return;
    }
    const index = text.indexOf(needle);
    if (index < 0) {
        return;
    }
    const pos = doc.positionAt(index);
    const range = new vscode.Range(pos, pos.translate(0, needle.length));
    editor.selection = new vscode.Selection(range.start, range.end);
    editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
}
exports.openReference = openReference;
