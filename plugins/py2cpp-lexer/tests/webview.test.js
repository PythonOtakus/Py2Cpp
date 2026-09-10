"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../media/main.mjs"), "utf8")
    .replace("import { parse } from '../vendor/gpu-lexer/index.mjs';", "const parse = mockParse;");
const nextTurn = () => new Promise((resolve) => setImmediate(resolve));
const metadata = { name: "example.py", version: 2, languageId: "python" };
const session = "17";
const plain = (source) => source.length ? [{ type: "plain", start: 0, end: source.length }] : [];

function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((success, failure) => { resolve = success; reject = failure; });
    return { promise, resolve, reject };
}

function boot(parse) {
    const posts = [];
    const timers = new Set();
    const calls = [];
    class Element {
        constructor(tag = "div") {
            this.tag = tag;
            this.children = [];
            this.dataset = {};
            this.listeners = {};
            this.text = "";
        }
        set textContent(value) { this.text = String(value); this.children = []; }
        get textContent() { return this.text + this.children.map((child) => child.textContent).join(""); }
        set innerHTML(_value) { throw new Error("Unsafe innerHTML rendering"); }
        appendChild(child) { this.children.push(child); return child; }
        replaceChildren(child) { this.text = ""; this.children = child.children; }
        addEventListener(name, handler) { this.listeners[name] = handler; }
    }
    const elements = Object.fromEntries(["status", "details", "title", "summary", "code", "refresh", "restart"]
        .map((id) => [id, new Element()]));
    let receive;
    let clock = 0;
    vm.runInNewContext(script, {
        mockParse: (source) => { calls.push(source); return parse(source); },
        acquireVsCodeApi: () => ({ postMessage: (message) => posts.push(JSON.parse(JSON.stringify(message))) }),
        document: {
            body: { dataset: { session } },
            getElementById: (id) => elements[id],
            createElement: (tag) => new Element(tag),
            createDocumentFragment: () => new Element("fragment"),
            createTextNode: (text) => { const node = new Element("text"); node.textContent = text; return node; },
        },
        window: { addEventListener: (_name, handler) => { receive = handler; } },
        performance: { now: () => clock++ },
        setTimeout: (handler, timeout) => {
            assert.equal(timeout, 25000);
            timers.add(handler);
            return handler;
        },
        clearTimeout: (timer) => timers.delete(timer),
    });
    return { elements, posts, calls, timers, receive: (data) => receive({ data: { session, ...data } }) };
}

test("real parse probe precedes ready; buttons send versioned commands", async () => {
    const app = boot(plain);
    await nextTurn();
    assert.deepEqual(app.calls, ["const gpuLexerReady = 1;"]);
    assert.deepEqual(app.posts, [{ v: 1, session, type: "ready", available: true }]);
    assert.equal(app.timers.size, 0);
    app.elements.refresh.listeners.click();
    app.elements.restart.listeners.click();
    assert.deepEqual(app.posts.slice(1), [{ v: 1, session, type: "refresh" }, { v: 1, session, type: "restart" }]);
});

test("GPU unavailable still accepts plain previews and rejects parse without fake success", async () => {
    const app = boot(() => Promise.reject("WebGPU unavailable"));
    await nextTurn();
    assert.deepEqual(app.posts, [{ v: 1, session, type: "ready", available: false, error: "WebGPU unavailable" }]);
    app.receive({ v: 1, type: "preview", source: "class A:\n    pass", document: metadata });
    assert.equal(app.elements.code.textContent, "class A:\n    pass");
    assert.equal(app.elements.title.textContent, metadata.name);
    assert.match(app.elements.summary.textContent, /版本 2/);
    assert.match(app.elements.details.textContent, /TextMate/);
    app.receive({ v: 1, type: "parse", id: 1, source: "next", document: metadata });
    assert.equal(app.elements.code.textContent, "next");
    assert.deepEqual(app.posts.at(-1), { v: 1, session, type: "error", id: 1, error: "WebGPU unavailable" });
    assert.equal(app.calls.length, 1);
});

