"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function boot() {
  const panels = [];
  const calls = [];
  const module = { exports: {} };
  const vscode = {
    ViewColumn: { Beside: 2 },
    Uri: { joinPath: (base, ...parts) => [base, ...parts].join("/") },
    window: {
      createWebviewPanel(type, title, location, options) {
        const posts = [];
        const panel = {
          type, title, location, options, posts, reveals: [], htmlWrites: 0,
          reveal(...args) { this.reveals.push(args); },
          onDidDispose(handler) { this.closed = handler; },
          dispose() {
            if (this.disposed) return;
            this.disposed = true;
            this.closed();
          },
        };
        let html;
        panel.webview = {
          cspSource: "local-resource:",
          asWebviewUri: (uri) => `local-resource:${uri}`,
          onDidReceiveMessage(handler) { panel.receive = handler; },
          postMessage(message) { posts.push(JSON.parse(JSON.stringify(message))); return Promise.resolve(true); },
          get html() { return html; },
          set html(value) { html = value; panel.htmlWrites++; },
        };
        panels.push(panel);
        return panel;
      },
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../out/gpuPanel.js"), "utf8"), {
    module,
    require(id) {
      if (id === "vscode") return vscode;
      if (id === "node:crypto") return require(id);
      throw new Error(`A passive panel must not load a runtime dependency: ${id}`);
    },
  });
  const panel = new module.exports.GpuPanel("/extension", () => calls.push("refresh"),
    () => calls.push("restart"), () => calls.push("close"));
  return {
    panel, panels, calls,
    send(target, type, overrides = {}) {
      const session = target.webview.html.match(/data-session="([^"]+)"/)[1];
      target.receive({ v: 1, session, type, ...overrides });
    },
  };
}

test("snapshots wait for Webview ready and replay the latest state after reload", () => {
  const app = boot();
  app.panel.update({ state: "starting", source: "first" });
  assert.equal(app.panels.length, 0);
  app.panel.show();
  const webview = app.panels[0];
  app.panel.update({ state: "ready", source: "latest", spans: [] });
  assert.equal(webview.posts.length, 0);
  app.send(webview, "ready");
  assert.deepEqual(webview.posts, [{ v: 1, session: "1", type: "snapshot", snapshot: { state: "ready", source: "latest", spans: [] } }]);
  app.panel.update({ state: "ready", source: "edited", pending: true });
  assert.equal(webview.posts.at(-1).snapshot.source, "edited");
  app.send(webview, "ready");
  assert.equal(webview.posts.length, 3);
  assert.deepEqual(webview.posts.at(-1), webview.posts.at(-2));
  assert.deepEqual(app.calls, []);
});

test("repeated show only reveals the current panel and restart delegates without reloading it", () => {
  const app = boot();
  app.panel.show();
  const webview = app.panels[0];
  app.send(webview, "ready");
  app.panel.show();
  assert.equal(app.panels.length, 1);
  assert.equal(webview.htmlWrites, 1);
  assert.equal(webview.reveals.length, 1);
  assert.equal(webview.reveals[0][0], 2);
  assert.equal(webview.reveals[0][1], true);
  app.send(webview, "refresh");
  app.send(webview, "restart");
  assert.deepEqual(app.calls, ["refresh", "restart"]);
  assert.equal(webview.htmlWrites, 1);
  assert.equal(app.panel.ready, true);
});

test("closing notifies once and preserves snapshots for reopening without owning GPU state", () => {
  const app = boot();
  app.panel.show();
  const first = app.panels[0];
  app.send(first, "ready");
  first.dispose();
  assert.equal(app.panel.panel, undefined);
  assert.equal(app.panel.ready, false);
  assert.deepEqual(app.calls, ["close"]);
  app.panel.update({ state: "ready", source: "computed while closed", spans: [] });
  assert.equal(first.posts.length, 1);
  app.panel.show();
  const second = app.panels[1];
  assert.equal(second.posts.length, 0);
  app.send(second, "ready");
  assert.equal(second.posts[0].session, "2");
  assert.equal(second.posts[0].snapshot.source, "computed while closed");
  assert.deepEqual(app.calls, ["close"]);
  app.panel.dispose();
  app.panel.dispose();
  assert.deepEqual(app.calls, ["close", "close"]);
});

test("messages and late disposal from an old panel cannot affect its replacement", () => {
  const app = boot();
  app.panel.show();
  const first = app.panels[0];
  first.dispose();
  app.panel.show();
  const second = app.panels[1];
  for (const type of ["ready", "refresh", "restart"]) {
    app.send(first, type);
    app.send(first, type, { session: "2" });
    app.send(second, type, { session: "1" });
    app.send(second, type, { session: undefined });
    app.send(second, type, { v: 2 });
  }
  first.closed();
  assert.equal(app.panel.panel, second);
  assert.equal(app.panel.ready, false);
  assert.equal(second.posts.length, 0);
  assert.deepEqual(app.calls, ["close"]);
  app.send(second, "ready");
  assert.equal(app.panel.ready, true);
  assert.equal(second.posts.length, 1);
});

test("preview resource policy permits only local UI assets and no model network connection", () => {
  const app = boot();
  app.panel.show();
  const webview = app.panels[0];
  assert.equal(webview.options.retainContextWhenHidden, true);
  assert.equal(webview.options.localResourceRoots.length, 1);
  assert.equal(webview.options.localResourceRoots[0], "/extension/media");
  assert.match(webview.webview.html, /connect-src 'none'/);
  assert.match(webview.webview.html, /media\/main\.mjs/);
  assert.doesNotMatch(webview.webview.html, /vendor|gpu-lexer\/index/);
});
