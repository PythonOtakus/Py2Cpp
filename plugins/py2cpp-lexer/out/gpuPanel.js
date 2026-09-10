"use strict";

const crypto = require("node:crypto");
const vscode = require("vscode");
const { RequestBroker } = require("./requestBroker");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

class GpuPanel {
  constructor(extensionUri, onStateChange, onRefresh) {
    this.extensionUri = extensionUri;
    this.onStateChange = onStateChange;
    this.onRefresh = onRefresh;
    this.state = "closed";
    this.error = "";
    this.generation = 0;
    this.panel = undefined;
  }

  show() {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Beside, true);
      return;
    }
    this.panel = vscode.window.createWebviewPanel("py2cppLexer", "Py2Cpp Lexer", {
      viewColumn: vscode.ViewColumn.Beside, preserveFocus: true,
    }, {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [
        vscode.Uri.joinPath(this.extensionUri, "media"),
        vscode.Uri.joinPath(this.extensionUri, "vendor"),
      ],
    });
    this.panel.webview.onDidReceiveMessage((message) => this.onMessage(message));
    this.panel.onDidDispose(() => {
      clearTimeout(this.initTimer);
      this.broker?.dispose();
      this.panel = undefined;
      this.setState("closed");
    });
    this.restart();
  }

  restart() {
    if (!this.panel) return this.show();
    clearTimeout(this.initTimer);
    this.broker?.dispose();
    this.generation += 1;
    const session = String(this.generation);
    this.broker = new RequestBroker((message) => this.panel?.webview.postMessage({ ...message, session }) ?? false);
    this.setState("starting");
    this.initTimer = setTimeout(() => {
      if (this.state === "starting") this.setState("unavailable", "WebGPU initialization timed out. Restart the GPU session or check editor hardware acceleration.");
    }, 30000);
    this.panel.webview.html = this.html(this.panel.webview);
  }

  setState(state, error = "") {
    this.state = state;
    this.error = error;
    this.onStateChange();
  }

  onMessage(message) {
    if (!message || message.v !== 1 || message.session !== String(this.generation)) return;
    if (message.type === "ready" && this.state === "starting") {
      clearTimeout(this.initTimer);
      this.setState(message.available === true ? "ready" : "unavailable", String(message.error || ""));
    } else if (message.type === "restart") {
      this.restart();
    } else if (message.type === "refresh") {
      this.onRefresh();
    } else {
      this.broker?.accept(message);
    }
  }

  preview(source, document) {
    return this.panel?.webview.postMessage({ v: 1, session: String(this.generation), type: "preview", source, document });
  }

  parse(source, document, cancellation, timeoutMs) {
    if (this.state !== "ready") return Promise.reject(new Error(this.error || "GPU panel is not ready"));
    this.broker.timeoutMs = timeoutMs;
    return this.broker.request(source, document, cancellation);
  }

  html(webview) {
    const nonce = crypto.randomBytes(18).toString("base64");
    const script = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "main.mjs"));
    const style = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "style.css"));
    const source = escapeHtml(webview.cspSource);
    return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src ${source} 'nonce-${nonce}'; style-src ${source}; connect-src 'none'; img-src ${source}; base-uri 'none'; form-action 'none';">
<link rel="stylesheet" href="${escapeHtml(style)}"><title>Py2Cpp Lexer</title></head><body data-session="${this.generation}">
<header><h1>Py2Cpp Lexer</h1><div class="actions"><button id="refresh" type="button">刷新</button><button id="restart" type="button">重启 GPU</button></div></header>
<p id="status" role="status">正在初始化本地 WebGPU…</p><p id="details">gpu-lexer 0.0.2 · 文件内容仅在本地处理</p>
<h2 id="title">打开代码文件以预览</h2><p id="summary"></p><pre><code id="code"></code></pre>
<script type="module" nonce="${nonce}" src="${escapeHtml(script)}"></script></body></html>`;
  }

  dispose() {
    clearTimeout(this.initTimer);
    this.broker?.dispose();
    this.panel?.dispose();
  }
}

module.exports = { GpuPanel, escapeHtml };
