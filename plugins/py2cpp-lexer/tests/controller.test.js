"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const nextTurn = () => new Promise((resolve) => setImmediate(resolve));
const noCancellation = { isCancellationRequested: false };

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((success, failure) => { resolve = success; reject = failure; });
  return { promise, resolve, reject };
}

function document(name, languageId = "py2cpp", source = "call f() from invoke(f): pass\n") {
  return {
    uri: { path: `/workspace/${name}`, toString: () => `file:///workspace/${name}` },
    languageId,
    version: 1,
    isClosed: false,
    getText: () => source,
    edit(value) { source = value; this.version++; },
  };
}

function boot(documents = [], options = {}) {
  const timers = new Map();
  const subscriptions = [];
  const commands = new Map();
  const config = { enabled: true, debounceMs: 50, ...options.config };
  const events = {};
  const runtimes = [];
  const panels = [];
  let nextTimer = 0;
  let provider;

  class EventEmitter {
    constructor() {
      this.listeners = new Set();
      this.event = (listener) => {
        this.listeners.add(listener);
        return { dispose: () => this.listeners.delete(listener) };
      };
    }
    fire(value) { for (const listener of [...this.listeners]) listener(value); }
    dispose() { this.listeners.clear(); }
  }

  function event(name) {
    events[name] = new EventEmitter();
    return events[name].event;
  }

  class CancellationTokenSource {
    constructor() {
      this.changed = new EventEmitter();
      this.token = { isCancellationRequested: false, onCancellationRequested: this.changed.event };
    }
    cancel() { this.token.isCancellationRequested = true; this.changed.fire(); }
    dispose() { this.changed.dispose(); }
  }

  class GpuRuntime {
    constructor(_extensionUri, onStateChange) {
      this.onStateChange = onStateChange;
      this.state = "closed";
      this.error = "";
      this.generation = 0;
      this.backend = "test-dawn";
      this.starts = 0;
      this.stops = 0;
      this.calls = [];
      this.disposed = false;
      runtimes.push(this);
    }
    ensureStarted() {
      if (this.state !== "closed") return;
      this.starts++;
      this.generation++;
      this.setState("starting");
    }
    ready() { this.setState("ready"); }
    setState(state, error = "") {
      this.state = state;
      this.error = error;
      this.onStateChange();
    }
    stop() {
      if (this.state === "closed") return;
      this.stops++;
      this.setState("closed");
    }
    restart() { this.stop(); this.ensureStarted(); }
    parse(source, metadata, cancellation, timeoutMs) {
      assert.equal(this.state, "ready", "only a ready runtime may receive inference");
      const call = { source, metadata, cancellation, timeoutMs };
      this.calls.push(call);
      return Promise.resolve(options.parse ? options.parse(call) : {
        spans: source.length ? [{ type: "keyword", start: 0, end: source.length }] : [],
        elapsedMs: 2,
      });
    }
    dispose() { this.disposed = true; this.stop(); }
  }

  class GpuPanel {
    constructor(_extensionUri, onRefresh, onRestart, onClose) {
      this.onRefresh = onRefresh;
      this.onRestart = onRestart;
      this.onClose = onClose;
      this.panel = undefined;
      this.updates = [];
      panels.push(this);
    }
    show() { this.panel = this.panel || { dispose: () => this.close() }; }
    update(snapshot) { this.updates.push(snapshot); }
    close() {
      if (!this.panel) return;
      this.panel = undefined;
      this.onClose();
    }
    dispose() { this.close(); }
  }

  const vscode = {
    EventEmitter,
    CancellationTokenSource,
    SemanticTokens: class { constructor(data) { this.data = data; } },
    SemanticTokensLegend: class { constructor(types, modifiers) { this.tokenTypes = types; this.tokenModifiers = modifiers; } },
    StatusBarAlignment: { Right: 2 },
    window: {
      activeTextEditor: options.focus === null ? undefined : { document: options.focus || documents[0] },
      createOutputChannel: () => ({ appendLine() {}, dispose() {} }),
      createStatusBarItem: () => ({ show() {}, hide() {}, dispose() {} }),
      showInformationMessage: async () => {},
      onDidChangeActiveTextEditor: event("focus"),
    },
    workspace: {
      textDocuments: [...documents],
      getConfiguration: () => ({ get: (key, fallback) => config[key] ?? fallback }),
      onDidOpenTextDocument: event("open"),
      onDidCloseTextDocument: event("close"),
      onDidChangeTextDocument: event("edit"),
      onDidChangeConfiguration: event("config"),
    },
    languages: {
      registerDocumentSemanticTokensProvider: (_selector, instance) => {
        provider = instance;
        return { dispose() {} };
      },
      setTextDocumentLanguage: async (doc, language) => {
        events.close.fire(doc);
        doc.languageId = language;
        events.open.fire(doc);
        return doc;
      },
    },
    commands: {
      registerCommand: (name, callback) => {
        commands.set(name, callback);
        return { dispose: () => commands.delete(name) };
      },
    },
  };
  if (!vscode.window.activeTextEditor?.document) vscode.window.activeTextEditor = undefined;

  const filename = path.join(__dirname, "../out/extension.js");
  const module = { exports: {} };
  vm.runInNewContext(fs.readFileSync(filename, "utf8"), {
    require(name) {
      if (name === "vscode") return vscode;
      if (name === "./gpuRuntime") return { GpuRuntime };
      if (name === "./gpuPanel") return { GpuPanel };
      if (name.startsWith(".")) return require(path.resolve(path.dirname(filename), name));
      return require(name);
    },
    module,
    exports: module.exports,
    setTimeout: (callback) => { const id = ++nextTimer; timers.set(id, callback); return id; },
    clearTimeout: (id) => timers.delete(id),
    console,
  }, { filename });
  const api = module.exports.activate({ extensionUri: { fsPath: path.resolve(__dirname, "..") }, subscriptions });

  return {
    api,
    get controller() { return provider; },
    get gpu() { return runtimes[0]; },
    get panel() { return panels[0]; },
    config,
    async flush() {
      for (let turn = 0; turn < 20; turn++) {
        const queued = [...timers];
        for (const [id, callback] of queued) {
          if (timers.delete(id)) callback();
        }
        await nextTurn();
        if (timers.size === 0) return;
      }
      assert.fail("controller scheduled work indefinitely");
    },
    command(name) { return commands.get(`py2cpp-lexer.${name}`)(); },
    tokens(doc) { return provider.provideDocumentSemanticTokens(doc, noCancellation); },
    open(doc) { vscode.workspace.textDocuments.push(doc); events.open.fire(doc); },
    close(doc) {
      doc.isClosed = true;
      vscode.workspace.textDocuments = vscode.workspace.textDocuments.filter((item) => item !== doc);
      events.close.fire(doc);
    },
    edit(doc, source) { doc.edit(source); events.edit.fire({ document: doc, contentChanges: [{ text: source }] }); },
    focus(doc) {
      vscode.window.activeTextEditor = doc ? { document: doc } : undefined;
      events.focus.fire(vscode.window.activeTextEditor);
    },
    configure(values) {
      Object.assign(config, values);
      events.config.fire({ affectsConfiguration: (name) => name === "py2cpp-lexer" });
    },
    dispose() { for (const subscription of [...subscriptions].reverse()) subscription.dispose(); },
  };
}

