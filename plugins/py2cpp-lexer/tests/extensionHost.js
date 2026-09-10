"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vscode = require("vscode");

async function waitUntil(read, description, timeout = 45000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    const result = await read();
    if (result) return result;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out: ${description}`);
}

async function run() {
  const reportDir = path.resolve(__dirname, "../../../.cache/py2cpp-lexer");
  fs.mkdirSync(reportDir, { recursive: true });
  const report = { editor: vscode.version, scenario: "background-gpu-primary", startedAt: new Date().toISOString(), status: "running", checks: [] };
  let api;
  const persist = () => {
    report.runtime = api?.getStatus();
    const output = JSON.stringify(report, null, 2);
    fs.writeFileSync(path.join(reportDir, "extension-host-results.json"), output);
    fs.writeFileSync(path.join(reportDir, "extension-host-background-results.json"), output);
  };
  const passed = (description) => { report.checks.push(description); persist(); };
  const webviewTabs = () => vscode.window.tabGroups.all.flatMap((group) => group.tabs)
    .filter((tab) => tab.input instanceof vscode.TabInputWebview);
  const ready = (description) => waitUntil(() => {
    const status = api.getStatus();
    if (status.state === "unavailable") throw new Error(status.error);
    return status.state === "ready";
  }, description);
  const tokensFor = async (document) => {
    await waitUntil(() => {
      const status = api.getStatus();
      if (status.state === "unavailable") throw new Error(status.error);
      const record = status.documents.find((item) => item.uri === document.uri.toString());
      if (record?.error) throw new Error(record.error);
      return record?.version === document.version && record.tokenCount > 0;
    }, `GPU token response for ${path.basename(document.uri.path)} version ${document.version}`);
    let tokens;
    await waitUntil(async () => {
      tokens = await vscode.commands.executeCommand("vscode.provideDocumentSemanticTokens", document.uri);
      return tokens?.data?.length > 0;
    }, "VS Code semantic token provider");
    assert.equal(tokens.data.length % 5, 0);
    let line = 0;
    let column = 0;
    for (let i = 0; i < tokens.data.length; i += 5) {
      const delta = tokens.data[i];
      line += delta;
      column = delta ? tokens.data[i + 1] : column + tokens.data[i + 1];
      assert.ok(line < document.lineCount);
      assert.ok(column + tokens.data[i + 2] <= document.lineAt(line).text.length);
    }
    return Array.from(tokens.data);
  };
  persist();
  try {
    const extension = vscode.extensions.getExtension("PythonOtakus.py2cpp-lexer");
    assert.ok(extension, `extension discovered in test host; available: ${vscode.extensions.all.map((item) => item.id).join(", ")}`);
    report.extensionPath = extension.extensionPath;
    if (process.env.PY2CPP_LEXER_EXPECT_EXTENSION_ROOT) {
      assert.equal(path.resolve(extension.extensionPath).toLowerCase(), path.resolve(process.env.PY2CPP_LEXER_EXPECT_EXTENSION_ROOT).toLowerCase(),
        "integration tests must run against the expected installed extension root");
      report.artifact = "installed-vsix";
    }
    const file = path.join(reportDir, "background-main.py2");
    fs.writeFileSync(file, '# 中文 😀\r\nclass Counter:\r\n    value: int = 42\r\n    def get(self):\r\n        return "hello"\r\n');
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
    await vscode.window.showTextDocument(document, { preview: false });
    assert.equal(document.languageId, "py2cpp", ".py2 filename selects the contributed language");
    await waitUntil(() => extension.isActive && extension.exports, "automatic onLanguage extension activation");
    api = extension.exports;
    assert.equal(api.getStatus().previewOpen, false);
    assert.equal(webviewTabs().length, 0, "startup must not create a hidden or visible Webview tab");
    await ready("automatic background WebGPU initialization without openPanel");
    const tokens = await tokensFor(document);
    assert.equal(api.getStatus().previewOpen, false);
    assert.equal(webviewTabs().length, 0);
    assert.ok(api.getStatus().backend, "background runtime reports its real backend");
    passed(`opening .py2 automatically produced ${tokens.length / 5} bounded native GPU tokens without any Webview tab`);

    const secondFile = path.join(reportDir, "background-second.py2");
    fs.writeFileSync(secondFile, "lazy def compute(value: int) -> int:\n    return value * 2\n");
    const second = await vscode.workspace.openTextDocument(vscode.Uri.file(secondFile));
    assert.equal(second.languageId, "py2cpp");
    await tokensFor(second);
    assert.deepEqual(await tokensFor(document), tokens);
    passed("multiple open Py2Cpp documents receive GPU tokens, including a document never focused");

    const session = api.getStatus().session;
    await vscode.commands.executeCommand("py2cpp-lexer.openPanel");
    await waitUntil(() => api.getStatus().previewOpen && webviewTabs().some((tab) => tab.label === "Py2Cpp Lexer"), "preview tab created");
    assert.equal(api.getStatus().session, session);
    assert.deepEqual(await tokensFor(document), tokens);
    const panelTab = webviewTabs().find((tab) => tab.label === "Py2Cpp Lexer");
    assert.ok(await vscode.window.tabGroups.close(panelTab), "preview tab closes");
    await waitUntil(() => !api.getStatus().previewOpen, "preview-only disposal");
    assert.equal(api.getStatus().state, "ready");
    assert.equal(api.getStatus().session, session);
    assert.deepEqual(await tokensFor(document), tokens);
    assert.equal(webviewTabs().length, 0);
    passed("opening and closing preview preserves the GPU session and byte-identical editor tokens");

    const edit = new vscode.WorkspaceEdit();
    edit.insert(document.uri, new vscode.Position(0, 0), "# edited\n");
    assert.ok(await vscode.workspace.applyEdit(edit));
    const version = document.version;
    const editedTokens = await tokensFor(document);
    assert.notDeepEqual(editedTokens, tokens);
    assert.equal(api.getStatus().documents.find((item) => item.uri === document.uri.toString()).version, version);
    assert.equal(api.getStatus().session, session);
    assert.equal(api.getStatus().previewOpen, false);
    await document.save();
    passed("editing after preview closure produces fresh GPU tokens without restarting the session");

    const python = await vscode.workspace.openTextDocument({ language: "python", content: "answer = 42\n" });
    await vscode.window.showTextDocument(python, { preview: false });
    assert.equal(python.languageId, "python");
    await vscode.commands.executeCommand("py2cpp-lexer.enableForCurrentFile");
    assert.equal(vscode.window.activeTextEditor.document.languageId, "py2cpp");
    await tokensFor(vscode.window.activeTextEditor.document);
    assert.equal(api.getStatus().previewOpen, false);
    await vscode.commands.executeCommand("py2cpp-lexer.restoreLanguage");
    assert.equal(vscode.window.activeTextEditor.document.languageId, "python");
    assert.equal(api.getStatus().previewOpen, false);
    await tokensFor(document);
    await tokensFor(second);
    passed("explicit enable and restore preserve Python's original language without opening preview or interrupting other Py2Cpp documents");

    const sessionBeforeRestart = api.getStatus().session;
    await vscode.commands.executeCommand("py2cpp-lexer.restartGpu");
    await ready("background GPU session restart");
    assert.notEqual(api.getStatus().session, sessionBeforeRestart);
    await tokensFor(document);
    await tokensFor(second);
    assert.equal(api.getStatus().previewOpen, false);
    assert.equal(webviewTabs().length, 0);
    passed("restart creates a new background GPU session and refreshes all Py2Cpp documents without showing preview");
    report.status = "passed";
  } catch (error) {
    report.status = "failed";
    report.error = String(error.stack || error);
    throw error;
  } finally {
    report.completedAt = new Date().toISOString();
    persist();
  }
}

module.exports = { run };
