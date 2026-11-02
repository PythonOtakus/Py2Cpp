"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { RequestBroker } = require("../out/requestBroker");

const runtimeSource = fs.readFileSync(path.join(__dirname, "../out/gpuRuntime.js"), "utf8");

function harness({ bundled = true, throwOnFork, cooperative = true } = {}) {
  const children = [];
  const timers = [];
  const states = [];
  const calls = [];
  const module = { exports: {} };
  const mockProcess = { platform: "win32", arch: "x64", env: { TEST_PARENT: "inherited" }, execPath: "Cursor.exe" };
  const context = vm.createContext({
    module, process: mockProcess,
    setTimeout(fn, delay) { const timer = { fn, delay, cleared: false }; timers.push(timer); return timer; },
    clearTimeout(timer) { if (timer) timer.cleared = true; },
    require(name) {
      if (name === "./requestBroker") return { RequestBroker };
      if (name === "node:fs") return { existsSync: () => bundled };
      if (name === "node:path") return path;
      if (name === "node:child_process") return { fork(script, args, options) {
        if (throwOnFork) throw new Error(throwOnFork);
        calls.push({ script, args, options });
        const child = new EventEmitter();
        Object.assign(child, {
          connected: true, stderr: new EventEmitter(), sent: [], killed: false, kills: [],
          send(message, callback) {
            this.sent.push(message); callback?.();
            if (message.type === "stop" && cooperative) this.kill();
          },
          kill(signal) { this.kills.push(signal); this.killed = true; this.connected = false; this.emit("exit", 0); },
          message(message) { this.emit("message", { v: 1, session: args[0], ...message }); },
        });
        children.push(child);
        return child;
      } };
      throw new Error(`Unexpected require ${name}`);
    },
  });
  vm.runInContext(runtimeSource, context);
  let runtime;
  runtime = new module.exports.GpuRuntime({ fsPath: "extension" }, () => states.push(runtime.state));
  return { runtime, children, calls, timers, states };
}

test("starts once without a preview and uses ordinary bundled Node in an isolated hidden child", async () => {
  const app = harness();
  const initial = app.runtime.ensureStarted();
  assert.equal(app.runtime.ensureStarted(), initial);
  assert.equal(app.children.length, 1);
  assert.match(app.calls[0].options.execPath, /vendor[\\/]node[\\/]win32-x64[\\/]node.exe$/);
  assert.equal(app.calls[0].options.windowsHide, true);
  assert.deepEqual(Array.from(app.calls[0].options.execArgv), []);
  assert.equal(app.calls[0].options.env.ELECTRON_RUN_AS_NODE, "1");
  assert.equal(app.calls[0].options.env.TEST_PARENT, "inherited");
  assert.notEqual(app.calls[0].options.execPath, "Cursor.exe");
  app.children[0].message({ type: "ready", available: true, backend: "vulkan · GPU" });
  assert.equal(await initial, true);
  assert.equal(app.runtime.backend, "vulkan · GPU");
  assert.equal(app.timers[0].cleared, true);
  assert.equal(await app.runtime.ensureStarted(), true);
  assert.equal(app.children.length, 1);
  assert.deepEqual(app.states, ["starting", "ready"]);
  app.runtime.dispose();
});

test("configured Node overrides bundled Node and PATH is the unbundled fallback", async () => {
  for (const [options, nodePath, expected] of [[{}, "custom-node", "custom-node"], [{ bundled: false }, "", "node"]]) {
    const app = harness(options);
    const started = app.runtime.ensureStarted(nodePath);
    assert.equal(app.calls[0].options.execPath, expected);
    app.runtime.stop();
    assert.equal(await started, false);
    assert.equal(app.children[0].killed, true);
    assert.equal(app.runtime.state, "closed");
  }
});

test("IPC responses correlate by request and stale sessions never replace current tokens", async () => {
  const app = harness();
  const starting = app.runtime.ensureStarted();
  const child = app.children[0];
  child.message({ type: "ready", available: true });
  await starting;
  const first = app.runtime.parse("first", { version: 1 }, undefined, 1000);
  const second = app.runtime.parse("second", { version: 2 }, undefined, 1000);
  await Promise.resolve();
  assert.equal(child.sent[0].session, "1");
  assert.equal(child.sent[0].source, "first");
  child.message({ session: "old", type: "result", id: 1, spans: [{ type: "wrong" }] });
  assert.equal(app.runtime.broker.pending.size, 2);
  child.message({ type: "result", id: 2, spans: [], elapsedMs: 2 });
  child.message({ type: "result", id: 1, spans: [], elapsedMs: 1 });
  assert.equal((await first).elapsedMs, 1);
  assert.equal((await second).elapsedMs, 2);
  app.runtime.dispose();
});