test("activation highlights every existing Py2Cpp document without opening a preview", async (t) => {
  const first = document("first.py2");
  const second = document("second.py2", "py2cpp", "lazy def compute(): return 42\n");
  const app = boot([first, second], { focus: null });
  t.after(() => app.dispose());
  await app.flush();
  assert.equal(app.gpu.starts, 1);
  assert.equal(app.panel.panel, undefined);
  app.gpu.ready();
  await app.flush();
  assert.equal(app.gpu.calls.length, 2);
  assert.ok(app.tokens(first)?.data.length > 0);
  assert.ok(app.tokens(second)?.data.length > 0);
  assert.equal(app.api.getStatus().previewOpen, false);
  assert.equal(app.api.getStatus().session, app.gpu.generation);
});

test("opening a Py2Cpp document starts GPU automatically; ordinary Python does not", async (t) => {
  const python = document("plain.py", "python");
  const app = boot([python]);
  t.after(() => app.dispose());
  await app.flush();
  app.focus(python);
  await app.flush();
  assert.equal(app.gpu.starts, 0);
  const py2 = document("new.py2");
  app.open(py2);
  await app.flush();
  assert.equal(app.gpu.starts, 1);
  assert.equal(app.panel.panel, undefined);
  app.gpu.ready();
  await app.flush();
  assert.ok(app.tokens(py2)?.data.length > 0);
  assert.equal(app.gpu.calls.some((call) => call.metadata.name === "plain.py"), false);
});

test("opening and closing preview preserves the GPU session and cached semantic tokens", async (t) => {
  const doc = document("preview.py2");
  const app = boot([doc]);
  t.after(() => app.dispose());
  await app.flush();
  app.gpu.ready();
  await app.flush();
  const before = Array.from(app.tokens(doc).data);
  const session = app.gpu.generation;
  app.command("openPanel");
  await app.flush();
  assert.equal(app.api.getStatus().previewOpen, true);
  app.panel.close();
  await app.flush();
  assert.equal(app.api.getStatus().previewOpen, false);
  assert.equal(app.gpu.state, "ready");
  assert.equal(app.gpu.generation, session);
  assert.equal(app.gpu.stops, 0);
  assert.deepEqual(Array.from(app.tokens(doc).data), before);

  const callsBeforeEdit = app.gpu.calls.length;
  app.edit(doc, "lazy property def value(self): return 12\n");
  await app.flush();
  assert.equal(app.gpu.calls.length, callsBeforeEdit + 1);
  assert.equal(app.api.getStatus().documents.find((item) => item.uri === doc.uri.toString()).version, doc.version);
  assert.ok(app.tokens(doc)?.data.length > 0);
  assert.equal(app.panel.panel, undefined);
});

