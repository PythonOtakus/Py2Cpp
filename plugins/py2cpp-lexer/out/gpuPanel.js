"use strict";

const crypto = require("node:crypto");
const vscode = require("vscode");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

class GpuPanel {
  constructor(extensionUri, onRefresh, onRestart, onClose) {
    this.extensionUri = extensionUri;
    this.onRefresh = onRefresh;
    this.onRestart = onRestart;
    this.onClose = onClose;
    this.snapshot = { state: "starting" };
    this.generation = 0;
    this.panel = undefined;
    this.ready = false;
  }

  show() {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Beside, true);
      return;
    }
    const panel = vscode.window.createWebviewPanel("py2cppLexer", "Py2Cpp Lexer", {
      viewColumn: vscode.ViewColumn.Beside, preserveFocus: true,
    }, {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [vscode.Uri.joinPath(this.extensionUri, "media")],
    });
    this.panel = panel;
    this.ready = false;
    const session = String(++this.generation);
    panel.webview.onDidReceiveMessage((message) => this.onMessage(message, panel, session));
    panel.onDidDispose(() => {
      if (this.panel !== panel) return;
      this.panel = undefined;
      this.ready = false;
      this.onClose?.();
    });
    panel.webview.html = this.html(panel.webview);
  }

  onMessage(message, panel, session) {
    if (this.panel !== panel || session !== String(this.generation) ||
        !message || message.v !== 1 || message.session !== session) return;
    if (message.type === "ready") {
      this.ready = true;
      // Repeated ready messages also replay the snapshot after a Webview reload.
      this.publish();
    } else if (message.type === "restart") {
      this.onRestart?.();
    } else if (message.type === "refresh") {
      this.onRefresh?.();
    }
  }

  update(snapshot) {
    this.snapshot = snapshot;
    this.publish();
  }

  publish() {
    if (!this.panel || !this.ready) return;
    return Promise.resolve(this.panel.webview.postMessage({
      v: 1, session: String(this.generation), type: "snapshot", snapshot: this.snapshot,
    })).catch(() => false);
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
<p id="status" role="status">正在连接后台 GPU…</p><p id="details">预览关闭后编辑器高亮继续运行 · 文件内容仅在本地处理</p>
<h2 id="title">打开代码文件以预览</h2><p id="summary"></p><pre><code id="code"></code></pre>
<script type="module" nonce="${nonce}" src="${escapeHtml(script)}"></script></body></html>`;
  }

  dispose() {
    this.panel?.dispose();
  }
}

module.exports = { GpuPanel, escapeHtml };
