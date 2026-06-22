"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Py2CppDefinitionProvider = void 0;
const path = require("path");
const vscode = require("vscode");
const indexStore_1 = require("./indexStore");
const symbolParse_1 = require("./symbolParse");
const util_1 = require("./util");
class Py2CppDefinitionProvider {
    constructor(store) {
        this.store = store;
    }
    provideDefinition(document, position) {
        const repoRoot = (0, util_1.findRepoRoot)();
        if (!repoRoot) {
            return undefined;
        }
        if (!(0, util_1.isNavPythonDocument)(document) && !(0, util_1.isGeneratedDocument)(document)) {
            return undefined;
        }
        if (!this.store.manifest) {
            this.store.reload(repoRoot);
        }
        if (!this.store.manifest) {
            return undefined;
        }
        if ((0, util_1.isNavPythonDocument)(document)) {
            return this.pythonToCpp(repoRoot, document, position);
        }
        return this.cppToPython(repoRoot, document, position);
    }
    pythonToCpp(repoRoot, document, position) {
        const ctx = (0, symbolParse_1.parsePythonContext)(document, position);
        if (!ctx) {
            return undefined;
        }
        const relPy = path.relative(repoRoot, document.uri.fsPath).replace(/\\/g, "/");
        let modulePath = this.store.moduleForDocument(repoRoot, document.uri.fsPath);
        if (!modulePath) {
            modulePath = this.store.moduleForDocument(repoRoot, relPy);
        }
        if (!modulePath) {
            modulePath = relPy.replace(/\.py$/, "");
        }
        const query = { pyName: ctx.name, owner: ctx.owner };
        if (ctx.kind === "class") {
            query.kind = "class";
            delete query.owner;
        }
        else if (ctx.kind === "function") {
            query.kind = "function";
            delete query.owner;
        }
        else if (ctx.kind === "method") {
            query.kind = "method";
        }
        else if (ctx.kind === "field") {
            query.kind = "field";
        }
        else {
            query.kind = "member";
        }
        let symbols = this.store.findSymbols(repoRoot, modulePath, query);
        if (symbols.length === 0 && query.owner) {
            symbols = this.store.findSymbols(repoRoot, modulePath, {
                ...query,
                owner: undefined,
            });
        }
        if (symbols.length === 0) {
            symbols = this.fallbackSymbols(repoRoot, modulePath, ctx, query);
        }
        symbols = this.rankSymbols(symbols, modulePath, query);
        if (symbols.length === 0) {
            return undefined;
        }
        const pref = (0, util_1.getConfig)().get("jumpPreference", "implementation");
        const locations = [];
        for (const sym of symbols) {
            const symModule = sym.module ?? modulePath;
            locations.push(...this.cppTargets(repoRoot, symModule, sym, pref));
        }
        return locations.length > 0 ? locations : undefined;
    }
    fallbackSymbols(repoRoot, modulePath, ctx, query) {
        const shards = this.store.allShards(repoRoot);
        const prefer = modulePath
            ? shards.filter((s) => s.module === modulePath)
            : [];
        const rest = modulePath
            ? shards.filter((s) => s.module !== modulePath)
            : shards;
        const pick = (scope, useOwner) => {
            const matches = [];
            for (const shard of scope) {
                for (const sym of shard.symbols) {
                    if (sym.name !== ctx.name && sym.cppName !== ctx.name) {
                        continue;
                    }
                    if (useOwner && query.owner && sym.owner && sym.owner !== query.owner) {
                        continue;
                    }
                    matches.push(sym);
                }
            }
            return matches;
        };
        let matches = pick(prefer, true);
        if (matches.length === 0) {
            matches = pick(prefer, false);
        }
        if (matches.length === 0) {
            matches = pick(rest, true);
        }
        if (matches.length === 0) {
            matches = pick(rest, false);
        }
        return matches;
    }
    rankSymbols(symbols, modulePath, query) {
        if (symbols.length <= 1) {
            return symbols;
        }
        const scored = symbols.map((sym, index) => {
            let score = index;
            if (modulePath && sym.module === modulePath) {
                score -= 1000;
            }
            if (query.owner && sym.owner === query.owner) {
                score -= 100;
            }
            return { sym, score };
        });
        scored.sort((a, b) => a.score - b.score);
        const best = scored[0].score;
        return scored.filter((entry) => entry.score === best).map((entry) => entry.sym);
    }
    cppToPython(repoRoot, document, position) {
        const ctx = (0, symbolParse_1.parseCppContext)(document, position);
        if (!ctx) {
            return undefined;
        }
        const modulePath = this.store.moduleForDocument(repoRoot, document.uri.fsPath);
        const searchShards = [];
        if (modulePath) {
            const shard = this.store.loadShard(repoRoot, modulePath);
            if (shard) {
                searchShards.push(shard);
            }
        }
        if (searchShards.length === 0) {
            searchShards.push(...this.store.allShards(repoRoot));
        }
        const matches = [];
        for (const shard of searchShards) {
            for (const sym of shard.symbols) {
                if (ctx.kind === "class" && sym.kind === "class") {
                    if (sym.cppName === ctx.name || sym.name === ctx.name) {
                        matches.push(sym);
                    }
                    continue;
                }
                if (sym.cppName === ctx.name || sym.name === ctx.name) {
                    if (ctx.owner && sym.owner && sym.owner !== ctx.owner) {
                        const ownerSym = shard.symbols.find((s) => s.kind === "class" && (s.cppName === ctx.owner || s.name === ctx.owner));
                        if (ownerSym && sym.owner !== ownerSym.name) {
                            continue;
                        }
                    }
                    matches.push(sym);
                }
            }
        }
        if (matches.length === 0) {
            return undefined;
        }
        const locations = [];
        for (const sym of matches) {
            const pyFile = sym.py?.file;
            const line = sym.py?.line;
            if (!pyFile || !line) {
                continue;
            }
            const abs = path.isAbsolute(pyFile)
                ? pyFile
                : path.join(repoRoot, pyFile.replace(/\//g, path.sep));
            locations.push(new vscode.Location(vscode.Uri.file(abs), new vscode.Position(line - 1, 0)));
        }
        return locations.length > 0 ? locations : undefined;
    }
    cppTargets(repoRoot, modulePath, sym, pref) {
        const shard = this.store.loadShard(repoRoot, modulePath);
        const artifactMap = shard?.artifacts ?? {};
        const out = [];
        const add = (rel, site) => {
            if (!rel || !site?.line) {
                return;
            }
            const abs = path.join(repoRoot, rel.replace(/\//g, path.sep));
            out.push(new vscode.Location(vscode.Uri.file(abs), new vscode.Position(site.line - 1, 0)));
        };
        const decl = sym.cpp?.decl ? { line: sym.cpp.decl.line } : undefined;
        const impl = sym.cpp?.impl ? { line: sym.cpp.impl.line } : undefined;
        if (pref === "implementation") {
            add(artifactMap.inl, impl);
            add(artifactMap.cpp, impl);
            add(artifactMap.h, decl);
        }
        else if (pref === "declaration") {
            add(artifactMap.h, decl);
            add(artifactMap.inl, impl);
            add(artifactMap.cpp, impl);
        }
        else {
            add(artifactMap.h, decl);
            add(artifactMap.inl, impl);
            add(artifactMap.cpp, impl);
        }
        return out;
    }
}
exports.Py2CppDefinitionProvider = Py2CppDefinitionProvider;
