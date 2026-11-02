"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode = require("vscode");
const definitionProvider_1 = require("./definitionProvider");
const foldingProvider_1 = require("./foldingProvider");
const hoverProvider_1 = require("./hoverProvider");

const SELECTOR = { language: "pyml" };

function activate(context) {
  context.subscriptions.push(
    vscode.languages.registerHoverProvider(SELECTOR, new hoverProvider_1.PymlHoverProvider()),
  );
  context.subscriptions.push(
    vscode.languages.registerDefinitionProvider(SELECTOR, new definitionProvider_1.PymlDefinitionProvider()),
  );
  context.subscriptions.push(
    vscode.languages.registerFoldingRangeProvider(SELECTOR, new foldingProvider_1.PymlFoldingProvider()),
  );
}
exports.activate = activate;

function deactivate() {}
exports.deactivate = deactivate;