test("cancels requests in the same session and rejects pending requests on stop", async () => {
  const app = harness();
  const starting = app.runtime.ensureStarted();
  const child = app.children[0];
  child.message({ type: "ready", available: true });
  await starting;
  let cancel;
  const cancellation = { onCancellationRequested(fn) { cancel = fn; return { dispose() {} }; } };
  const request = app.runtime.parse("pending", {}, cancellation, 1000);
  const rejected = assert.rejects(request, /cancelled/);
  await Promise.resolve();
  cancel();
  await rejected;
  assert.ok(child.sent.some((message) => message.type === "cancel" && message.session === "1"));
  const abandoned = app.runtime.parse("stop", {}, undefined, 1000);
  const closed = assert.rejects(abandoned, /closed/);
  app.runtime.stop();
  await closed;
  assert.equal(app.runtime.broker, undefined);
  assert.equal(child.killed, true);
});

test("initialization failure stays unavailable until an explicit restart", async () => {
  const app = harness();
  const first = app.runtime.ensureStarted();
  const old = app.children[0];
  old.message({ type: "ready", available: false, error: "hardware GPU unavailable" });
  assert.equal(await first, false);
  assert.equal(app.runtime.state, "unavailable");
  assert.match(app.runtime.error, /hardware GPU/);
  assert.equal(old.killed, true);
  assert.equal(await app.runtime.ensureStarted(), false);
  assert.equal(app.children.length, 1);
  const restarted = app.runtime.restart("different-node");
  old.message({ type: "ready", available: true });
  assert.equal(app.runtime.state, "starting");
  app.children[1].message({ type: "ready", available: true });
  assert.equal(await restarted, true);
  assert.equal(app.calls[1].args[0], "2");
  assert.equal(app.calls[1].options.execPath, "different-node");
  app.runtime.dispose();
});

test("initialization timeout and child spawn errors stop the native process", async () => {
  const app = harness();
  const starting = app.runtime.ensureStarted();
  assert.equal(app.timers[0].delay, 30000);
  app.timers[0].fn();
  assert.equal(await starting, false);
  assert.equal(app.runtime.state, "unavailable");
  assert.match(app.runtime.error, /timed out/);
  assert.equal(app.children[0].killed, true);
  const failed = harness({ throwOnFork: "Node missing" });
  assert.equal(await failed.runtime.ensureStarted(), false);
  assert.match(failed.runtime.error, /Node missing/);
});

test("device loss and native crashes reject outstanding work without restarting indefinitely", async () => {
  for (const failure of ["fatal", "exit", "error", "disconnect"]) {
    const app = harness();
    const starting = app.runtime.ensureStarted();
    const child = app.children[0];
    child.message({ type: "ready", available: true });
    await starting;
    const request = app.runtime.parse("pending", {}, undefined, 1000);
    const rejected = assert.rejects(request, /closed/);
    if (failure === "fatal") child.message({ type: "fatal", error: "GPU device lost" });
    else if (failure === "error") child.emit("error", new Error("native failure"));
    else child.emit(failure, failure === "exit" ? 1 : undefined);
    await rejected;
    assert.equal(app.runtime.state, "unavailable");
    assert.equal(child.killed, true);
    assert.equal(await app.runtime.ensureStarted(), false);
    assert.equal(app.children.length, 1);
  }
});

test("disposal terminates startup and prevents any new GPU child", async () => {
  const app = harness();
  const initial = app.runtime.ensureStarted();
  app.runtime.dispose();
  assert.equal(await initial, false);
  assert.equal(await app.runtime.ensureStarted(), false);
  assert.equal(await app.runtime.restart(), false);
  assert.equal(app.children.length, 1);
  await assert.rejects(app.runtime.parse("x", {}, undefined, 100), /not ready/);
});

test("shutdown first requests device cleanup and force-kills an unresponsive driver after one second", async () => {
  const app = harness({ cooperative: false });
  const initial = app.runtime.ensureStarted();
  const child = app.children[0];
  child.message({ type: "ready", available: true });
  await initial;
  app.runtime.stop();
  assert.ok(child.sent.some((message) => message.type === "stop" && message.session === "1"));
  assert.equal(child.killed, false);
  const forceKill = app.timers.find((timer) => timer.delay === 1000);
  forceKill.fn();
  assert.equal(child.killed, true);
  assert.deepEqual(child.kills, ["SIGKILL"]);
  assert.equal(forceKill.cleared, true);
});

test("already-exited children are not signalled again during cleanup", async () => {
  const app = harness();
  const initial = app.runtime.ensureStarted();
  const child = app.children[0];
  child.exitCode = 1;
  child.emit("exit", 1);
  assert.equal(await initial, false);
  assert.equal(app.runtime.state, "unavailable");
  assert.equal(child.kills.length, 0);
});

const workerSource = fs.readFileSync(path.join(__dirname, "../out/gpuWorker.mjs"), "utf8")
  .replace('await import("../vendor/webgpu/index.js")', "await loadRuntime()")
  .replaceAll("import.meta.url", '"file:///extension/out/gpuWorker.mjs"')
  .replace("await import(moduleUrl.href)", "await loadModel(moduleUrl.href)");

