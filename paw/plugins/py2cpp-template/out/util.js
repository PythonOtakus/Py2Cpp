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
exports.getIncludeWarnings = exports.getPythonPath = exports.getConfig = exports.isTemplateDocument = void 0;
exports.findRepoRoot = findRepoRoot;
exports.severityToDiagnostic = severityToDiagnostic;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const vscode = __importStar(require("vscode"));
const TEMPLATE_PATH_RE = /[/\\]templates[/\\].+\.(h|inl)$/i;
function isTemplateDocument(doc) {
    if (doc.isUntitled) {
        return false;
    }
    const normalized = doc.uri.fsPath.replace(/\\/g, "/");
    if (normalized.includes("/~macro/")) {
        return false;
    }
    return TEMPLATE_PATH_RE.test(normalized);
}
exports.isTemplateDocument = isTemplateDocument;
function getConfig() {
    return vscode.workspace.getConfiguration("py2cpp-template");
}
exports.getConfig = getConfig;
function getPythonPath() {
    return getConfig().get("pythonPath", "python");
}
exports.getPythonPath = getPythonPath;
function getIncludeWarnings() {
    return getConfig().get("includeWarnings", true);
}
exports.getIncludeWarnings = getIncludeWarnings;
function findRepoRoot() {
    const configured = getConfig().get("repoRoot", "").trim();
    if (configured && fs.existsSync(path.join(configured, "main.py"))) {
        return path.resolve(configured);
    }
    const folders = vscode.workspace.workspaceFolders ?? [];
    for (const folder of folders) {
        const root = folder.uri.fsPath;
        if (fs.existsSync(path.join(root, "main.py")) &&
            fs.existsSync(path.join(root, "templates"))) {
            return root;
        }
    }
    for (const folder of folders) {
        const hit = walkForRepoRoot(folder.uri.fsPath, 4);
        if (hit) {
            return hit;
        }
    }
    return undefined;
}
function walkForRepoRoot(start, maxDepth) {
    const queue = [{ dir: start, depth: 0 }];
    while (queue.length > 0) {
        const { dir, depth } = queue.shift();
        if (fs.existsSync(path.join(dir, "main.py")) &&
            fs.existsSync(path.join(dir, "templates"))) {
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
            if (entry.name === "node_modules" || entry.name === "generated") {
                continue;
            }
            queue.push({ dir: path.join(dir, entry.name), depth: depth + 1 });
        }
    }
    return undefined;
}
function severityToDiagnostic(severity) {
    return severity === "warning"
        ? vscode.DiagnosticSeverity.Warning
        : vscode.DiagnosticSeverity.Error;
}
