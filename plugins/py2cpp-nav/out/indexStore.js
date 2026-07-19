"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NavIndexStore = void 0;
const fs = require("fs");
const path = require("path");
const util_1 = require("./util");
class NavIndexStore {
    constructor() {
        this.manifest = null;
        this.shardCache = new Map();
        this.fileToModule = new Map();
    }
    getManifestPath(repoRoot) {
        const generated = (0, util_1.getGeneratedDir)(repoRoot);
        return path.join(generated, ".cache", "nav", "manifest.json");
    }
    reload(repoRoot) {
        this.manifest = null;
        this.shardCache.clear();
        this.fileToModule.clear();
        const manifestPath = this.getManifestPath(repoRoot);
        if (!fs.existsSync(manifestPath)) {
            return false;
        }
        try {
            this.manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
        }
        catch {
            this.manifest = null;
            return false;
        }
        for (const [modulePath, entry] of Object.entries(this.manifest.modules ?? {})) {
            const arts = entry.artifacts ?? {};
            for (const rel of [arts.h, arts.inl, arts.cpp, entry.pyFile]) {
                if (!rel) {
                    continue;
                }
                this.fileToModule.set(this.normalizeKey(repoRoot, rel), modulePath);
            }
        }
        return true;
    }
    normalizeKey(repoRoot, relPath) {
        const abs = path.isAbsolute(relPath)
            ? relPath
            : path.join(repoRoot, relPath.replace(/\//g, path.sep));
        return abs.replace(/\\/g, "/").toLowerCase();
    }
    moduleForDocument(repoRoot, docPath) {
        const key = this.normalizeKey(repoRoot, docPath);
        if (this.fileToModule.has(key)) {
            return this.fileToModule.get(key);
        }
        if (!this.manifest) {
            return undefined;
        }
        const norm = docPath.replace(/\\/g, "/").toLowerCase();
        for (const [modulePath, entry] of Object.entries(this.manifest.modules ?? {})) {
            const py = entry.pyFile?.replace(/\\/g, "/").toLowerCase();
            if (py && norm.endsWith(py)) {
                return modulePath;
            }
            for (const art of Object.values(entry.artifacts ?? {})) {
                if (art && norm.endsWith(String(art).replace(/\\/g, "/").toLowerCase())) {
                    return modulePath;
                }
            }
        }
        return undefined;
    }
    loadShard(repoRoot, modulePath) {
        if (this.shardCache.has(modulePath)) {
            return this.shardCache.get(modulePath);
        }
        const entry = this.manifest?.modules?.[modulePath];
        const shardRel = entry?.shard ?? `modules/${modulePath.replace(/\\/g, "/")}.json`;
        const shardPath = path.join((0, util_1.getGeneratedDir)(repoRoot), ".cache", "nav", shardRel.replace(/\//g, path.sep));
        if (!fs.existsSync(shardPath)) {
            const legacy = path.join((0, util_1.getGeneratedDir)(repoRoot), ".cache", "nav", "modules", modulePath.replace(/[/\\]/g, "__") + ".json");
            if (fs.existsSync(legacy)) {
                try {
                    const shard = JSON.parse(fs.readFileSync(legacy, "utf-8"));
                    this.shardCache.set(modulePath, shard);
                    return shard;
                }
                catch {
                    return undefined;
                }
            }
            return undefined;
        }
        try {
            const shard = JSON.parse(fs.readFileSync(shardPath, "utf-8"));
            this.shardCache.set(modulePath, shard);
            return shard;
        }
        catch {
            return undefined;
        }
    }
    findSymbols(repoRoot, modulePath, query) {
        const shard = this.loadShard(repoRoot, modulePath);
        if (!shard) {
            return [];
        }
        const memberKinds = new Set([
            "method",
            "field",
            "property",
            "type_alias",
            "enum_member",
            "variant",
            "delegate",
        ]);
        const classLike = new Set(["class", "protocol", "mixin", "descriptor", "delegate"]);
        return shard.symbols.filter((sym) => {
            if (query.kind) {
                if (query.kind === "member") {
                    if (!memberKinds.has(sym.kind)) {
                        return false;
                    }
                }
                else if (query.kind === "method") {
                    if (sym.kind !== "method" && sym.kind !== "property") {
                        return false;
                    }
                }
                else if (query.kind === "class") {
                    if (!classLike.has(sym.kind)) {
                        return false;
                    }
                }
                else if (query.kind === "function") {
                    if (sym.kind !== "function" && sym.kind !== "delegate") {
                        return false;
                    }
                }
                else if (sym.kind !== query.kind) {
                    return false;
                }
            }
            if (query.owner && sym.owner && sym.owner !== query.owner) {
                return false;
            }
            if (query.pyName && sym.name !== query.pyName && sym.cppName !== query.pyName) {
                return false;
            }
            if (query.cppName && sym.cppName !== query.cppName && sym.name !== query.cppName) {
                return false;
            }
            if (query.cppQual && sym.cppQual && !query.cppQual.endsWith(sym.cppQual)) {
                return false;
            }
            return true;
        });
    }
    allShards(repoRoot) {
        if (!this.manifest?.modules) {
            return [];
        }
        const out = [];
        for (const modulePath of Object.keys(this.manifest.modules)) {
            const shard = this.loadShard(repoRoot, modulePath);
            if (shard) {
                out.push(shard);
            }
        }
        return out;
    }
}
exports.NavIndexStore = NavIndexStore;