function workerHarness({ fallback = false, description = "hardware", missingFirstAdapter = false, parseFailure, electron = false } = {}) {
  const child = new EventEmitter();
  const messages = [];
  const parses = [];
  const backends = [];
  const work = [];
  let lost;
  let destroyed = 0;
  const device = {
    features: new Set(), limits: { maxBufferSize: 1024, maxStorageBufferBindingSize: 1024 },
    lost: new Promise((resolve) => { lost = resolve; }),
    destroy() { destroyed++; },
  };
  Object.assign(child, {
    argv: ["node", "gpuWorker.mjs", "7"], platform: "win32", connected: true, exits: [],
    versions: electron ? { electron: "1.0" } : {},
    send(message, callback) { messages.push(message); callback?.(); },
    exit(code) { this.exits.push(code); this.connected = false; },
  });
  const context = vm.createContext({
    process: child, URL, performance,
    setTimeout() { return { unref() {} }; },
    async loadRuntime() {
      return { globals: {}, create(options) {
        backends.push(options[0]);
        return { async requestAdapter() {
          if (missingFirstAdapter && backends.length === 1) return null;
          return {
            info: { isFallbackAdapter: fallback, device: "GPU", description },
            features: device.features, limits: device.limits,
            async requestDevice() { return device; },
          };
        } };
      } };
    },
    async loadModel() {
      return { async parse(source) {
        parses.push(source);
        if (source.startsWith("def gpuLexerReady")) return [{ type: "keyword", start: 0, end: 3 }];
        if (parseFailure) throw new Error(parseFailure);
        return new Promise((resolve, reject) => work.push({ source, resolve, reject }));
      } };
    },
  });
  vm.runInContext(workerSource, context);
  const flush = () => new Promise((resolve) => setImmediate(resolve));
  return { messages, parses, backends, work, lost, child, flush,
    get destroyed() { return destroyed; },
    message(message) { child.emit("message", { v: 1, session: "7", ...message }); },
  };
}

test("worker probes real model entrypoint before ready and serializes/cancels queued work", async () => {
  const app = workerHarness();
  await app.flush();
  assert.equal(app.messages[0].type, "ready");
  assert.equal(app.messages[0].available, true);
  assert.equal(app.parses.length, 1);
  app.message({ type: "parse", id: 1, source: "first" });
  app.message({ type: "parse", id: 2, source: "second" });
  app.message({ type: "parse", id: 3, source: "third" });
  assert.equal(app.work.length, 1);
  app.message({ type: "cancel", id: 2 });
  app.message({ type: "cancel", id: 1 });
  app.work[0].resolve([{ type: "plain", start: 0, end: 5 }]);
  await app.flush();
  assert.equal(app.work.length, 2);
  assert.equal(app.work[1].source, "third");
  assert.equal(app.messages.some((message) => message.id === 1 || message.id === 2), false);
  app.work[1].resolve([{ type: "plain", start: 0, end: 5 }]);
  await app.flush();
  const result = app.messages.find((message) => message.id === 3);
  assert.equal(result.type, "result");
  assert.equal(result.session, "7");
  assert.ok(result.elapsedMs >= 0);
  app.message({ type: "stop" });
  assert.equal(app.destroyed, 1);
  assert.deepEqual(app.child.exits, [0]);
});

test("worker rejects software adapters and falls back only between GPU backends", async () => {
  for (const options of [{ fallback: true }, { description: "SwiftShader Device" }]) {
    const app = workerHarness(options);
    await app.flush();
    assert.equal(app.messages[0].available, false);
    assert.match(app.messages[0].error, /hardware GPU/);
    assert.equal(app.parses.length, 0);
  }
  const app = workerHarness({ missingFirstAdapter: true });
  await app.flush();
  assert.deepEqual(app.backends, ["backend=vulkan", "backend=d3d12"]);
  assert.equal(app.messages[0].available, true);
  app.message({ type: "stop" });
});

test("worker ignores stale sessions, validates ranges, and reports device loss", async () => {
  const app = workerHarness();
  await app.flush();
  app.message({ session: "old", type: "parse", id: 1, source: "ignored" });
  assert.equal(app.work.length, 0);
  app.message({ type: "parse", id: 2, source: "short" });
  app.work[0].resolve([{ type: "keyword", start: 0, end: 50 }]);
  await app.flush();
  assert.equal(app.messages.find((message) => message.id === 2).type, "error");
  app.lost({ reason: "unknown", message: "driver reset" });
  await app.flush();
  assert.match(app.messages.find((message) => message.type === "fatal").error, /driver reset/);
  assert.equal(app.destroyed, 1);
  assert.deepEqual(app.child.exits, [0]);
});

test("worker releases GPU resources when the extension host IPC disconnects", async () => {
  const app = workerHarness();
  await app.flush();
  app.child.emit("disconnect");
  assert.equal(app.destroyed, 1);
  assert.deepEqual(app.child.exits, [0]);
});

test("worker rejects an Electron executable before loading incompatible native code", async () => {
  const app = workerHarness({ electron: true });
  await app.flush();
  assert.equal(app.messages[0].available, false);
  assert.match(app.messages[0].error, /ordinary Node.js/);
  assert.equal(app.backends.length, 0);
  assert.equal(app.parses.length, 0);
});