test("initialization timeout fails queued work and ignores eventual probe success", async () => {
    const probe = deferred();
    const app = boot(() => probe.promise);
    app.receive({ v: 1, type: "parse", id: "queued", source: "queued", document: metadata });
    await nextTurn();
    for (const timer of app.timers) { timer(); }
    assert.equal(app.posts[0].type, "ready");
    assert.equal(app.posts[0].available, false);
    assert.equal(app.posts[1].type, "error");
    assert.equal(app.posts[1].id, "queued");
    assert.match(app.elements.details.textContent, /25 秒/);
    probe.resolve([]);
    await nextTurn();
    assert.equal(app.posts.length, 2);
});

test("tasks serialize, queued cancellation avoids parse and active cancellation discards result", async () => {
    const slow = deferred();
    const app = boot((source) => source === "old" ? slow.promise : plain(source));
    await nextTurn();
    app.receive({ v: 1, type: "parse", id: 1, source: "old", document: metadata });
    app.receive({ v: 1, type: "parse", id: 2, source: "skipped", document: metadata });
    app.receive({ v: 1, type: "parse", id: 3, source: "new", document: metadata });
    app.receive({ v: 1, type: "cancel", id: 2 });
    app.receive({ v: 1, type: "cancel", id: 1 });
    assert.deepEqual(app.calls, ["const gpuLexerReady = 1;", "old"]);
    slow.resolve(plain("old"));
    await nextTurn();
    assert.deepEqual(app.calls, ["const gpuLexerReady = 1;", "old", "new"]);
    assert.deepEqual(app.posts.filter((item) => item.type === "result").map((item) => item.id), [3]);
    assert.equal(app.elements.code.textContent, "new");
});

test("a late result is returned to host without overwriting a newer plain preview", async () => {
    const slow = deferred();
    const app = boot((source) => source === "old" ? slow.promise : plain(source));
    await nextTurn();
    app.receive({ v: 1, type: "parse", id: 1, source: "old", document: metadata });
    app.receive({ v: 1, type: "preview", source: "new 😀", document: { ...metadata, version: 3 } });
    slow.resolve(plain("old"));
    await nextTurn();
    assert.equal(app.posts.at(-1).type, "result");
    assert.equal(app.elements.code.textContent, "new 😀");
    assert.match(app.elements.summary.textContent, /版本 3/);
});

test("preview rendering preserves gaps, UTF-16 text, whitespace and literal HTML", async () => {
    const source = "<img>\n  😀  ";
    const app = boot((value) => value === source ? [{ type: "string", start: 0, end: 5 }] : plain(value));
    await nextTurn();
    app.receive({ v: 1, type: "parse", id: 1, source, document: { ...metadata, name: "<script>" } });
    await nextTurn();
    assert.equal(app.elements.code.textContent, source);
    assert.equal(app.elements.title.textContent, "<script>");
    assert.equal(app.elements.code.children[0].tag, "span");
    assert.equal(app.elements.code.children[0].className, "token-string");
    assert.equal(app.elements.code.children[0].textContent, "<img>");
    assert.match(app.elements.summary.textContent, /推理耗时 1.0 ms/);
    assert.equal(app.posts.at(-1).elapsedMs, 1);
});

test("invalid GPU spans become explicit errors and retain plain source", async () => {
    for (const invalid of [
        null,
        [{ start: -1, end: 1, type: "plain" }],
        [{ start: 0, end: 4, type: "plain" }],
        [{ start: 0, end: 1.5, type: "plain" }],
        [{ start: 0, end: Infinity, type: "plain" }],
        [{ start: 0, end: 1, type: "malicious-class" }],
        [{ start: 0, end: 2, type: "string" }, { start: 1, end: 3, type: "string" }],
    ]) {
        const app = boot((source) => source === "abc" ? invalid : plain(source));
        await nextTurn();
        app.receive({ v: 1, type: "parse", id: 1, source: "abc", document: metadata });
        await nextTurn();
        assert.equal(app.posts.at(-1).type, "error");
        assert.equal(app.elements.code.textContent, "abc");
        assert.match(app.elements.details.textContent, /TextMate/);
        assert.equal(app.posts.some((message) => message.type === "result"), false);
    }
});

