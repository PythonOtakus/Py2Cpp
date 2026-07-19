"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Py2CppDefinitionProvider = void 0;
const path = require("path");
const vscode = require("vscode");
const indexStore_1 = require("./indexStore");
const symbolParse_1 = require("./symbolParse");
const util_1 = require("./util");

/** member / qualified 查询可命中的索引 kind */
const MEMBER_KINDS = new Set([
    "method",
    "field",
    "property",
    "type_alias",
    "enum_member",
    "variant",
    "delegate",
]);

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
        const query = {
            pyName: ctx.name,
            owner: ctx.owner,
            preferSetter: !!ctx.preferSetter,
        };
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
        else if (ctx.kind === "type_alias") {
            query.kind = "type_alias";
        }
        else if (ctx.kind === "variant") {
            query.kind = "variant";
            delete query.owner;
        }
        else if (ctx.kind === "qualified") {
            query.kind = "member";
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
        symbols = this.rankSymbols(symbols, modulePath, query, ctx);
        // protocol / mixin 仅 Python：无 C++ 目标时回跳自身定义
        const locations = [];
        for (const sym of symbols) {
            const symModule = sym.module ?? modulePath;
            const cppLocs = this.cppTargets(repoRoot, symModule, sym, (0, util_1.getConfig)().get("jumpPreference", "implementation"));
            if (cppLocs.length > 0) {
                locations.push(...cppLocs);
            }
            else if (sym.kind === "protocol" || sym.kind === "mixin" || sym.role === "protocol" || sym.role === "mixin") {
                const pyLoc = this.pyLocation(repoRoot, sym);
                if (pyLoc) {
                    locations.push(pyLoc);
                }
            }
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
    rankSymbols(symbols, modulePath, query, ctx) {
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
            // 限定名：``AggMode.Min`` 优先 enum_member；``Result.Ok`` 优先 variant
            if (ctx?.kind === "qualified" || ctx?.kind === "variant") {
                if (sym.kind === "variant") {
                    score -= 50;
                }
                if (sym.kind === "enum_member") {
                    score -= 40;
                }
                if (sym.kind === "property" && sym.role === "getter") {
                    score -= 30;
                }
                if (sym.kind === "type_alias") {
                    score -= 20;
                }
            }
            // F4：赋值左值优先 setter；否则 getter
            if (sym.kind === "property") {
                if (query.preferSetter) {
                    if (sym.role === "setter") {
                        score -= 80;
                    }
                    else if (sym.role === "getter") {
                        score += 20;
                    }
                }
                else if (sym.role === "getter") {
                    score -= 40;
                }
                else if (sym.role === "setter") {
                    score += 10;
                }
            }
            return { sym, score };
        });
        scored.sort((a, b) => a.score - b.score);
        // Q5：overload 全部保留（同分）；property getter/setter 在 prefer 后只留最优一类
        const best = scored[0].score;
        let kept = scored.filter((entry) => entry.score === best).map((entry) => entry.sym);
        if (query.preferSetter) {
            const setters = kept.filter((s) => s.kind === "property" && s.role === "setter");
            if (setters.length > 0) {
                kept = setters;
            }
        }
        else if (kept.some((s) => s.kind === "property" && s.role === "getter")) {
            // 读位点：若有 getter 则去掉同名 setter，避免双跳
            const hasGetter = kept.some((s) => s.role === "getter");
            if (hasGetter && !query.preferSetter) {
                kept = kept.filter((s) => !(s.kind === "property" && s.role === "setter"));
            }
        }
        return kept;
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
                if (ctx.kind === "class" && (sym.kind === "class" || sym.kind === "protocol" || sym.kind === "mixin" || sym.kind === "delegate" || sym.kind === "descriptor")) {
                    if (sym.cppName === ctx.name || sym.name === ctx.name) {
                        matches.push(sym);
                    }
                    continue;
                }
                if (ctx.kind === "type_alias" && sym.kind === "type_alias") {
                    if (sym.name === ctx.name || sym.cppName === ctx.name) {
                        matches.push(sym);
                    }
                    continue;
                }
                if (ctx.kind === "property") {
                    if (sym.kind === "property" && (sym.name === ctx.name || sym.cppName === ctx.cppName)) {
                        if (ctx.role && sym.role && sym.role !== ctx.role) {
                            continue;
                        }
                        matches.push(sym);
                    }
                    continue;
                }
                if (ctx.kind === "enum_member") {
                    if ((sym.kind === "enum_member" || sym.kind === "variant") &&
                        (sym.name === ctx.name || sym.cppName === ctx.name)) {
                        if (ctx.owner && sym.owner && sym.owner !== ctx.owner) {
                            const ownerSym = shard.symbols.find((s) => (s.kind === "class" || s.kind === "delegate") &&
                                (s.cppName === ctx.owner || s.name === ctx.owner));
                            if (ownerSym && sym.owner !== ownerSym.name) {
                                continue;
                            }
                        }
                        matches.push(sym);
                    }
                    continue;
                }
                if (sym.cppName === ctx.name || sym.name === ctx.name || sym.cppName === ctx.cppName) {
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
            const pyLoc = this.pyLocation(repoRoot, sym);
            if (pyLoc) {
                locations.push(pyLoc);
            }
        }
        return locations.length > 0 ? locations : undefined;
    }
    pyLocation(repoRoot, sym) {
        const pyFile = sym.py?.file;
        const line = sym.py?.line;
        if (!pyFile || !line) {
            return undefined;
        }
        const abs = path.isAbsolute(pyFile)
            ? pyFile
            : path.join(repoRoot, pyFile.replace(/\//g, path.sep));
        return new vscode.Location(vscode.Uri.file(abs), new vscode.Position(line - 1, 0));
    }
    cppTargets(repoRoot, modulePath, sym, pref) {
        let shard = this.store.loadShard(repoRoot, modulePath);
        // mixin 方法可能指向宿主模块生成物
        const implModule = sym.cpp?.implModule;
        if (implModule && implModule !== modulePath) {
            const hostShard = this.store.loadShard(repoRoot, implModule);
            if (hostShard) {
                shard = hostShard;
            }
        }
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
        const tag = sym.cpp?.tag ? { line: sym.cpp.tag.line } : undefined;
        const payload = sym.cpp?.payload ? { line: sym.cpp.payload.line } : undefined;
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
            // both：含 variant tag/payload 附加锚点
            add(artifactMap.h, decl);
            add(artifactMap.inl, impl);
            add(artifactMap.cpp, impl);
            add(artifactMap.h, tag);
            add(artifactMap.h, payload);
        }
        return out;
    }
}
exports.Py2CppDefinitionProvider = Py2CppDefinitionProvider;
