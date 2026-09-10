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
  const report = { editor: vscode.version, checks: [] };
  let api;
  try {
    const extension = vscode.extensions.getExtension("PythonOtakus.py2cpp-lexer");
    assert.ok(extension, "extension discovered");
    api = await extension.activate();
    const document = await vscode.workspace.openTextDocument({
      language: "py2cpp",
      content: '# 中文 😀\r\nclass Counter:\r\n    value: int = 42\r\n    def get(self):\r\n        return "hello"\r\n',
    });
    await vscode.window.showTextDocument(document);
    await vscode.commands.executeCommand("py2cpp-lexer.openPanel");
    await waitUntil(() => {
      const status = api.getStatus();
      if (status.state === "unavailable") throw new Error(status.error);
      return status.state === "ready";
    }, "real WebGPU initialization");
    report.checks.push("real upstream parse() initialized WebGPU");
    await waitUntil(() => api.getStatus().documents.some((item) => item.uri === document.uri.toString() && item.version === document.version && item.tokenCount > 0), "GPU token response");
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
    report.checks.push(`native editor returned ${tokens.data.length / 5} correctly bounded semantic tokens`);
    const edit = new vscode.WorkspaceEdit();
    edit.insert(document.uri, new vscode.Position(0, 0), "# edited\n");
    await vscode.workspace.applyEdit(edit);
    const version = document.version;
    await waitUntil(() => api.getStatus().documents.some((item) => item.uri === document.uri.toString() && item.version === version && item.tokenCount > 0), "edited version token response");
    report.checks.push("editing invalidated old version and produced new GPU tokens");

    const python = await vscode.workspace.openTextDocument({ language: "python", content: "answer = 42\n" });
    await vscode.window.showTextDocument(python);
    assert.equal(python.languageId, "python");
    await vscode.commands.executeCommand("py2cpp-lexer.enableForCurrentFile");
    assert.equal(vscode.window.activeTextEditor.document.languageId, "py2cpp");
    await vscode.commands.executeCommand("py2cpp-lexer.restoreLanguage");
    assert.equal(vscode.window.activeTextEditor.document.languageId, "python");
    report.checks.push("explicit language enable and restore preserve Python default");

    await vscode.commands.executeCommand("py2cpp-lexer.restartGpu");
    await waitUntil(() => {
      const status = api.getStatus();
      if (status.state === "unavailable") throw new Error(status.error);
      return status.state === "ready";
    }, "GPU session restart");
    report.checks.push("GPU session restarted successfully");
    await waitUntil(() => api.getStatus().documents.some((item) => item.uri === python.uri.toString() && item.tokenCount > 0), "preview after language restore and GPU restart");
    report.checks.push("restored Python document still previews after restart");
    const panelTab = vscode.window.tabGroups.all.flatMap((group) => group.tabs).find((tab) => tab.input instanceof vscode.TabInputWebview && tab.label === "Py2Cpp Lexer");
    assert.ok(panelTab, "GPU panel exists");
    await vscode.window.tabGroups.close(panelTab);
    await waitUntil(() => api.getStatus().state === "closed", "GPU panel disposal");
    assert.ok(api.getStatus().documents.every((item) => item.tokenCount === 0));
    report.checks.push("closing GPU panel clears cached semantic tokens and closes session");
    report.status = "passed";
  } catch (error) {
    report.status = "failed";
    report.error = String(error.stack || error);
    throw error;
  } finally {
    report.runtime = api?.getStatus();
    fs.writeFileSync(path.join(reportDir, "extension-host-results.json"), JSON.stringify(report, null, 2));
  }
}

module.exports = { run };
