"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.translatePythonFile = exports.shouldUseNoMain = exports.relativePyPath = void 0;
const child_process_1 = require("child_process");
const path = require("path");
const util_1 = require("./util");
function relativePyPath(repoRoot, fsPath) {
    return path.relative(repoRoot, fsPath).replace(/\\/g, "/");
}
exports.relativePyPath = relativePyPath;
function shouldUseNoMain(relPy) {
    const norm = relPy.replace(/\\/g, "/");
    if (norm.startsWith("py2cpp/")) {
        return true;
    }
    return false;
}
exports.shouldUseNoMain = shouldUseNoMain;
function translatePythonFile(repoRoot, fsPath) {
    const python = (0, util_1.getPythonPath)();
    const rel = relativePyPath(repoRoot, fsPath);
    const generatedDir = path.basename((0, util_1.getGeneratedDir)(repoRoot));
    const args = ["main.py", rel, "-o", generatedDir];
    if (shouldUseNoMain(rel)) {
        args.push("--no-main");
    }
    return new Promise((resolve, reject) => {
        const proc = (0, child_process_1.spawn)(python, args, {
            cwd: repoRoot,
            windowsHide: true,
        });
        let stderr = "";
        proc.stderr.on("data", (chunk) => {
            stderr += String(chunk);
        });
        proc.on("error", reject);
        proc.on("close", (code) => {
            if (code === 0) {
                resolve();
            }
            else {
                reject(new Error(stderr.trim() || `翻译失败 exit ${code}`));
            }
        });
    });
}
exports.translatePythonFile = translatePythonFile;
