"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.applyRefactorPlan = exports.checkRefactorPlan = exports.translateCurrentFile = void 0;
const child_process_1 = require("child_process");
const path = require("path");
const util_1 = require("./util");
function runScript(repoRoot, args) {
    const python = (0, util_1.getPythonPath)();
    const script = path.join(repoRoot, "scripts", "apply_refactor_plan.py");
    return new Promise((resolve, reject) => {
        const proc = (0, child_process_1.spawn)(python, [script, ...args], {
            cwd: repoRoot,
            windowsHide: true,
        });
        let stdout = "";
        let stderr = "";
        proc.stdout.on("data", (c) => {
            stdout += String(c);
        });
        proc.stderr.on("data", (c) => {
            stderr += String(c);
        });
        proc.on("error", reject);
        proc.on("close", (code) => {
            if (code === 0) {
                resolve(stdout);
            }
            else {
                reject(new Error(stderr.trim() || stdout.trim() || `exit ${code}`));
            }
        });
    });
}
async function translateCurrentFile(repoRoot, fsPath) {
    const python = (0, util_1.getPythonPath)();
    const rel = path.relative(repoRoot, fsPath).replace(/\\/g, "/");
    const generatedDir = path.basename((0, util_1.getGeneratedDir)(repoRoot));
    const args = ["main.py", rel, "-o", generatedDir];
    if (rel.startsWith("py2cpp/")) {
        args.push("--no-main");
    }
    return new Promise((resolve, reject) => {
        const proc = (0, child_process_1.spawn)(python, args, { cwd: repoRoot, windowsHide: true });
        let stderr = "";
        proc.stderr.on("data", (c) => {
            stderr += String(c);
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
exports.translateCurrentFile = translateCurrentFile;
function checkRefactorPlan(repoRoot, planPath) {
    return runScript(repoRoot, [planPath, "--check"]);
}
exports.checkRefactorPlan = checkRefactorPlan;
function applyRefactorPlan(repoRoot, planPath) {
    return runScript(repoRoot, [planPath, "--apply"]);
}
exports.applyRefactorPlan = applyRefactorPlan;
