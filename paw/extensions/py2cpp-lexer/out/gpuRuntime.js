"use strict";

const { fork } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { RequestBroker } = require("./requestBroker");

function nodeExecutable(extensionPath, configuredPath = "") {
  if (configuredPath.trim()) return configuredPath.trim();
  const bundled = path.join(extensionPath, "vendor", "node", `${process.platform}-${process.arch}`,
    process.platform === "win32" ? "node.exe" : "node");
  return fs.existsSync(bundled) ? bundled : "node";
}

class GpuRuntime {
  constructor(extensionUri, onStateChange, storageUri) {
    this.extensionPath = extensionUri.fsPath;
    this.onStateChange = onStateChange;
    this.state = "closed";
    this.error = "";
    this.backend = "";
    this.generation = 0;
    this.nodePath = "";
    this.disposed = false;
  }

  setState(state, error = "") {
    this.state = state;
    this.error = error;
    this.onStateChange();
  }

  ensureStarted(nodePath = this.nodePath) {
    if (this.disposed) return Promise.resolve(false);
    if (this.state === "starting") return this.startPromise;
    if (this.state !== "closed") return Promise.resolve(this.state === "ready");
    this.nodePath = nodePath;
    const session = String(++this.generation);
    this.backend = "";
    this.stderr = "";
    this.startPromise = new Promise((resolve) => { this.finishStart = resolve; });
    this.setState("starting");
    try {
      const child = fork(path.join(this.extensionPath, "out", "gpuWorker.mjs"), [session], {
        execPath: nodeExecutable(this.extensionPath, this.nodePath),
        execArgv: [],
        cwd: this.extensionPath,
        env: { ...process.env, ELECTRON_RUN_AS_NODE: "1" },
        windowsHide: true,
        stdio: ["ignore", "ignore", "pipe", "ipc"],
      });
      this.child = child;
      this.broker = new RequestBroker((message) => new Promise((resolve, reject) => {
        if (this.child !== child || !child.connected) return resolve(false);
        child.send({ ...message, session }, (error) => error ? reject(error) : resolve(true));
      }));
      child.stderr?.on("data", (data) => {
        if (this.child === child) this.stderr = (this.stderr + String(data)).slice(-4096);
      });
      child.on("message", (message) => {
        if (this.child !== child || !message || message.v !== 1 || message.session !== session) return;
        if (message.type === "ready" && this.state === "starting") {
          if (message.available !== true) return this.fail(String(message.error || "GPU initialization failed"));
          clearTimeout(this.initTimer);
          this.backend = String(message.backend || "WebGPU");
          this.finishStart?.(true);
          this.finishStart = undefined;
          this.setState("ready");
        } else if (message.type === "fatal") {
          this.fail(String(message.error || "GPU device lost"));
        } else {
          this.broker?.accept(message);
        }
      });
      child.on("error", (error) => {
        if (this.child === child) this.fail(`GPU worker could not start: ${error.message}`);
      });
      child.on("exit", (code, signal) => {
        if (this.child === child) this.fail(`GPU worker exited (${signal || code}).${this.stderr ? ` ${this.stderr.trim()}` : ""}`);
      });
      child.on("disconnect", () => {
        if (this.child === child) this.fail("GPU worker disconnected");
      });
      this.initTimer = setTimeout(() => {
        if (this.child === child && this.state === "starting") this.fail("GPU initialization timed out after 30 seconds");
      }, 30000);
    } catch (error) {
      this.fail(`GPU worker could not start: ${error.message}`);
    }
    return this.startPromise;
  }

  release() {
    clearTimeout(this.initTimer);
    this.finishStart?.(false);
    this.finishStart = undefined;
    this.broker?.dispose();
    this.broker = undefined;
    const child = this.child;
    this.child = undefined;
    // The upstream model holds private GPU resources. Process termination also
    // releases those resources when device cleanup is prevented by a driver hang.
    if (child && child.exitCode == null && child.signalCode == null) {
      const killTimer = setTimeout(() => {
        try { child.kill("SIGKILL"); } catch { /* Already exited. */ }
      }, 1000);
      killTimer.unref?.();
      child.once("exit", () => clearTimeout(killTimer));
      const terminate = () => {
        try { child.kill(); } catch { clearTimeout(killTimer); }
      };
      if (child.connected) {
        // SIGTERM is an immediate TerminateProcess on Windows. Give the worker
        // an IPC shutdown first so it can destroy its device before exiting.
        try {
          child.send({ v: 1, type: "stop", session: String(this.generation) }, (error) => {
            if (error) terminate();
          });
        } catch { terminate(); }
      } else {
        terminate();
      }
    }
  }

  fail(error) {
    this.release();
    this.setState("unavailable", error);
  }

  stop() {
    this.release();
    this.backend = "";
    this.setState("closed");
  }

  restart(nodePath = this.nodePath) {
    this.stop();
    return this.ensureStarted(nodePath);
  }

  parse(source, document, cancellation, timeoutMs = 15000) {
    if (this.state !== "ready" || !this.broker) return Promise.reject(new Error(this.error || "GPU runtime is not ready"));
    this.broker.timeoutMs = timeoutMs;
    return this.broker.request(source, document, cancellation);
  }

  dispose() {
    this.disposed = true;
    this.stop();
  }
}

module.exports = { GpuRuntime, nodeExecutable };
