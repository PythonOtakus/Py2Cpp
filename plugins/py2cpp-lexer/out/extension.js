"use strict";

const vscode = require("vscode");
const path = require("node:path");
const { GpuRuntime } = require("./gpuRuntime");
const { GpuPanel } = require("./gpuPanel");
const { TOKEN_TYPES, TOKEN_MODIFIERS, encodeSemanticTokens } = require("./semanticTokens");

function bounded(value, fallback, minimum, maximum) {
  return Number.isFinite(value) ? Math.min(maximum, Math.max(minimum, Math.floor(value))) : fallback;
}

function settings(uri) {
  const config = vscode.workspace.getConfiguration("py2cpp-lexer", uri);
  const nodePath = config.get("nodePath", "");
  return {
    enabled: config.get("enabled", true),
    nodePath: typeof nodePath === "string" ? nodePath : "",
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
    this.preview = new GpuPanel(context.extensionUri, () => this.refresh(), () => this.restartGpu(), () => this.onPreviewClosed());
    this.gpu = new GpuRuntime(context.extensionUri, () => this.onGpuState(), context.globalStorageUri);
  }

  record(document) {
    const key = document.uri.toString();
    let record = this.records.get(key);
    if (!record) {
      record = { document, data: undefined, source: undefined, spans: undefined, elapsedMs: undefined,
        version: -1, serial: 0, timer: undefined, cancellation: undefined, promise: undefined, error: "" };
      this.records.set(key, record);
    }
    record.document = document;
    return record;
  }

  interested(document) {
    return !document.isClosed && (document.languageId === "py2cpp" || (this.preview.panel && document === this.focusedDocument));
  }

  consumers() {
    return vscode.workspace.textDocuments.filter((document) => this.interested(document) && settings(document.uri).enabled);
  }

  syncRuntime() {
    if (this.disposed) return;
    const documents = this.consumers();
    const previewEnabled = this.preview.panel && settings(this.focusedDocument?.uri).enabled;
    if (documents.length || previewEnabled) {
      this.gpu.ensureStarted(settings(documents[0]?.uri || this.focusedDocument?.uri).nodePath);
    } else {
      this.gpu.stop();
    }
    this.updateStatus();
    this.updatePreview();
  }

  start() {
    for (const document of vscode.workspace.textDocuments) {
      if (this.interested(document)) this.record(document);
    }
    this.syncRuntime();
    for (const document of this.consumers()) this.schedule(document, true);
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

  clearResult(record) {
    record.data = undefined;
    record.source = undefined;
    record.spans = undefined;
    record.elapsedMs = undefined;
    record.version = -1;
  }

  invalidate(document) {
    const record = this.record(document);
    this.cancel(record);
    this.clearResult(record);
    record.error = "";
    this.changed.fire();
    this.schedule(document);
    this.updatePreview();
  }

  schedule(document, immediate = false) {
    if (this.disposed || !this.interested(document) || !settings(document.uri).enabled) return;
    const record = this.record(document);
    if (record.version === document.version && record.data) return;
    if (record.promise || record.error) return;
    clearTimeout(record.timer);
    record.timer = setTimeout(() => {
      record.timer = undefined;
      void this.highlight(document);
    }, immediate ? 0 : settings(document.uri).debounceMs);
  }

  metadata(document) {
    return { name: path.basename(document.uri.path) || "Untitled", version: document.version, languageId: document.languageId };
  }

  async highlight(document) {
    if (this.disposed || !this.interested(document) || !settings(document.uri).enabled) return;
    const record = this.record(document);
    if (record.promise) return record.promise;
    if (record.version === document.version && record.data) return;
    const options = settings(document.uri);
    const source = document.getText();
    if (source.length > options.maxCharacters) {
      record.error = `文件超过 ${options.maxCharacters} 个 UTF-16 单元，保留基础高亮`;
      this.clearResult(record);
      this.changed.fire();
      this.updateStatus();
      this.updatePreview();
      return;
    }
    if (this.gpu.state !== "ready") return;
    const version = document.version;
    const serial = ++record.serial;
    const cancellation = new vscode.CancellationTokenSource();
    record.cancellation = cancellation;
    record.promise = this.gpu.parse(source, this.metadata(document), cancellation.token, options.timeoutMs).then((result) => {
      if (this.disposed || document.isClosed || record.serial !== serial || document.version !== version) return;
      record.data = encodeSemanticTokens(source, result.spans);
      record.source = source;
      record.spans = result.spans;
      record.elapsedMs = result.elapsedMs;
      record.version = version;
      record.error = "";
      this.changed.fire();
    }).catch((error) => {
      if (this.disposed || record.serial !== serial || cancellation.token.isCancellationRequested) return;
      this.clearResult(record);
      record.error = String(error?.message || error);
      this.output.appendLine(`${this.metadata(document).name}: ${record.error}`);
      this.changed.fire();
    }).finally(() => {
      cancellation.dispose();
      if (record.serial === serial) {
        record.cancellation = undefined;
        record.promise = undefined;
      }
      if (!this.disposed) {
        this.updateStatus();
        this.updatePreview();
      }
    });
    this.updatePreview();
    return record.promise;
  }

  provideDocumentSemanticTokens(document, cancellation) {
    if (this.disposed || document.languageId !== "py2cpp" || cancellation.isCancellationRequested || !settings(document.uri).enabled) return undefined;
    const record = this.record(document);
    if (record.version === document.version && record.data) return new vscode.SemanticTokens(record.data);
    if (!record.error && !record.timer && !record.promise && this.gpu.state === "ready") this.schedule(document);
    return undefined;
  }

  onGpuState() {
    if (this.disposed) return;
    for (const record of this.records.values()) {
      this.cancel(record);
      this.clearResult(record);
      record.error = "";
    }
    this.changed.fire();
    if (this.gpu.state === "ready") {
      for (const document of this.consumers()) this.schedule(document, true);
    }
    if (this.gpu.error) this.output.appendLine(this.gpu.error);
    this.updateStatus();
    this.updatePreview();
  }

  updateStatus() {
    if (this.disposed) return;
    const doc = this.focusedDocument;
    if (!doc || (doc.languageId !== "py2cpp" && !this.preview.panel)) {
      this.status.hide();
      return;
    }
    const record = this.records.get(doc.uri.toString());
    const disabled = !settings(doc.uri).enabled;
    const ready = this.gpu.state === "ready" && !record?.error;
    this.status.text = disabled ? "$(circle-slash) Py2Cpp GPU" : ready ? "$(symbol-color) Py2Cpp GPU" : "$(symbol-color) Py2Cpp Lexer";
    this.status.tooltip = disabled ? "GPU 高亮已在设置中关闭" : record?.error || this.gpu.error || ({
      closed: "打开 Py2Cpp 文件后自动启动 GPU 高亮；点击查看预览",
      starting: "正在启动后台 GPU 高亮",
      ready: `GPU 在后台运行${this.gpu.backend ? ` · ${this.gpu.backend}` : ""}；关闭预览不影响高亮`,
      unavailable: "GPU 不可用，保留基础高亮；可重启 GPU 后重试",
    }[this.gpu.state]);
    this.status.show();
  }

  updatePreview() {
    if (this.disposed || !this.preview.panel) return;
    const document = this.focusedDocument;
    const record = document && this.records.get(document.uri.toString());
    const enabled = settings(document?.uri).enabled;
    const current = record?.version === document?.version;
    const snapshot = { state: this.gpu.state, error: record?.error || this.gpu.error, backend: this.gpu.backend, enabled,
      pending: !!(record?.promise || record?.timer) };
    if (document && !document.isClosed) {
      const source = current && record.source !== undefined ? record.source : document.getText();
      snapshot.document = this.metadata(document);
      // The same limit also bounds preview messages and browser rendering.
      if (source.length <= settings(document.uri).maxCharacters) {
        snapshot.source = source;
        if (enabled && current && record.spans) {
          snapshot.spans = record.spans;
          snapshot.elapsedMs = record.elapsedMs;
        }
      } else {
        snapshot.source = "";
        snapshot.note = "文件超过大小上限，保留编辑器基础高亮";
      }
    }
    this.preview.update(snapshot);
  }

  focus(editor) {
    if (this.disposed || !editor) return;
    const previous = this.focusedDocument;
    this.focusedDocument = editor.document;
    if (previous && previous !== editor.document && previous.languageId !== "py2cpp") {
      const old = this.records.get(previous.uri.toString());
      if (old) this.cancel(old);
      this.records.delete(previous.uri.toString());
    }
    this.syncRuntime();
    this.schedule(editor.document, true);
    this.updatePreview();
  }

  openDocument(document) {
    if (this.interested(document)) this.record(document);
    this.syncRuntime();
    this.schedule(document, true);
  }

  openPanel() {
    this.focusedDocument = vscode.window.activeTextEditor?.document || this.focusedDocument;
    this.preview.show();
    this.syncRuntime();
    if (this.focusedDocument) this.schedule(this.focusedDocument, true);
    this.updatePreview();
  }

  onPreviewClosed() {
    if (this.disposed) return;
    // GPU editor work belongs to documents, never to a preview tab.
    for (const [key, record] of this.records) {
      if (record.document.languageId !== "py2cpp") {
        this.cancel(record);
        this.records.delete(key);
      }
    }
    this.syncRuntime();
  }

  async enableCurrent() {
    const document = vscode.window.activeTextEditor?.document;
    if (!document) return void vscode.window.showInformationMessage("请先打开代码文件。");
    if (document.languageId !== "py2cpp") {
      this.previousLanguages.set(document.uri.toString(), document.languageId);
      this.focusedDocument = await vscode.languages.setTextDocumentLanguage(document, "py2cpp");
    } else this.focusedDocument = document;
    this.syncRuntime();
    this.schedule(this.focusedDocument, true);
  }

  async restoreLanguage() {
    const document = vscode.window.activeTextEditor?.document;
    if (!document) return;
    const key = document.uri.toString();
    const language = this.previousLanguages.get(key);
    if (!language) return void vscode.window.showInformationMessage("此文件没有由 Py2Cpp Lexer 保存的语言模式；可点击状态栏语言名称手动选择。");
    this.focusedDocument = await vscode.languages.setTextDocumentLanguage(document, language);
    this.previousLanguages.delete(key);
    this.syncRuntime();
    this.schedule(this.focusedDocument, true);
  }

  refresh() {
    this.syncRuntime();
    if (this.focusedDocument && this.interested(this.focusedDocument)) {
      this.invalidate(this.focusedDocument);
      this.schedule(this.focusedDocument, true);
    }
  }

  restartGpu() {
    if (!this.consumers().length && !(this.preview.panel && settings(this.focusedDocument?.uri).enabled)) return;
    this.gpu.restart(settings(this.focusedDocument?.uri).nodePath);
  }

  configurationChanged(event) {
    if (!event.affectsConfiguration("py2cpp-lexer")) return;
    for (const record of this.records.values()) {
      this.cancel(record);
      this.clearResult(record);
      record.error = "";
    }
    if (event.affectsConfiguration("py2cpp-lexer.nodePath") && this.gpu.state !== "closed") this.gpu.stop();
    this.changed.fire();
    this.start();
  }

  closeDocument(document) {
    const key = document.uri.toString();
    const record = this.records.get(key);
    if (record) this.cancel(record);
    this.records.delete(key);
    if (this.focusedDocument === document) this.focusedDocument = undefined;
    this.syncRuntime();
  }

  diagnostics() {
    return { state: this.gpu.state, error: this.gpu.error, backend: this.gpu.backend,
      session: this.gpu.generation, previewOpen: !!this.preview.panel,
      documents: [...this.records.values()].map((r) => ({ uri: r.document.uri.toString(), version: r.version, tokenCount: (r.data?.length || 0) / 5, error: r.error })),
    };
  }

  dispose() {
    this.disposed = true;
    for (const record of this.records.values()) this.cancel(record);
    this.records.clear();
    this.preview.dispose();
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
    command("restartGpu", () => controller.restartGpu()),
    vscode.window.onDidChangeActiveTextEditor((editor) => controller.focus(editor)),
    vscode.workspace.onDidOpenTextDocument((document) => controller.openDocument(document)),
    vscode.workspace.onDidChangeTextDocument((event) => {
      if (event.contentChanges.length && controller.interested(event.document)) controller.invalidate(event.document);
    }),
    vscode.workspace.onDidCloseTextDocument((document) => controller.closeDocument(document)),
    vscode.workspace.onDidChangeConfiguration((event) => controller.configurationChanged(event)),
  );
  controller.start();
  return { getStatus: () => controller.diagnostics() };
}

function deactivate() {}

module.exports = { activate, deactivate, HighlightController, settings, bounded };