test("parse rejection is reported and a following task can still run", async () => {
    const app = boot((source) => source === "bad" ? Promise.reject("GPU dispatch failed") : plain(source));
    await nextTurn();
    app.receive({ v: 1, type: "parse", id: 1, source: "bad", document: metadata });
    app.receive({ v: 1, type: "parse", id: 2, source: "good", document: metadata });
    await nextTurn();
    assert.deepEqual(app.posts[1], { v: 1, session, type: "error", id: 1, error: "GPU dispatch failed" });
    assert.equal(app.posts[2].type, "result");
    assert.equal(app.elements.code.textContent, "good");
});

test("messages from another Webview session cannot change the preview or run tasks", async () => {
    const app = boot(plain);
    await nextTurn();
    app.receive({ v: 1, type: "preview", source: "current", document: metadata });
    app.receive({ v: 1, session: "16", type: "preview", source: "stale", document: metadata });
    app.receive({ v: 1, session: "16", type: "parse", id: 1, source: "stale", document: metadata });
    app.receive({ v: 1, session: undefined, type: "parse", id: 2, source: "missing", document: metadata });
    await nextTurn();
    assert.equal(app.elements.code.textContent, "current");
    assert.deepEqual(app.calls, ["const gpuLexerReady = 1;"]);
    assert.equal(app.posts.length, 1);
    assert.equal(app.posts[0].session, session);
});

test("background parse success returns tokens without changing any active preview UI", async () => {
    const background = deferred();
    const app = boot((source) => source === "background" ? background.promise : plain(source));
    await nextTurn();
    app.receive({ v: 1, type: "parse", id: 1, source: "active", document: metadata });
    await nextTurn();
    const before = Object.fromEntries(["code", "title", "summary", "status", "details"]
        .map((id) => [id, app.elements[id].textContent]));
    app.receive({ v: 1, type: "parse", id: 2, source: "background", document: { ...metadata, name: "background.py", preview: false } });
    for (const [id, text] of Object.entries(before)) assert.equal(app.elements[id].textContent, text);
    background.resolve(plain("background"));
    await nextTurn();
    for (const [id, text] of Object.entries(before)) assert.equal(app.elements[id].textContent, text);
    assert.equal(app.posts.at(-1).type, "result");
    assert.equal(app.posts.at(-1).id, 2);
});

test("background parse failure leaves active preview and its in-flight result intact", async () => {
    const active = deferred();
    const app = boot((source) => source === "active" ? active.promise : source === "background" ? Promise.reject("background failure") : plain(source));
    await nextTurn();
    app.receive({ v: 1, type: "parse", id: 1, source: "active", document: metadata });
    app.receive({ v: 1, type: "parse", id: 2, source: "background", document: { ...metadata, name: "background.py", preview: false } });
    assert.equal(app.elements.code.textContent, "active");
    assert.match(app.elements.status.textContent, /正在推理/);
    active.resolve(plain("active"));
    await nextTurn();
    assert.equal(app.elements.code.textContent, "active");
    assert.equal(app.elements.title.textContent, metadata.name);
    assert.match(app.elements.summary.textContent, /推理耗时 1.0 ms/);
    assert.equal(app.elements.status.textContent, "GPU 已就绪");
    assert.deepEqual(app.posts.at(-1), { v: 1, session, type: "error", id: 2, error: "background failure" });
});

test("background rejection while GPU is unavailable does not replace a plain preview", async () => {
    const app = boot(() => Promise.reject("WebGPU unavailable"));
    await nextTurn();
    app.receive({ v: 1, type: "preview", source: "active", document: metadata });
    const before = Object.fromEntries(["code", "title", "summary", "status", "details"]
        .map((id) => [id, app.elements[id].textContent]));
    app.receive({ v: 1, type: "parse", id: 1, source: "background", document: { ...metadata, preview: false } });
    for (const [id, text] of Object.entries(before)) assert.equal(app.elements[id].textContent, text);
    assert.equal(app.posts.at(-1).type, "error");
});
