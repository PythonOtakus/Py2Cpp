"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.violationsToDiagnostics = exports.runTemplateLint = void 0;
const child_process_1 = require("child_process");
const path = __importStar(require("path"));
const vscode = __importStar(require("vscode"));
const util_1 = require("./util");
async function runTemplateLint(repoRoot, filePath) {
    const extensionRoot = path.resolve(__dirname, "..");
    const scriptPath = path.join(extensionRoot, "python", "lint_cli.py");
    const pythonPath = (0, util_1.getPythonPath)();
    const args = [scriptPath, "--repo", repoRoot, "--json"];
    if (!(0, util_1.getIncludeWarnings)()) {
        args.push("--no-warnings");
    }
    if (filePath) {
        args.push("--file", filePath);
    }
    return new Promise((resolve, reject) => {
        const child = (0, child_process_1.spawn)(pythonPath, args, {
            cwd: repoRoot,
            windowsHide: true,
        });
        let stdout = "";
        let stderr = "";
        child.stdout.on("data", (chunk) => {
            stdout += chunk.toString();
        });
        child.stderr.on("data", (chunk) => {
            stderr += chunk.toString();
        });
        child.on("error", (err) => {
            reject(err);
        });
        child.on("close", (code) => {
            const trimmed = stdout.trim();
            if (!trimmed) {
                reject(new Error(`lint_cli 无输出 (exit ${code ?? "?"}): ${stderr.trim() || pythonPath}`));
                return;
            }
            try {
                const parsed = JSON.parse(trimmed);
                if (!parsed.ok && parsed.error) {
                    reject(new Error(parsed.error));
                    return;
                }
                resolve(parsed);
            }
            catch (err) {
                reject(new Error(`lint_cli JSON 解析失败: ${err instanceof Error ? err.message : String(err)}\n${trimmed}`));
            }
        });
    });
}
exports.runTemplateLint = runTemplateLint;
function violationsToDiagnostics(violations, document) {
    const out = [];
    for (const v of violations) {
        const line = Math.max(0, (v.line ?? 1) - 1);
        if (line >= document.lineCount) {
            continue;
        }
        const lineText = document.lineAt(line).text;
        const range = new vscode.Range(line, 0, line, lineText.length || 1);
        const diag = new vscode.Diagnostic(range, `[${v.rule}] ${v.message}`, v.severity === "warning"
            ? vscode.DiagnosticSeverity.Warning
            : vscode.DiagnosticSeverity.Error);
        diag.source = "py2cpp-template";
        diag.code = v.rule;
        out.push(diag);
    }
    return out;
}
exports.violationsToDiagnostics = violationsToDiagnostics;
