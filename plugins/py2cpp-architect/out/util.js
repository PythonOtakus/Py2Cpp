"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getGeneratedDir = exports.getPythonPath = exports.getConfig = exports.moduleIdFromPythonFile = exports.isArchitectPythonDocument = exports.findRepoRoot = void 0;
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
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
    return undefined;
}
exports.findRepoRoot = findRepoRoot;
function isArchitectPythonDocument(doc) {
    if (doc.isUntitled || !doc.uri.fsPath.endsWith(".py")) {
        return false;
    }
    const normalized = doc.uri.fsPath.replace(/\\/g, "/");
    return (PY2CPP_RE.test(normalized) ||
        TEST_RE.test(normalized) ||
        EXAMPLES_RE.test(normalized));
}
exports.isArchitectPythonDocument = isArchitectPythonDocument;
function moduleIdFromPythonFile(repoRoot, fsPath) {
    const rel = path.relative(repoRoot, fsPath).replace(/\\/g, "/");
    if (!rel.endsWith(".py")) {
        return undefined;
    }
    return rel.slice(0, -3);
}
exports.moduleIdFromPythonFile = moduleIdFromPythonFile;
function getConfig() {
    return vscode.workspace.getConfiguration("py2cpp-architect");
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
