"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { TOKEN_TYPES, TOKEN_MODIFIERS, encodeSemanticTokens } = require("../out/semanticTokens");

function span(start, end, type = "keyword") {
    return { start, end, type };
}

function tokens(source, spans) {
    const result = encodeSemanticTokens(source, spans);
    assert.ok(result instanceof Uint32Array);
    return Array.from(result);
}

test("legend and lexer types map to stable semantic token identifiers", () => {
    assert.deepEqual(TOKEN_TYPES, [
        "comment", "string", "number", "keyword", "type", "function", "variable", "operator",
    ]);
    assert.deepEqual(TOKEN_MODIFIERS, ["readonly"]);
    const types = ["comment", "string", "number", "keyword", "type", "function", "constant", "operator"];
    const input = types.map((type, index) => span(index, index + 1, type));
    assert.deepEqual(tokens("abcdefgh", input), [
        0, 0, 1, 0, 0,
        0, 1, 1, 1, 0,
        0, 1, 1, 2, 0,
        0, 1, 1, 3, 0,
        0, 1, 1, 4, 0,
        0, 1, 1, 5, 0,
        0, 1, 1, 6, 1,
        0, 1, 1, 7, 0,
    ]);
});

test("multiple spans reset the column delta after every line break", () => {
    assert.deepEqual(tokens("a b\n  c d\r\nx\ry", [
        span(0, 1, "function"),
        span(2, 3, "constant"),
        span(6, 7, "type"),
        span(8, 9, "keyword"),
        span(11, 12, "number"),
        span(13, 14, "operator"),
    ]), [
        0, 0, 1, 5, 0,
        0, 2, 1, 6, 1,
        1, 2, 1, 4, 0,
        0, 2, 1, 3, 0,
        1, 0, 1, 2, 0,
        1, 0, 1, 7, 0,
    ]);
});

test("one multiline span splits at CRLF, LF and CR without newline tokens", () => {
    const source = "ab\r\ncd\nef\rg\r\n";
    assert.deepEqual(tokens(source, [span(0, source.length, "string")]), [
        0, 0, 2, 1, 0,
        1, 0, 2, 1, 0,
        1, 0, 2, 1, 0,
        1, 0, 1, 1, 0,
    ]);
});

test("partial first and last lines of a multiline span retain correct offsets", () => {
    assert.deepEqual(tokens("pre abc\r\ndef ghi\njkl end", [span(4, 20, "comment")]), [
        0, 4, 3, 0, 0,
        1, 0, 7, 0, 0,
        1, 0, 3, 0, 0,
    ]);
});

test("Chinese and emoji use UTF-16 lengths and columns", () => {
    const source = "变量 = \"😀\"\r\n名";
    assert.equal(source.length, 12);
    assert.deepEqual(tokens(source, [
        span(0, 2, "type"),
        span(3, 4, "operator"),
        span(5, 9, "string"),
        span(11, 12, "function"),
    ]), [
        0, 0, 2, 4, 0,
        0, 3, 1, 7, 0,
        0, 2, 4, 1, 0,
        1, 0, 1, 5, 0,
    ]);
    assert.deepEqual(tokens("😀x", [span(2, 3, "keyword")]), [0, 2, 1, 3, 0]);
});

test("plain spans are omitted while later line and column positions stay correct", () => {
    assert.deepEqual(tokens("text\r\n\n   x", [
        span(0, 10, "plain"), span(10, 11, "keyword"),
    ]), [2, 3, 1, 3, 0]);
    assert.deepEqual(tokens("abc", [span(0, 3, "plain")]), []);
});

test("empty lines and spans containing only newline units produce no empty tokens", () => {
    const source = "\r\n\n\ra\r\nb";
    assert.deepEqual(tokens(source, [span(0, source.length, "comment")]), [
        3, 0, 1, 0, 0,
        1, 0, 1, 0, 0,
    ]);
    assert.deepEqual(tokens("a\r\nb", [
        span(1, 2, "string"), span(2, 3, "string"), span(3, 4, "keyword"),
    ]), [1, 0, 1, 3, 0]);
    assert.deepEqual(tokens("\r\n\n\r", [span(0, 4, "comment")]), []);
});

test("empty documents, no spans and zero-length boundary spans are supported", () => {
    assert.deepEqual(tokens("", []), []);
    assert.deepEqual(tokens("", [span(0, 0)]), []);
    assert.deepEqual(tokens("abc", []), []);
    assert.deepEqual(tokens("abc", [span(0, 0), span(0, 1), span(1, 1), span(3, 3)]), [0, 0, 1, 3, 0]);
});

test("invalid source and spans containers fail rather than returning partial data", () => {
    for (const source of [undefined, null, 1, {}, ["a"]]) {
        assert.throws(() => encodeSemanticTokens(source, []), TypeError);
    }
    for (const spans of [undefined, null, "", {}, new Uint32Array(0)]) {
        assert.throws(() => encodeSemanticTokens("abc", spans), TypeError);
    }
    for (const value of [undefined, null, 1, "abc", [], {}]) {
        assert.throws(() => encodeSemanticTokens("abc", [value]));
    }
    assert.throws(() => encodeSemanticTokens("abc", new Array(1)), TypeError);
});

test("invalid bounds reject non-finite, fractional, reversed and out-of-range offsets", () => {
    for (const [start, end] of [
        [-1, 1], [0, 4], [2, 1], [4, 4], [0.5, 1], [0, 1.5],
        [NaN, 1], [0, NaN], [Infinity, Infinity], [-Infinity, 0],
        [0, Infinity], ["0", 1], [0, "1"], [0n, 1],
    ]) {
        assert.throws(() => encodeSemanticTokens("abc", [span(start, end)]), RangeError);
    }
    assert.throws(() => encodeSemanticTokens("", [span(0, 1)]), RangeError);
});

test("overlap and out-of-order spans are rejected even when plain or empty", () => {
    for (const input of [
        [span(0, 2), span(1, 3)],
        [span(2, 3), span(0, 1)],
        [span(0, 2, "plain"), span(1, 3)],
        [span(0, 2), span(1, 1)],
        [span(2, 2), span(1, 1)],
    ]) {
        assert.throws(() => encodeSemanticTokens("abc", input), RangeError);
    }
});

test("unknown token types, including on empty spans, are rejected", () => {
    for (const type of [undefined, null, 0, "variable", "constructor", "toString", "", "unknown"]) {
        assert.throws(() => encodeSemanticTokens("abc", [{ start: 0, end: 1, type }]), TypeError);
        assert.throws(() => encodeSemanticTokens("", [{ start: 0, end: 0, type }]), TypeError);
    }
});
