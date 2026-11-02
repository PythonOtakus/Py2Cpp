"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PymlFoldingProvider = void 0;
const vscode = require("vscode");
const symbolIndex_1 = require("./symbolIndex");
const util_1 = require("./util");

const FOLD_KEY_RE =
  /^\s*(?:\$[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][\w.-]*|"[^"]*"|'[^']*'|=.+)\s*:\s*$/;

class PymlFoldingProvider {
  provideFoldingRanges(document) {
    if (!(0, util_1.isPymlDocument)(document)) {
      return undefined;
    }
    if (!(0, util_1.getConfig)().get("enableFolding", true)) {
      return undefined;
    }

    const seen = new Set();
    const ranges = [];

    const trimEnd = (start, end) => {
      let e = end;
      while (e > start) {
        const t = (0, util_1.stripComment)(document.lineAt(e).text).trim();
        if (t) {
          break;
        }
        e -= 1;
      }
      return e;
    };

    const add = (start, end) => {
      const trimmed = trimEnd(start, end);
      if (trimmed <= start) {
        return;
      }
      const key = `${start}:${trimmed}`;
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      ranges.push(new vscode.FoldingRange(start, trimmed, vscode.FoldingRangeKind.Region));
    };

    for (const block of (0, symbolIndex_1.listFoldBlocks)(document)) {
      add(block.line, block.endLine);
    }

    const lineCount = document.lineCount;
    for (let i = 0; i < lineCount; i += 1) {
      const stripped = (0, util_1.stripComment)(document.lineAt(i).text);
      if (!FOLD_KEY_RE.test(stripped)) {
        continue;
      }
      if (/^\s*@(?:def|inline|if|elif|else|for)\b/.test(stripped)) {
        continue;
      }
      const indent = (0, util_1.indentWidth)(stripped);
      let end = i;
      for (let j = i + 1; j < lineCount; j += 1) {
        const next = (0, util_1.stripComment)(document.lineAt(j).text);
        if (!next.trim()) {
          // 块后空行不计入折叠终点；中间空行也不把 end 推过去
          continue;
        }
        if ((0, util_1.indentWidth)(next) <= indent) {
          break;
        }
        end = j;
      }
      add(i, end);
    }

    return ranges;
  }
}
exports.PymlFoldingProvider = PymlFoldingProvider;
