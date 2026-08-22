"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PymlDefinitionProvider = void 0;
const vscode = require("vscode");
const symbolIndex_1 = require("./symbolIndex");
const util_1 = require("./util");

function locationOf(uri, line, character, length) {
  const start = new vscode.Position(line, character);
  const end = new vscode.Position(line, character + Math.max(1, length));
  return new vscode.Location(uri, new vscode.Range(start, end));
}

class PymlDefinitionProvider {
  provideDefinition(document, position) {
    if (!(0, util_1.isPymlDocument)(document)) {
      return undefined;
    }
    const lineText = document.lineAt(position.line).text;
    const moduleRoot = (0, util_1.getConfig)().get("moduleRoot", "") || "";

    // 模块路径 → 目标 .pyml 文件
    const modAt = (0, util_1.fromModuleAt)(lineText, position.character);
    if (modAt) {
      const target = (0, symbolIndex_1.resolveImportPath)(document.uri.fsPath, modAt.module, moduleRoot);
      if (target) {
        return new vscode.Location(vscode.Uri.file(target), new vscode.Position(0, 0));
      }
      return undefined;
    }

    const dollar = (0, util_1.dollarNameAt)(lineText, position.character);
    if (!dollar) {
      return undefined;
    }

    const indent = (0, util_1.indentWidth)(lineText);
    const def = (0, symbolIndex_1.findDefinition)(document, dollar.name, position.line, indent);
    if (!def) {
      return undefined;
    }

    // 导入符号：跳到源模块中的导出定义；失败则跳到 import 行本身
    if (def.kind === "import" && def.source) {
      const targetFile = (0, symbolIndex_1.resolveImportPath)(document.uri.fsPath, def.source, moduleRoot);
      const exportName = def.aliasOf || def.name;
      if (targetFile) {
        const exported = (0, symbolIndex_1.findExportInFile)(targetFile, exportName);
        if (exported) {
          return locationOf(
            vscode.Uri.file(exported.filePath),
            exported.symbol.line,
            exported.symbol.character,
            exported.symbol.dollarName.length,
          );
        }
        return new vscode.Location(vscode.Uri.file(targetFile), new vscode.Position(0, 0));
      }
    }

    return locationOf(document.uri, def.line, def.character, def.dollarName.length);
  }
}
exports.PymlDefinitionProvider = PymlDefinitionProvider;
