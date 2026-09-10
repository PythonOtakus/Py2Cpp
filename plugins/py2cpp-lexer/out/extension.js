"use strict";

const vscode = require("vscode");
const path = require("node:path");
const { GpuPanel } = require("./gpuPanel");
const { TOKEN_TYPES, TOKEN_MODIFIERS, encodeSemanticTokens } = require("./semanticTokens");

function bounded(value, fallback, minimum, maximum) {
  return Number.isFinite(value) ? Math.min(maximum, Math.max(minimum, Math.floor(value))) : fallback;
}

function settings(uri) {
  const config = vscode.workspace.getConfiguration("py2cpp-lexer", uri);
  return {
    enabled: config.get("enabled", true),
    debounceMs: bounded(config.get("debounceMs"), 250, 50, 3000),
    maxCharacters: bounded(config.get("maxDocumentCharacters"), 200000, 1000, 1000000),
    timeoutMs: bounded(config.get("requestTimeoutMs"), 15000, 1000, 60000),
  };
}

class HighlightController {
  constructor(context) {
    this.records = new Map();
    this.previousLanguages = new Map();
    this.focusedDocument = vscode.window.activeTextEditor?.document;
    this.disposed = false;
    this.changed = new vscode.EventEmitter();
    this.onDidChangeSemanticTokens = this.changed.event;
    this.output = vscode.window.createOutputChannel("Py2Cpp Lexer");
    this.status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 15);
    this.status.command = "py2cpp-lexer.openPanel";
    this.gpu = new GpuPanel(context.extensionUri, () => this.onGpuState(), () => this.refresh());
    this.updateStatus();
  }

  record(document) {
    const key = document.uri.toString();
    let record = this.records.get(key);
    if (!record) {
      record = { document, data: undefined, version: -1, serial: 0, timer: undefined, cancellation: undefined, promise: undefined, error: "" };
      this.records.set(key, record);
    }
    record.document = document;
    return record;
  }

  interested(document) {
    return !document.isClosed && (document.languageId === "py2cpp" || document === this.focusedDocument);
  }

  cancel(record) {
    record.serial += 1;
    clearTimeout(record.timer);
    record.timer = undefined;
    record.cancellation?.cancel();
    record.cancellation?.dispose();
    record.cancellation = undefined;
    record.promise = undefined;
  }

  invalidate(document) {
    const record = this.record(document);
    this.cancel(record);
    record.data = undefined;
    record.version = -1;
    record.error = "";
    this.changed.fire();
    this.schedule(document);
  }

  schedule(document, immediate = false) {
    if (this.disposed || !this.interested(document) || !settings(document.uri).enabled || !this.gpu.panel) return;
    const record = this.record(document);
    clearTimeout(record.timer);
    record.timer = setTimeout(() => {
      record.timer = undefined;
      void this.highlight(document);
    }, immediate ? 0 : settings(document.uri).debounceMs);
  }

  metadata(document) {
    return { name: path.basename(document.uri.path) || "Untitled", version: document.version, languageId: document.languageId, preview: document === this.focusedDocument };
  }

  async highlight(document) {
    if (this.disposed || document.isClosed || !this.gpu.panel) return;
    const options = settings(document.uri);
    if (!options.enabled) return;
    const record = this.record(document);
    if (record.promise) return record.promise;
    const source = document.getText();
    if (source.length > options.maxCharacters) {
      record.error = `文件超过 ${options.maxCharacters} 个 UTF-16 单元，保留基础高亮`;
      this.updateStatus();
      if (document === this.focusedDocument) {
        void this.gpu.preview("", { ...this.metadata(document), name: `${this.metadata(document).name} · ${record.error}` });
      }
      return;
    }
    // The preview may show any language; only Py2Cpp has a semantic provider.
    if (document === this.focusedDocument) void this.gpu.preview(source, this.metadata(document));
    if (this.gpu.state !== "ready") return;
    const version = document.version;
    const serial = ++record.serial;
    const cancellation = new vscode.CancellationTokenSource();
    record.cancellation = cancellation;
    record.promise = this.gpu.parse(source, this.metadata(document), cancellation.token, options.timeoutMs).then((result) => {
      if (this.disposed || document.isClosed || record.serial !== serial || document.version !== version) return;
      record.data = encodeSemanticTokens(source, result.spans);
      record.version = version;
      record.error = "";
      this.changed.fire();
    }).catch((error) => {
      if (this.disposed || record.serial !== serial || cancellation.token.isCancellationRequested) return;
      record.data = undefined;
      record.error = String(error?.message || error);
      this.output.appendLine(`${this.metadata(document).name}: ${record.error}`);
      this.changed.fire();
    }).finally(() => {
      cancellation.dispose();
      if (record.serial === serial) {
        record.cancellation = undefined;
        record.promise = undefined;
      }
      this.updateStatus();
    });
    return record.promise;
  }

  provideDocumentSemanticTokens(document, cancellation) {
    if (this.disposed || cancellation.isCancellationRequested || !settings(document.uri).enabled) return undefined;
    const record = this.record(document);
    if (record.version === document.version && record.data) return new vscode.SemanticTokens(record.data);
    // Do not block VS Code's language service on GPU setup, or resubmit known failures.
    if (!record.error && !record.timer && !record.promise) this.schedule(document);
    return undefined;
  }

  onGpuState() {
    for (const record of this.records.values()) {
      this.cancel(record);
      record.data = undefined;
      record.version = -1;
      record.error = "";
    }
    this.changed.fire();
    this.updateStatus();
    if ((this.gpu.state === "ready" || this.gpu.state === "unavailable") && this.focusedDocument) this.schedule(this.focusedDocument, true);
    if (this.gpu.error) this.output.appendLine(this.gpu.error);
  }

  updateStatus() {
    if (this.disposed) return;
    const doc = this.focusedDocument;
    if (!doc || (doc.languageId !== "py2cpp" && !this.gpu.panel)) {
      this.status.hide();
      return;
    }
    const record = this.records.get(doc.uri.toString());
    const disabled = !settings(doc.uri).enabled;
    this.status.text = disabled ? "$(circle-slash) Py2Cpp Lexer" : this.gpu.state === "ready" && !record?.error ? "$(symbol-color) Py2Cpp GPU" : "$(symbol-color) Py2Cpp Lexer";
    this.status.tooltip = disabled ? "GPU 高亮已在设置中关闭" : record?.error || this.gpu.error || ({ closed: "点击打开本地 GPU 高亮面板", starting: "正在初始化 WebGPU", ready: "gpu-lexer 0.0.2 · 本地 GPU 推理", unavailable: "WebGPU 不可用，保留基础高亮" }[this.gpu.state]);
    this.status.show();
  }

  focus(editor) {
    if (!editor) return;
    this.focusedDocument = editor.document;
    // Reissue an in-flight background request as the current preview.
    const record = this.records.get(editor.document.uri.toString());
    if (record?.promise) this.cancel(record);
    this.updateStatus();
    this.schedule(editor.document, true);
  }

  openPanel() {
    this.focusedDocument = vscode.window.activeTextEditor?.document || this.focusedDocument;
    this.gpu.show();
    if (this.focusedDocument) this.schedule(this.focusedDocument, true);
  }

  async enableCurrent() {
    const document = vscode.window.activeTextEditor?.document;
    if (!document) return void vscode.window.showInformationMessage("请先打开代码文件。");
    if (document.languageId !== "py2cpp") {
      this.previousLanguages.set(document.uri.toString(), document.languageId);
      this.focusedDocument = await vscode.languages.setTextDocumentLanguage(document, "py2cpp");
    } else this.focusedDocument = document;
    this.openPanel();
  }

  async restoreLanguage() {
    const document = vscode.window.activeTextEditor?.document;
    if (!document) return;
    const key = document.uri.toString();
    const language = this.previousLanguages.get(key);
    if (!language) return void vscode.window.showInformationMessage("此文件没有由 Py2Cpp Lexer 保存的语言模式；可点击状态栏语言名称手动选择。");
    this.focusedDocument = await vscode.languages.setTextDocumentLanguage(document, language);
    this.previousLanguages.delete(key);
    this.updateStatus();
    this.schedule(this.focusedDocument, true);
  }

  refresh() {
    if (!this.gpu.panel) this.openPanel();
    if (this.focusedDocument) {
      this.invalidate(this.focusedDocument);
      this.schedule(this.focusedDocument, true);
    }
  }

  closeDocument(document) {
    const key = document.uri.toString();
    const record = this.records.get(key);
    if (record) this.cancel(record);
    this.records.delete(key);
    if (this.focusedDocument === document) this.focusedDocument = undefined;
    this.updateStatus();
  }

  diagnostics() {
    return {
      state: this.gpu.state, error: this.gpu.error,
      documents: [...this.records.values()].map((r) => ({ uri: r.document.uri.toString(), version: r.version, tokenCount: (r.data?.length || 0) / 5, error: r.error })),
    };
  }

  dispose() {
    this.disposed = true;
    for (const record of this.records.values()) this.cancel(record);
    this.records.clear();
    this.gpu.dispose();
    this.changed.dispose();
    this.status.dispose();
    this.output.dispose();
  }
}

