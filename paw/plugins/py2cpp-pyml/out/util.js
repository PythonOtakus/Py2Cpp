"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getConfig = getConfig;
exports.isPymlDocument = isPymlDocument;
exports.indentWidth = indentWidth;
exports.stripComment = stripComment;
exports.wordAt = wordAt;
exports.dollarNameAt = dollarNameAt;
exports.directiveAt = directiveAt;
exports.fromModuleAt = fromModuleAt;

const vscode = require("vscode");

const DIRECTIVE_RE = /@(?:from|def|inline|if|elif|else|for|expand|return)\b/;

function getConfig() {
  return vscode.workspace.getConfiguration("py2cpp-pyml");
}

function isPymlDocument(doc) {
  if (!doc) {
    return false;
  }
  if (doc.languageId === "pyml") {
    return true;
  }
  return !doc.isUntitled && /\.pyml$/i.test(doc.uri.fsPath);
}

/** 行首空白宽度（空格+Tab 按 1 计，与折叠/作用域一致） */
function indentWidth(line) {
  let i = 0;
  while (i < line.length && (line[i] === " " || line[i] === "\t")) {
    i += 1;
  }
  return i;
}

function stripComment(line) {
  let inSingle = false;
  let inDouble = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === "\\" && (inSingle || inDouble)) {
      i += 1;
      continue;
    }
    if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
      continue;
    }
    if (ch === "\"" && !inSingle) {
      inDouble = !inDouble;
      continue;
    }
    if (ch === "#" && !inSingle && !inDouble) {
      return line.slice(0, i).replace(/\s+$/, "");
    }
  }
  return line.replace(/\s+$/, "");
}

function wordAt(line, character) {
  if (character < 0 || character > line.length) {
    return undefined;
  }
  let start = character;
  let end = character;
  const isWord = (c) => /[A-Za-z0-9_$.]/.test(c);
  while (start > 0 && isWord(line[start - 1])) {
    start -= 1;
  }
  while (end < line.length && isWord(line[end])) {
    end += 1;
  }
  if (start === end) {
    return undefined;
  }
  return { text: line.slice(start, end), start, end };
}

/** 光标落在 `$name` 上时返回不含 `$` 的名字与整段 range */
function dollarNameAt(line, character) {
  const word = wordAt(line, character);
  if (!word || !word.text.startsWith("$")) {
    return undefined;
  }
  const name = word.text.slice(1);
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) {
    return undefined;
  }
  return {
    name,
    dollarName: `$${name}`,
    start: word.start,
    end: word.end,
  };
}

function directiveAt(line, character) {
  const re = /@(from|def|inline|if|elif|else|for|expand|return)\b/g;
  let match;
  while ((match = re.exec(line)) !== null) {
    const start = match.index;
    const end = start + match[0].length;
    if (character >= start && character <= end) {
      return { directive: match[1], start, end, full: match[0] };
    }
  }
  return undefined;
}

/** 光标在 `@from` 行的模块路径上时返回路径文本 */
function fromModuleAt(line, character) {
  const m = stripComment(line).match(/^\s*@from\s+(\.+[\w.]*|[\w][\w.]*)\s+import\b/);
  if (!m) {
    return undefined;
  }
  const full = m[0];
  const mod = m[1];
  const start = line.indexOf(mod);
  if (start < 0) {
    return undefined;
  }
  const end = start + mod.length;
  if (character >= start && character <= end) {
    return { module: mod, start, end, linePrefix: full };
  }
  return undefined;
}

exports.DIRECTIVE_RE = DIRECTIVE_RE;
