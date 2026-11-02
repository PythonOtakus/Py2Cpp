"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.lineIsMacroDelimiter = exports.findEnclosingPair = exports.macroTokenRange = exports.parseMacroPairs = void 0;
const BEGIN_RE = /^\s*PY2CPP_BEGIN\s*\(\s*(.*?)\s*\)\s*$/;
const END_RE = /^\s*PY2CPP_END\s*$/;
const INJECT_CLASS_RE = /^\s*PY2CPP_INJECT_CLASS\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$/;
const IGNORE_RE = /^\s*PY2CPP_IGNORE\s*$/;
const BEGIN_SCOPE_RE = /^\s*PY2CPP_BEGIN_SCOPE\s*$/;
const END_SCOPE_RE = /^\s*PY2CPP_END_SCOPE\s*$/;
const MACRO_HEAD_RE = /\bPY2CPP_(?:BEGIN(?:_SCOPE)?|END(?:_SCOPE)?|IGNORE|INJECT_CLASS)\b/;
function parseMacroPairs(text) {
    const lines = text.split(/\r?\n/);
    const pairs = [];
    const endStack = [];
    const scopeStack = [];
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (IGNORE_RE.test(line)) {
            const depth = endStack.length + scopeStack.length;
            endStack.push({ kind: "ignore", line: i, depth, label: "IGNORE" });
            continue;
        }
        const injectMatch = line.match(INJECT_CLASS_RE);
        if (injectMatch) {
            const depth = endStack.length + scopeStack.length;
            endStack.push({
                kind: "inject",
                line: i,
                depth,
                label: `INJECT_CLASS(${injectMatch[1]})`,
            });
            continue;
        }
        const beginMatch = line.match(BEGIN_RE);
        if (beginMatch) {
            const depth = endStack.length + scopeStack.length;
            const header = beginMatch[1].trim();
            endStack.push({
                kind: "begin",
                line: i,
                depth,
                label: `BEGIN(${header})`,
            });
            continue;
        }
        if (END_RE.test(line)) {
            if (endStack.length > 0) {
                const frame = endStack.pop();
                pairs.push({
                    openKind: frame.kind,
                    openLine: frame.line,
                    closeLine: i,
                    depth: frame.depth,
                    label: frame.label,
                });
            }
            continue;
        }
        if (BEGIN_SCOPE_RE.test(line)) {
            const depth = endStack.length + scopeStack.length;
            scopeStack.push({ line: i, depth });
            continue;
        }
        if (END_SCOPE_RE.test(line)) {
            if (scopeStack.length > 0) {
                const frame = scopeStack.pop();
                pairs.push({
                    openKind: "scope",
                    openLine: frame.line,
                    closeLine: i,
                    depth: frame.depth,
                    label: "BEGIN_SCOPE",
                });
            }
        }
    }
    return pairs;
}
exports.parseMacroPairs = parseMacroPairs;
function macroTokenRange(lineText, _lineNumber) {
    const match = lineText.match(MACRO_HEAD_RE);
    if (!match || match.index === undefined) {
        return undefined;
    }
    return {
        start: match.index,
        end: lineText.trimEnd().length,
    };
}
exports.macroTokenRange = macroTokenRange;
function findEnclosingPair(pairs, line) {
    return pairs.find((pair) => line >= pair.openLine && line <= pair.closeLine);
}
exports.findEnclosingPair = findEnclosingPair;
function lineIsMacroDelimiter(pairs, line) {
    return pairs.some((pair) => line === pair.openLine || line === pair.closeLine);
}
exports.lineIsMacroDelimiter = lineIsMacroDelimiter;
