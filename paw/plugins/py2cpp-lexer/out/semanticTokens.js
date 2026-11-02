"use strict";

const TOKEN_TYPES = Object.freeze([
    "comment", "string", "number", "keyword", "type", "function", "variable", "operator",
]);
const TOKEN_MODIFIERS = Object.freeze(["readonly"]);
const LEXER_TYPES = new Map([
    ["plain", null],
    ["comment", [0, 0]],
    ["string", [1, 0]],
    ["number", [2, 0]],
    ["keyword", [3, 0]],
    ["type", [4, 0]],
    ["function", [5, 0]],
    ["constant", [6, 1]],
    ["operator", [7, 0]],
]);

/** Convert ordered gpu-lexer UTF-16 spans to VS Code's delta-encoded token data. */
function encodeSemanticTokens(source, spans) {
    if (typeof source !== "string") {
        throw new TypeError("Semantic token source must be a string");
    }
    if (!Array.isArray(spans)) {
        throw new TypeError("Semantic token spans must be an array");
    }

    let previousEnd = 0;
    for (let index = 0; index < spans.length; index++) {
        const span = spans[index];
        if (!span || typeof span !== "object" || Array.isArray(span)) {
            throw new TypeError(`Invalid semantic token span at index ${index}`);
        }
        if (!Number.isInteger(span.start) || !Number.isInteger(span.end) ||
            span.start < 0 || span.end < span.start || span.end > source.length) {
            throw new RangeError(`Invalid UTF-16 span bounds at index ${index}`);
        }
        if (span.start < previousEnd) {
            throw new RangeError(`Semantic token spans overlap or are unordered at index ${index}`);
        }
        if (!LEXER_TYPES.has(span.type)) {
            throw new TypeError(`Invalid lexer token type at index ${index}`);
        }
        previousEnd = span.end;
    }

    if (source.length === 0 || spans.length === 0) {
        return new Uint32Array(0);
    }

    // Ends exclude newline characters; starts retain UTF-16 offsets, including both CRLF units.
    const lineStarts = [0];
    const lineEnds = [];
    for (let offset = 0; offset < source.length; offset++) {
        const code = source.charCodeAt(offset);
        if (code === 10 || code === 13) {
            lineEnds.push(offset);
            if (code === 13 && source.charCodeAt(offset + 1) === 10) {
                offset++;
            }
            lineStarts.push(offset + 1);
        }
    }
    lineEnds.push(source.length);

    const result = [];
    let line = 0;
    let previousTokenLine = 0;
    let previousTokenColumn = 0;
    for (const span of spans) {
        const token = LEXER_TYPES.get(span.type);
        if (token === null || span.start === span.end) {
            continue;
        }
        while (line + 1 < lineStarts.length && lineStarts[line + 1] <= span.start) {
            line++;
        }
        while (lineStarts[line] < span.end) {
            const start = Math.max(span.start, lineStarts[line]);
            const end = Math.min(span.end, lineEnds[line]);
            if (start < end) {
                const column = start - lineStarts[line];
                const deltaLine = line - previousTokenLine;
                const deltaColumn = deltaLine === 0 ? column - previousTokenColumn : column;
                result.push(deltaLine, deltaColumn, end - start, token[0], token[1]);
                previousTokenLine = line;
                previousTokenColumn = column;
            }
            if (line + 1 === lineStarts.length || lineStarts[line + 1] >= span.end) {
                break;
            }
            line++;
        }
    }
    return new Uint32Array(result);
}

module.exports = { TOKEN_TYPES, TOKEN_MODIFIERS, encodeSemanticTokens };
