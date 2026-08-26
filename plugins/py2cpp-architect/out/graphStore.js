"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.GraphStore = void 0;
const fs = require("fs");
const path = require("path");
const util_1 = require("./util");
const ARCH_PLAN_SUFFIX = ".arch.json";
class GraphStore {
    constructor() {
        this.graph = null;
    }
    graphPath(repoRoot) {
        return path.join((0, util_1.getGeneratedDir)(repoRoot), ".cache", "architect", "graph.json");
    }
    reload(repoRoot) {
        this.graph = null;
        const graphPath = this.graphPath(repoRoot);
        if (!fs.existsSync(graphPath)) {
            return false;
        }
        try {
            this.graph = JSON.parse(fs.readFileSync(graphPath, "utf-8"));
            return true;
        }
        catch {
            this.graph = null;
            return false;
        }
    }
    moduleIds() {
        if (!this.graph?.modules) {
            return [];
        }
        return Object.keys(this.graph.modules).sort();
    }
    moduleEntry(moduleId) {
        return this.graph?.modules?.[moduleId] ?? null;
    }
    outgoing(moduleId) {
        const entry = this.moduleEntry(moduleId);
        return entry?.imports ?? [];
    }
    incoming(moduleId) {
        const out = [];
        for (const id of this.moduleIds()) {
            if (this.outgoing(id).includes(moduleId)) {
                out.push(id);
            }
        }
        return out.sort();
    }
    moduleSymbols(moduleId) {
        return this.moduleEntry(moduleId)?.symbols ?? [];
    }
    refs() {
        return this.graph?.refs ?? [];
    }
    moduleRefs(moduleId) {
        return this.refs().filter((r) => {
            const f = r.from;
            const t = r.to;
            if (typeof f === "string" && (f === moduleId || t === moduleId)) {
                return true;
            }
            if (typeof f === "object" && f?.module === moduleId) {
                return true;
            }
            if (typeof t === "object" && t?.module === moduleId) {
                return true;
            }
            if (typeof t === "string" && t === moduleId) {
                return true;
            }
            return false;
        });
    }
    symbolRefs(moduleId) {
        return this.moduleRefs(moduleId).filter((r) => typeof r.from === "object" || typeof r.to === "object");
    }
    neighborhood(moduleId, hops = 1) {
        const nodes = new Set([moduleId]);
        let frontier = [moduleId];
        for (let h = 0; h < hops; h++) {
            const next = [];
            for (const id of frontier) {
                for (const dep of this.outgoing(id)) {
                    if (!nodes.has(dep)) {
                        nodes.add(dep);
                        next.push(dep);
                    }
                }
                for (const src of this.incoming(id)) {
                    if (!nodes.has(src)) {
                        nodes.add(src);
                        next.push(src);
                    }
                }
            }
            frontier = next;
        }
        return [...nodes].sort();
    }
    domainPrefix(moduleId) {
        const parts = moduleId.split("/");
        if (parts[0] === "py2cpp" && parts.length >= 2) {
            return `py2cpp/${parts[1]}`;
        }
        return parts[0] ?? moduleId;
    }
    modulesInDomain(prefix) {
        return this.moduleIds().filter((id) => id === prefix || id.startsWith(prefix + "/"));
    }
    pyFileAbs(repoRoot, moduleId) {
        const entry = this.moduleEntry(moduleId);
        const rel = entry?.pyFile ?? `${moduleId.replace(/\\/g, "/")}.py`;
        return path.join(repoRoot, rel.replace(/\//g, path.sep));
    }
    meta() {
        return {
            version: this.graph?.version ?? 0,
            updatedAt: this.graph?.updatedAt ?? "",
            moduleCount: this.moduleIds().length,
            planSuffix: this.graph?.planSuffix ?? ARCH_PLAN_SUFFIX,
        };
    }
    toJson() {
        return this.graph ?? { version: 0, modules: {}, refs: [] };
    }
}
exports.GraphStore = GraphStore;
