"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../media/main.mjs"), "utf8");
const metadata = { name: "example.py2", version: 2, languageId: "py2cpp" };
const session = "17";

function boot() {
    const posts = [];
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
    vm.runInNewContext(script, {
        acquireVsCodeApi: () => ({ postMessage: (message) => posts.push(JSON.parse(JSON.stringify(message))) }),
        document: {
            body: { dataset: { session } },
            getElementById: (id) => elements[id],
            createElement: (tag) => new Element(tag),
            createDocumentFragment: () => new Element("fragment"),
            createTextNode: (text) => { const node = new Element("text"); node.textContent = text; return node; },
        },
        window: { addEventListener: (_name, handler) => { receive = handler; } },
    });
    return {
        elements, posts,
        receive: (data) => receive({ data: { v: 1, session, ...data } }),
        snapshot: (snapshot) => receive({ data: { v: 1, session, type: "snapshot", snapshot } }),
    };
}

test("passive preview sends ready immediately; buttons only forward versioned commands", () => {
    const app = boot();
    assert.deepEqual(app.posts, [{ v: 1, session, type: "ready" }]);
    app.snapshot({ state: "ready", source: "latest", document: metadata });
    const before = app.elements.code.textContent;
    app.elements.refresh.listeners.click();
    app.elements.restart.listeners.click();
    assert.deepEqual(app.posts.slice(1), [{ v: 1, session, type: "refresh" }, { v: 1, session, type: "restart" }]);
    assert.equal(app.elements.code.textContent, before);
    assert.doesNotMatch(script, /import\s|navigator\.gpu|\bparse\(|setTimeout\(/);
});

test("ready snapshot explains background GPU highlighting and local processing", () => {
    const app = boot();
    app.snapshot({ state: "ready", backend: "Dawn D3D12", source: "class A:\n    pass", document: metadata });
    assert.equal(app.elements.status.textContent, "后台 GPU 已就绪");
    assert.match(app.elements.details.textContent, /Dawn D3D12/);
    assert.match(app.elements.details.textContent, /关闭预览后继续运行/);
    assert.match(app.elements.details.textContent, /源码仅在本地处理/);
    assert.equal(app.elements.code.textContent, "class A:\n    pass");
    assert.match(app.elements.summary.textContent, /版本 2/);
});

test("starting, pending, unavailable and disabled states are controlled by host snapshots", () => {
    const app = boot();
    app.snapshot({ state: "starting" });
    assert.equal(app.elements.status.dataset.state, "busy");
    assert.match(app.elements.details.textContent, /关闭预览不会中断初始化/);
    app.snapshot({ state: "ready", pending: true, source: "queued", document: metadata });
    assert.equal(app.elements.status.textContent, "后台 GPU 正在推理");
    assert.match(app.elements.summary.textContent, /等待解析/);
    app.snapshot({ state: "busy", source: "running", document: metadata });
    assert.equal(app.elements.status.dataset.state, "busy");
    app.snapshot({ state: "unavailable", error: "<adapter failed>", source: "plain", document: metadata });
    assert.equal(app.elements.status.dataset.state, "error");
    assert.match(app.elements.details.textContent, /<adapter failed>/);
    assert.match(app.elements.details.textContent, /TextMate/);
    assert.equal(app.elements.code.textContent, "plain");
    app.snapshot({ state: "ready", enabled: false });
    assert.equal(app.elements.status.textContent, "GPU 高亮已禁用");
    assert.equal(app.elements.status.dataset.state, "disabled");
    app.snapshot({ state: "disabled" });
    assert.equal(app.elements.status.textContent, "GPU 高亮已禁用");
    assert.deepEqual(app.posts, [{ v: 1, session, type: "ready" }]);
});

test("snapshot rendering preserves gaps, UTF-16 text, whitespace and literal HTML", () => {
    const source = " <img>\n  😀  ";
    const app = boot();
    app.snapshot({
        state: "ready", source, document: { ...metadata, name: "<script>", languageId: "<py2cpp>" },
        spans: [{ type: "string", start: 1, end: 6 }, { type: "plain", start: 6, end: 6 }],
        elapsedMs: 1.25, note: "<img onerror=alert(1)>",
    });
    assert.equal(app.elements.code.textContent, source);
    assert.equal(app.elements.title.textContent, "<script>");
    assert.equal(app.elements.code.children[0].tag, "text");
    assert.equal(app.elements.code.children[1].tag, "span");
    assert.equal(app.elements.code.children[1].className, "token-string");
    assert.equal(app.elements.code.children[1].textContent, "<img>");
    assert.match(app.elements.summary.textContent, /推理耗时 1.3 ms/);
    assert.match(app.elements.summary.textContent, /<img onerror=alert\(1\)>/);
    assert.match(app.elements.summary.textContent, /<py2cpp>/);
});

test("new snapshots replace previous tokens and clear stale content when no document is active", () => {
    const app = boot();
    app.snapshot({ state: "ready", source: "old", document: metadata, spans: [{ start: 0, end: 3, type: "keyword" }] });
    assert.equal(app.elements.code.children[0].className, "token-keyword");
    app.snapshot({ state: "ready", source: "new 😀", document: { ...metadata, version: 3 }, pending: true });
    assert.equal(app.elements.code.textContent, "new 😀");
    assert.equal(app.elements.code.children.length, 0);
    assert.match(app.elements.summary.textContent, /版本 3/);
    app.snapshot({ state: "ready" });
    assert.equal(app.elements.code.textContent, "");
    assert.equal(app.elements.title.textContent, "打开代码文件以预览");
    assert.equal(app.elements.summary.textContent, "");
});

test("invalid spans retain plain source and show an explicit error", () => {
    for (const invalid of [
        null, {}, [null], [[]],
        [{ start: -1, end: 1, type: "plain" }],
        [{ start: 0, end: 4, type: "plain" }],
        [{ start: 0, end: 1.5, type: "plain" }],
        [{ start: 0, end: Infinity, type: "plain" }],
        [{ start: 2, end: 1, type: "plain" }],
        [{ start: 0, end: 1, type: "malicious-class" }],
        [{ start: 0, end: 2, type: "string" }, { start: 1, end: 3, type: "string" }],
    ]) {
        const app = boot();
        app.snapshot({ state: "ready", source: "abc", document: metadata, spans: invalid });
        assert.equal(app.elements.code.textContent, "abc");
        assert.equal(app.elements.code.children.length, 0);
        assert.equal(app.elements.status.textContent, "GPU 结果无效");
        assert.match(app.elements.details.textContent, /原始源码/);
        assert.equal(app.posts.length, 1);
    }
});

test("empty valid spans and invalid optional metadata do not crash rendering", () => {
    const app = boot();
    app.snapshot({ state: "ready", source: "", document: metadata, spans: [], elapsedMs: 0 });
    assert.equal(app.elements.code.textContent, "");
    assert.match(app.elements.summary.textContent, /0 个区间/);
    assert.match(app.elements.summary.textContent, /0.0 ms/);
    for (const elapsedMs of [NaN, Infinity, -1, "3"]) {
        app.snapshot({
            state: "ready", source: "abc", document: { name: {}, version: 2.5, languageId: [] },
            spans: [], elapsedMs, note: {}, backend: [], error: {},
        });
        assert.equal(app.elements.title.textContent, "未命名文档");
        assert.match(app.elements.summary.textContent, /未知语言 · 版本 — · 推理耗时 —/);
    }
});

test("a parse error snapshot is shown without taking ownership of the GPU session", () => {
    const app = boot();
    app.snapshot({ state: "ready", error: "GPU dispatch failed", source: "plain", document: metadata });
    assert.equal(app.elements.status.textContent, "GPU 解析失败");
    assert.match(app.elements.details.textContent, /后台会话保留/);
    assert.equal(app.elements.code.textContent, "plain");
    assert.equal(app.posts.length, 1);
    app.snapshot({ state: "ready", source: "okay", document: metadata, spans: [] });
    assert.equal(app.elements.status.textContent, "后台 GPU 已就绪");
});

test("malformed, old protocol and old session messages cannot change the preview", () => {
    const app = boot();
    app.snapshot({ state: "ready", source: "current", document: metadata });
    for (const data of [
        { session: "16", type: "snapshot", snapshot: { state: "ready", source: "stale" } },
        { session: undefined, type: "snapshot", snapshot: { source: "missing session" } },
        { v: 2, type: "snapshot", snapshot: { source: "wrong protocol" } },
        { type: "parse", source: "old protocol", id: 1 },
        { type: "preview", source: "old preview" },
        { type: "snapshot", snapshot: null },
        { type: "snapshot", snapshot: [] },
        { type: "snapshot", snapshot: "bad" },
    ]) {
        app.receive(data);
        assert.equal(app.elements.code.textContent, "current");
    }
    assert.equal(app.posts.length, 1);
});