function activate(context) {
  const controller = new HighlightController(context);
  const command = (name, callback) => vscode.commands.registerCommand(`py2cpp-lexer.${name}`, callback);
  context.subscriptions.push(
    controller,
    vscode.languages.registerDocumentSemanticTokensProvider({ language: "py2cpp" }, controller, new vscode.SemanticTokensLegend(TOKEN_TYPES, TOKEN_MODIFIERS)),
    command("openPanel", () => controller.openPanel()),
    command("enableForCurrentFile", () => controller.enableCurrent()),
    command("restoreLanguage", () => controller.restoreLanguage()),
    command("refresh", () => controller.refresh()),
    command("restartGpu", () => controller.gpu.restart()),
    vscode.window.onDidChangeActiveTextEditor((editor) => controller.focus(editor)),
    vscode.workspace.onDidChangeTextDocument((event) => {
      if (event.contentChanges.length && controller.interested(event.document)) controller.invalidate(event.document);
    }),
    vscode.workspace.onDidCloseTextDocument((document) => controller.closeDocument(document)),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (!event.affectsConfiguration("py2cpp-lexer")) return;
      for (const record of controller.records.values()) controller.invalidate(record.document);
      controller.updateStatus();
    }),
  );
  // Read-only test/diagnostic API; no source content is exposed or persisted.
  return { getStatus: () => controller.diagnostics() };
}

function deactivate() {}

module.exports = { activate, deactivate, HighlightController, settings, bounded };