test("closing preview does not cancel an in-flight editor inference", async (t) => {
  const result = deferred();
  const doc = document("pending.py2");
  const app = boot([doc], { parse: () => result.promise });
  t.after(() => app.dispose());
  await app.flush();
  app.command("openPanel");
  app.gpu.ready();
  await app.flush();
  assert.equal(app.gpu.calls.length, 1);
  app.panel.close();
  assert.equal(app.gpu.calls[0].cancellation.isCancellationRequested, false);
  result.resolve({ spans: [{ start: 0, end: 4, type: "keyword" }], elapsedMs: 2 });
  await app.flush();
  assert.ok(app.tokens(doc)?.data.length > 0);
  assert.equal(app.gpu.stops, 0);
});

test("a newer edited version cannot be overwritten by a stale GPU response", async (t) => {
  const oldResult = deferred();
  const newResult = deferred();
  const doc = document("editing.py2");
  const app = boot([doc], { parse: (call) => call.metadata.version === 1 ? oldResult.promise : newResult.promise });
  t.after(() => app.dispose());
  await app.flush();
  app.gpu.ready();
  await app.flush();
  app.edit(doc, "lazy def next(): return 2\n");
  await app.flush();
  assert.equal(app.gpu.calls.length, 2);
  assert.equal(app.gpu.calls[0].cancellation.isCancellationRequested, true);
  newResult.resolve({ spans: [{ start: 0, end: 4, type: "keyword" }], elapsedMs: 2 });
  await app.flush();
  const expected = Array.from(app.tokens(doc).data);
  oldResult.resolve({ spans: [{ start: 0, end: 1, type: "string" }], elapsedMs: 8 });
  await app.flush();
  assert.deepEqual(Array.from(app.tokens(doc).data), expected);
  assert.equal(app.api.getStatus().documents[0].version, 2);
});

test("runtime stops only after its last document and preview consumer are closed", async (t) => {
  const first = document("first.py2");
  const second = document("second.py2");
  const app = boot([first, second]);
  t.after(() => app.dispose());
  await app.flush();
  app.gpu.ready();
  await app.flush();
  app.close(first);
  assert.equal(app.gpu.stops, 0);
  assert.ok(app.tokens(second)?.data.length > 0);
  app.focus(second);
  app.command("openPanel");
  await app.flush();
  app.close(second);
  assert.equal(app.gpu.stops, 0);
  app.panel.close();
  await app.flush();
  assert.equal(app.gpu.state, "closed");
  assert.equal(app.gpu.stops, 1);
  assert.equal(app.api.getStatus().documents.length, 0);

  const third = document("third.py2");
  app.open(third);
  await app.flush();
  assert.equal(app.gpu.starts, 2);
  app.gpu.ready();
  await app.flush();
  assert.ok(app.tokens(third)?.data.length > 0);
});

test("disabling GPU releases runtime and tokens; enabling resumes without a preview", async (t) => {
  const doc = document("enabled.py2");
  const app = boot([doc]);
  t.after(() => app.dispose());
  await app.flush();
  app.gpu.ready();
  await app.flush();
  app.configure({ enabled: false });
  await app.flush();
  assert.equal(app.gpu.state, "closed");
  assert.equal(app.tokens(doc), undefined);
  const count = app.gpu.calls.length;
  app.edit(doc, "lazy def disabled(): return 0\n");
  await app.flush();
  assert.equal(app.gpu.calls.length, count);
  app.configure({ enabled: true });
  await app.flush();
  assert.equal(app.gpu.starts, 2);
  app.gpu.ready();
  await app.flush();
  assert.ok(app.tokens(doc)?.data.length > 0);
  assert.equal(app.panel.panel, undefined);
});

test("GPU startup failure falls back without retry loops or a surprise preview", async (t) => {
  const doc = document("unavailable.py2");
  const app = boot([doc]);
  t.after(() => app.dispose());
  await app.flush();
  app.gpu.setState("unavailable", "No compatible GPU adapter");
  await app.flush();
  assert.equal(app.tokens(doc), undefined);
  await app.flush();
  assert.equal(app.gpu.starts, 1);
  assert.equal(app.gpu.calls.length, 0);
  assert.equal(app.api.getStatus().error, "No compatible GPU adapter");
  assert.equal(app.panel.panel, undefined);
  app.command("restartGpu");
  await app.flush();
  assert.equal(app.gpu.starts, 2);
  app.gpu.ready();
  await app.flush();
  assert.ok(app.tokens(doc)?.data.length > 0);
  assert.equal(app.panel.panel, undefined);
});

test("disabled settings prevent background startup and also release an open preview's runtime", async (t) => {
  const doc = document("disabled.py2");
  const app = boot([doc], { config: { enabled: false } });
  t.after(() => app.dispose());
  await app.flush();
  assert.equal(app.gpu.starts, 0);
  assert.equal(app.tokens(doc), undefined);
  app.configure({ enabled: true });
  await app.flush();
  app.gpu.ready();
  await app.flush();
  app.command("openPanel");
  await app.flush();
  assert.equal(app.api.getStatus().previewOpen, true);
  app.configure({ enabled: false });
  await app.flush();
  assert.equal(app.gpu.state, "closed");
  assert.equal(app.tokens(doc), undefined);
  assert.equal(app.api.getStatus().previewOpen, true);
});
