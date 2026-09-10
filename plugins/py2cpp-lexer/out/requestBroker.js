"use strict";

class RequestBroker {
  constructor(send, timeoutMs = 15000) {
    this.send = send;
    this.timeoutMs = timeoutMs;
    this.sequence = 0;
    this.pending = new Map();
    this.disposed = false;
  }

  request(source, document, cancellation) {
    if (this.disposed) return Promise.reject(new Error("GPU session closed"));
    if (cancellation?.isCancellationRequested) return Promise.reject(new Error("Request cancelled"));
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const entry = { resolve, reject, timer: undefined, listener: undefined };
      this.pending.set(id, entry);
      const cancel = (reason) => {
        if (!this.pending.has(id)) return;
        this.finish(id, new Error(reason));
        Promise.resolve().then(() => this.send({ v: 1, type: "cancel", id })).catch(() => {});
      };
      entry.timer = setTimeout(() => cancel("GPU request timed out"), this.timeoutMs);
      entry.listener = cancellation?.onCancellationRequested(() => cancel("Request cancelled"));
      if (!this.pending.has(id)) {
        entry.listener?.dispose();
        return;
      }
      Promise.resolve().then(() => {
        if (this.pending.has(id)) return this.send({ v: 1, type: "parse", id, source, document });
        return true;
      }).then((sent) => {
        if (sent === false) this.finish(id, new Error("GPU runtime is not available"));
      }, (error) => this.finish(id, error));
    });
  }

  accept(message) {
    if (!message || message.v !== 1 || !Number.isSafeInteger(message.id)) return false;
    if (!this.pending.has(message.id)) return false;
    if (message.type === "result") {
      this.finish(message.id, undefined, { spans: message.spans, elapsedMs: message.elapsedMs });
      return true;
    }
    if (message.type === "error") {
      this.finish(message.id, new Error(String(message.error || "GPU parse failed")));
      return true;
    }
    return false;
  }

  finish(id, error, value) {
    const entry = this.pending.get(id);
    if (!entry) return;
    this.pending.delete(id);
    clearTimeout(entry.timer);
    entry.listener?.dispose();
    if (error) entry.reject(error); else entry.resolve(value);
  }

  dispose() {
    this.disposed = true;
    for (const id of this.pending.keys()) this.finish(id, new Error("GPU session closed"));
  }
}

module.exports = { RequestBroker };
