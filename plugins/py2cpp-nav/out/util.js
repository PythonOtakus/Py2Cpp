"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getGeneratedDir = exports.getPythonPath = exports.getConfig = exports.isGeneratedDocument = exports.isNavPythonDocument = exports.findRepoRoot = void 0;
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
const GENERATED_RE = /[/\\]generated[/\\]/i;
const PY2CPP_RE = /[/\\]py2cpp[/\\].+\.py$/i;
const TEST_RE = /[/\\]test[/\\].+\.py$/i;
const EXAMPLES_RE = /[/\\]examples[/\\].+\.py$/i;
function findRepoRoot() {
    const configured = getConfig().get("repoRoot", "").trim();
    if (configured && fs.existsSync(path.join(configured, "main.py"))) {
        return path.resolve(configured);
    }
    const folders = vscode.workspace.workspaceFolders ?? [];
    for (const folder of folders) {
        const root = folder.uri.fsPath;
        if (fs.existsSync(path.join(root, "main.py")) &&
            (fs.existsSync(path.join(root, "py2cpp")) || fs.existsSync(path.join(root, "templates")))) {
            return root;
        }
    }
    for (const folder of folders) {
        const hit = walkForRepoRoot(folder.uri.fsPath, 5);
        if (hit) {
            return hit;
        }
    }
    return undefined;
}
exports.findRepoRoot = findRepoRoot;
function walkForRepoRoot(start, maxDepth) {
    const queue = [{ dir: start, depth: 0 }];
    while (queue.length > 0) {
        const { dir, depth } = queue.shift();
        if (fs.existsSync(path.join(dir, "main.py")) &&
            (fs.existsSync(path.join(dir, "py2cpp")) || fs.existsSync(path.join(dir, "templates")))) {
            return dir;
        }
        if (depth >= maxDepth) {
            continue;
        }
        let entries;
        try {
            entries = fs.readdirSync(dir, { withFileTypes: true });
        }
        catch {
            continue;
        }
        for (const entry of entries) {
            if (!entry.isDirectory() || entry.name.startsWith(".")) {
                continue;
            }
            if (entry.name === "node_modules" || entry.name === ".git") {
                continue;
            }
            queue.push({ dir: path.join(dir, entry.name), depth: depth + 1 });
        }
    }
    return undefined;
}
function isNavPythonDocument(doc) {
    if (doc.isUntitled || !doc.uri.fsPath.endsWith(".py")) {
        return false;
    }
    const normalized = doc.uri.fsPath.replace(/\\/g, "/");
    return (PY2CPP_RE.test(normalized) ||
        TEST_RE.test(normalized) ||
        EXAMPLES_RE.test(normalized));
}
exports.isNavPythonDocument = isNavPythonDocument;
function isGeneratedDocument(doc) {
    if (doc.isUntitled) {
        return false;
    }
    const normalized = doc.uri.fsPath.replace(/\\/g, "/");
    if (!GENERATED_RE.test(normalized)) {
        return false;
    }
    return /\.(h|hpp|cpp|inl)$/i.test(normalized);
}
exports.isGeneratedDocument = isGeneratedDocument;
function getConfig() {
    return vscode.workspace.getConfiguration("py2cpp-nav");
}
exports.getConfig = getConfig;
function getPythonPath() {
    return getConfig().get("pythonPath", "python");
}
exports.getPythonPath = getPythonPath;
function getGeneratedDir(repoRoot) {
    const rel = getConfig().get("generatedDir", "generated").replace(/\\/g, "/").replace(/^\/+/, "");
    return path.join(repoRoot, rel);
}
exports.getGeneratedDir = getGeneratedDir;
