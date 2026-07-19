"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseCppContext = exports.parsePythonContext = exports.getWordRange = exports.getWordAt = void 0;
const vscode = require("vscode");
function getWordAt(line, character) {
    const identRe = /[A-Za-z_][A-Za-z0-9_]*/g;
    let match;
    while ((match = identRe.exec(line)) !== null) {
        const start = match.index;
        const end = start + match[0].length;
        if (character >= start && character <= end) {
            return match[0];
        }
    }
    return undefined;
}
exports.getWordAt = getWordAt;
function getWordRange(document, position) {
    const line = document.lineAt(position.line).text;
    const identRe = /[A-Za-z_][A-Za-z0-9_]*/g;
    let match;
    while ((match = identRe.exec(line)) !== null) {
        const start = match.index;
        const end = start + match[0].length;
        if (position.character >= start && position.character <= end) {
            return new vscode.Range(position.line, start, position.line, end);
        }
    }
    return undefined;
}
exports.getWordRange = getWordRange;
function parsePythonContext(document, position) {
    const lineText = document.lineAt(position.line).text;
    const word = getWordAt(lineText, position.character);
    if (!word) {
        return undefined;
    }
    const trimmed = lineText.trim();
    const assignLhs = isAssignLhs(lineText, word);
    // ``type Element = …`` / ``type Element[T] = …``
    if (/^type\s+/.test(trimmed)) {
        const m = trimmed.match(/^type\s+([A-Za-z_][A-Za-z0-9_]*)/);
        if (m && m[1] === word) {
            const owner = findEnclosingClass(document, position.line);
            return { kind: "type_alias", name: word, owner, preferSetter: false };
        }
    }
    if (/^class\s+/.test(trimmed)) {
        const m = trimmed.match(/^class\s+([A-Za-z_][A-Za-z0-9_]*)/);
        if (m && m[1] === word) {
            return { kind: "class", name: word, preferSetter: false };
        }
    }
    if (/^def\s+/.test(trimmed)) {
        const m = trimmed.match(/^def\s+([A-Za-z_][A-Za-z0-9_]*)/);
        if (m && m[1] === word) {
            const owner = findEnclosingClass(document, position.line);
            if (owner) {
                return { kind: "method", name: word, owner, preferSetter: false };
            }
            return { kind: "function", name: word, preferSetter: false };
        }
    }
    // ``AggMode.Min`` / ``Result.Ok`` / ``Matrix3.zero`` / ``new.Ok``
    const qual = qualifyBeforeDot(lineText, word);
    if (qual) {
        if (qual === "new" || qual === "Self") {
            return {
                kind: "variant",
                name: word,
                owner: undefined,
                receiver: qual,
                preferSetter: assignLhs,
            };
        }
        return {
            kind: "qualified",
            name: word,
            owner: qual,
            preferSetter: assignLhs,
        };
    }
    const owner = findEnclosingClass(document, position.line);
    if (owner && /^[A-Za-z_][A-Za-z0-9_]*\s*:/.test(trimmed)) {
        const m = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*:/);
        if (m && m[1] === word) {
            return { kind: "field", name: word, owner, preferSetter: false };
        }
    }
    if (owner) {
        return { kind: "member", name: word, owner, preferSetter: assignLhs };
    }
    return { kind: "reference", name: word, preferSetter: assignLhs };
}
exports.parsePythonContext = parsePythonContext;
function isAssignLhs(lineText, word) {
    // ``self.capacity =`` / ``x.foo =``；排除 ``==`` / ``!=`` / ``<=`` 等
    const re = new RegExp(`(?:^|[^A-Za-z0-9_])${escapeRegExp(word)}\\s*=(?!=)`);
    return re.test(lineText);
}
function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function qualifyBeforeDot(lineText, word) {
    const re = new RegExp(`([A-Za-z_][A-Za-z0-9_]*)\\s*\\.\\s*${escapeRegExp(word)}(?:\\b|$)`);
    const m = lineText.match(re);
    return m ? m[1] : undefined;
}
function findEnclosingClass(document, fromLine) {
    const effectiveIndent = effectiveLineIndent(document, fromLine);
    for (let line = fromLine; line >= 0; line -= 1) {
        const text = document.lineAt(line).text;
        const m = text.match(/^(\s*)class\s+([A-Za-z_][A-Za-z0-9_]*)/);
        if (!m) {
            continue;
        }
        const classIndent = m[1].length;
        if (line === fromLine || classIndent < effectiveIndent) {
            return m[2];
        }
    }
    return undefined;
}
function effectiveLineIndent(document, fromLine) {
    for (let line = fromLine; line >= 0; line -= 1) {
        const text = document.lineAt(line).text;
        if (!text.trim()) {
            continue;
        }
        return text.match(/^(\s*)/)?.[1].length ?? 0;
    }
    return 0;
}
function parseCppContext(document, position) {
    const lineText = document.lineAt(position.line).text;
    const word = getWordAt(lineText, position.character);
    if (!word) {
        return undefined;
    }
    // ``capacity__get`` / ``capacity__set`` → Python property ``capacity``
    const propSuffix = word.match(/^(.+)__(get|set|postset)$/);
    if (propSuffix) {
        return {
            kind: "property",
            name: propSuffix[1],
            cppName: word,
            role: propSuffix[2] === "get" ? "getter" : propSuffix[2] === "set" ? "setter" : "postsetter",
        };
    }
    const scopeMatch = lineText.match(/([A-Za-z_][A-Za-z0-9_:]*(?:::[A-Za-z_][A-Za-z0-9_]*)*)\s*::\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|$|,|=)/);
    if (scopeMatch) {
        const parts = scopeMatch[1].split("::").filter(Boolean);
        const method = scopeMatch[2];
        const owner = parts.length > 0 ? parts[parts.length - 1] : undefined;
        if (word === method) {
            // ``AggMode::Min`` / ``Enum::Ok``
            if (!/\(/.test(lineText.slice(lineText.indexOf(method))) || /,\s*$/.test(lineText.trim()) || /=\s*\d/.test(lineText)) {
                return { kind: "enum_member", name: method, owner, cppQual: `${scopeMatch[1]}::${method}` };
            }
            return { kind: "method", name: method, owner, cppQual: scopeMatch[1] };
        }
        if (word === owner) {
            return { kind: "class", name: owner, cppQual: scopeMatch[1] };
        }
    }
    if (/\benum\s+class\s+/.test(lineText)) {
        const m = lineText.match(/\benum\s+class\s+([A-Za-z_][A-Za-z0-9_]*)/);
        if (m && m[1] === word) {
            return { kind: "class", name: word, role: "enum" };
        }
    }
    if (/\b(class|struct)\s+/.test(lineText)) {
        const m = lineText.match(/\b(?:class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)/);
        if (m && m[1] === word) {
            return { kind: "class", name: word };
        }
    }
    if (/\busing\s+/.test(lineText)) {
        const m = lineText.match(/\busing\s+([A-Za-z_][A-Za-z0-9_]*)\s*=/);
        if (m && m[1] === word) {
            return { kind: "type_alias", name: word };
        }
    }
    // 枚举成员行：``Min = 0,`` / ``Ok,``
    if (/^\s*[A-Za-z_][A-Za-z0-9_]*\s*(?:=|,)/.test(lineText.trim()) && word === lineText.trim().match(/^([A-Za-z_][A-Za-z0-9_]*)/)?.[1]) {
        return { kind: "enum_member", name: word };
    }
    const qualMatch = lineText.match(/([A-Za-z_][A-Za-z0-9_:]*(?:::[A-Za-z_][A-Za-z0-9_]*)*)\s*::\s*([A-Za-z_][A-Za-z0-9_]*)/);
    if (qualMatch && word === qualMatch[2]) {
        const parts = qualMatch[1].split("::");
        return {
            kind: "method",
            name: word,
            owner: parts[parts.length - 1],
            cppQual: qualMatch[1],
        };
    }
    return { kind: "reference", name: word };
}
exports.parseCppContext = parseCppContext;
