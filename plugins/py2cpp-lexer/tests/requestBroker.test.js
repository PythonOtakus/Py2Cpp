"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { RequestBroker } = require("../out/requestBroker");

test("correlates out-of-order responses without leaking requests", async () => {
  const sent = [];
  const broker = new RequestBroker((m) => { sent.push(m); return true; });
  const a = broker.request("alpha", { version: 1 });
  const b = broker.request("beta", { version: 2 });
  await Promise.resolve();
  assert.equal(sent.length, 2);
  assert.equal(broker.accept({ v: 2, type: "result", id: sent[0].id }), false);
  broker.accept({ v: 1, type: "result", id: sent[1].id, spans: [], elapsedMs: 2 });
  broker.accept({ v: 1, type: "result", id: sent[0].id, spans: [], elapsedMs: 1 });
  assert.equal((await a).elapsedMs, 1);
  assert.equal((await b).elapsedMs, 2);
  assert.equal(broker.pending.size, 0);
  assert.equal(broker.accept({ v: 1, type: "result", id: sent[0].id, spans: [] }), false);
  broker.dispose();
});

test("timeout cancels transport and ignores late results", async () => {
  const sent = [];
  const broker = new RequestBroker((m) => { sent.push(m); return true; }, 10);
  await assert.rejects(broker.request("text", {}), /timed out/);
  assert.equal(sent[1].type, "cancel");
  assert.equal(broker.pending.size, 0);
  assert.equal(broker.accept({ v: 1, type: "result", id: sent[0].id, spans: [] }), false);
  broker.dispose();
});

test("cancellation cleans listener and pending GPU work", async () => {
  let callback;
  let disposed = false;
  const sent = [];
  const cancellation = { isCancellationRequested: false, onCancellationRequested(fn) { callback = fn; return { dispose() { disposed = true; } }; } };
  const broker = new RequestBroker((m) => { sent.push(m); return true; });
  const promise = broker.request("text", {}, cancellation);
  const rejection = assert.rejects(promise, /cancelled/);
  callback();
  await rejection;
  assert.ok(disposed);
  assert.equal(sent.filter((m) => m.type === "parse").length, 0);
  assert.equal(broker.pending.size, 0);
  broker.dispose();
});

test("transport failure, GPU errors and session disposal reject pending requests", async () => {
  const missing = new RequestBroker(() => false);
  await assert.rejects(missing.request("x", {}), /not available/);
  const throwing = new RequestBroker(() => { throw new Error("transport failed"); });
  await assert.rejects(throwing.request("x", {}), /transport failed/);
  let request;
  const broker = new RequestBroker((m) => { request = m; return true; });
  const gpuFailure = broker.request("x", {});
  await Promise.resolve();
  broker.accept({ v: 1, type: "error", id: request.id, error: "device lost" });
  await assert.rejects(gpuFailure, /device lost/);
  const closed = broker.request("x", {});
  broker.dispose();
  await assert.rejects(closed, /closed/);
  await assert.rejects(broker.request("x", {}), /closed/);
  missing.dispose();
  throwing.dispose();
});
