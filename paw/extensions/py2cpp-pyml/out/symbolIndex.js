"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseDocumentSymbols = parseDocumentSymbols;
exports.findDefinition = findDefinition;
exports.resolveImportPath = resolveImportPath;
exports.parseFromImports = parseFromImports;
exports.listFoldBlocks = listFoldBlocks;

const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
const util_1 = require("./util");

/**
 * 解析单份 .pyml：可调用片段、变量赋值、@from 导入、可折叠指令块。
 * 缩进规则：子块 indent > 父块；同级结束块。
 * 块 endLine 不含尾部空行（折叠时不吞掉块后空白）。
 */

/** 将 end 回退到 [start, end] 内最后一个非空行（含仅注释视为空） */
function trimTrailingEmptyLines(lines, start, end) {
  let e = end;
  while (e > start) {
    const t = (0, util_1.stripComment)(lines[e] || "").trim();
    if (t) {
      break;
    }
    e -= 1;
  }
  return e;
}

function parseDocumentSymbols(document) {
  const text = typeof document === "string" ? document : document.getText();
  const lines = text.split(/\r?\n/);
  /** @type {Array<{kind:string,name:string,dollarName:string,line:number,character:number,indent:number,endLine:number,params?:string[],source?:string,aliasOf?:string}>} */
  const symbols = [];
  /** @type {Array<{kind:string,line:number,indent:number,endLine:number}>} */
  const blocks = [];
  /** @type {Array<{line:number,module:string,names:Array<{name:string,alias?:string}|{star:true}>}>} */
  const imports = [];

  const openStack = [];

  for (let i = 0; i < lines.length; i += 1) {
    const raw = lines[i];
    const line = (0, util_1.stripComment)(raw);
    if (!line.trim()) {
      continue;
    }
    const indent = (0, util_1.indentWidth)(line);

    while (openStack.length > 0 && indent <= openStack[openStack.length - 1].indent) {
      const done = openStack.pop();
      done.endLine = trimTrailingEmptyLines(lines, done.line, i - 1);
      blocks.push(done);
    }

    const fromMatch = line.match(/^\s*@from\s+(\.+[\w.]*|[\w][\w.]*)\s+import\s+(.+)$/);
    if (fromMatch) {
      const mod = fromMatch[1];
      const namesPart = fromMatch[2].trim();
      const names = [];
      if (namesPart === "*") {
        names.push({ star: true });
      } else {
        for (const part of namesPart.split(",")) {
          const piece = part.trim();
          if (!piece) {
            continue;
          }
          const asMatch = piece.match(/^(\$[A-Za-z_][A-Za-z0-9_]*)\s+as\s+(\$[A-Za-z_][A-Za-z0-9_]*)$/);
          if (asMatch) {
            names.push({ name: asMatch[1].slice(1), alias: asMatch[2].slice(1) });
            const aliasName = asMatch[2].slice(1);
            const aliasStart = raw.indexOf(asMatch[2]);
            symbols.push({
              kind: "import",
              name: aliasName,
              dollarName: `$${aliasName}`,
              line: i,
              character: Math.max(0, aliasStart),
              indent,
              endLine: i,
              source: mod,
              aliasOf: asMatch[1].slice(1),
            });
          } else {
            const nameMatch = piece.match(/^(\$[A-Za-z_][A-Za-z0-9_]*)$/);
            if (nameMatch) {
              const n = nameMatch[1].slice(1);
              names.push({ name: n });
              const nameStart = raw.indexOf(nameMatch[1], raw.indexOf("import"));
              symbols.push({
                kind: "import",
                name: n,
                dollarName: `$${n}`,
                line: i,
                character: Math.max(0, nameStart),
                indent,
                endLine: i,
                source: mod,
              });
            }
          }
        }
      }
      imports.push({ line: i, module: mod, names });
      continue;
    }

    const defMatch = line.match(/^\s*@(def|inline)\s+(\$[A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*:/);
    if (defMatch) {
      const kind = defMatch[1] === "def" ? "def" : "inline";
      const dollarName = defMatch[2];
      const name = dollarName.slice(1);
      const paramsRaw = defMatch[3].trim();
      const params = [];
      if (paramsRaw) {
        for (const p of paramsRaw.split(",")) {
          const pm = p.trim().match(/^(\$[A-Za-z_][A-Za-z0-9_]*)/);
          if (pm) {
            params.push(pm[1].slice(1));
          }
        }
      }
      const char = raw.indexOf(dollarName);
      symbols.push({
        kind,
        name,
        dollarName,
        line: i,
        character: Math.max(0, char),
        indent,
        endLine: i,
        params,
      });
      for (const pname of params) {
        symbols.push({
          kind: "param",
          name: pname,
          dollarName: `$${pname}`,
          line: i,
          character: Math.max(0, raw.indexOf(`$${pname}`)),
          indent: indent + 1,
          endLine: i,
          ownerLine: i,
        });
      }
      openStack.push({ kind, line: i, indent, endLine: i });
      continue;
    }

    const ctrlMatch = line.match(/^\s*@(if|elif|else|for)\b.*:\s*$/);
    if (ctrlMatch) {
      openStack.push({ kind: ctrlMatch[1], line: i, indent, endLine: i });
      const forVars = line.match(/^\s*@for\s+(.+?)\s+in\s+/);
      if (forVars) {
        const varsPart = forVars[1];
        for (const vm of varsPart.matchAll(/\$([A-Za-z_][A-Za-z0-9_]*)/g)) {
          symbols.push({
            kind: "loopvar",
            name: vm[1],
            dollarName: `$${vm[1]}`,
            line: i,
            character: Math.max(0, raw.indexOf(`$${vm[1]}`)),
            indent: indent + 1,
            endLine: i,
            ownerLine: i,
          });
        }
      }
      continue;
    }

    const varMatch = line.match(/^\s*(\$[A-Za-z_][A-Za-z0-9_]*)\s*:/);
    if (varMatch) {
      const dollarName = varMatch[1];
      const name = dollarName.slice(1);
      symbols.push({
        kind: "var",
        name,
        dollarName,
        line: i,
        character: Math.max(0, raw.indexOf(dollarName)),
        indent,
        endLine: i,
      });
      continue;
    }
  }

  while (openStack.length > 0) {
    const done = openStack.pop();
    done.endLine = trimTrailingEmptyLines(lines, done.line, lines.length - 1);
    blocks.push(done);
  }

  // 回填 param/loopvar 的可见区间为所属块 endLine
  for (const sym of symbols) {
    if (sym.kind === "param" || sym.kind === "loopvar") {
      const owner = blocks.find((b) => b.line === sym.ownerLine);
      if (owner) {
        sym.endLine = owner.endLine;
      }
    }
  }
  for (const sym of symbols) {
    if (sym.kind === "def" || sym.kind === "inline") {
      const owner = blocks.find((b) => b.line === sym.line && (b.kind === "def" || b.kind === "inline"));
      if (owner) {
        sym.endLine = owner.endLine;
      }
    }
  }

  return { symbols, blocks, imports, lineCount: lines.length };
}

function symbolVisibleAt(sym, line, indent) {
  if (sym.kind === "param" || sym.kind === "loopvar") {
    return line >= sym.line && line <= sym.endLine && indent >= sym.indent;
  }
  if (sym.kind === "def" || sym.kind === "inline") {
    return true;
  }
  if (sym.kind === "import") {
    return line >= sym.line;
  }
  if (sym.kind === "var") {
    // 同作用域：定义行之后；子作用域可读外层（indent 更深或同级但行号更大）
    if (line < sym.line) {
      return false;
    }
    return true;
  }
  return false;
}

/**
 * 在文档内查找 `$name` 定义；优先参数/循环变量，再 import，再 def/inline，再最近的 var。
 */
function findDefinition(document, name, atLine, atIndent) {
  const { symbols } = parseDocumentSymbols(document);
  const candidates = symbols.filter((s) => s.name === name && symbolVisibleAt(s, atLine, atIndent));
  if (candidates.length === 0) {
    return undefined;
  }
  const rank = (k) => {
    switch (k) {
      case "param":
        return 0;
      case "loopvar":
        return 1;
      case "import":
        return 2;
      case "def":
      case "inline":
        return 3;
      case "var":
        return 4;
      default:
        return 9;
    }
  };
  candidates.sort((a, b) => {
    const ra = rank(a.kind);
    const rb = rank(b.kind);
    if (ra !== rb) {
      return ra - rb;
    }
    // 同种：取光标前最近、缩进最深（最内层）
    if (a.indent !== b.indent) {
      return b.indent - a.indent;
    }
    return b.line - a.line;
  });
  // 对 var：只要 line <= atLine 的最近定义
  const best = candidates.find((c) => {
    if (c.kind === "var") {
      return c.line <= atLine;
    }
    return true;
  }) || candidates[0];
  return best;
}

function parseFromImports(document) {
  return parseDocumentSymbols(document).imports;
}

function listFoldBlocks(document) {
  return parseDocumentSymbols(document).blocks.filter((b) => b.endLine > b.line);
}

/**
 * 将 `@from` 模块路径解析为文件系统路径。
 * @param {string} currentFile
 * @param {string} moduleSpec  如 `.ui.button` / `game.ui.button`
 * @param {string} [moduleRoot]
 */
function resolveImportPath(currentFile, moduleSpec, moduleRoot) {
  const m = moduleSpec.match(/^(\.*)(.*)$/);
  if (!m) {
    return undefined;
  }
  const dots = m[1].length;
  const rest = m[2];
  if (!rest && dots > 0) {
    return undefined;
  }
  const fileDir = path.dirname(currentFile);

  if (dots === 0) {
    const rel = rest.replace(/\./g, path.sep) + ".pyml";
    if (moduleRoot && moduleRoot.trim()) {
      const abs = path.resolve(moduleRoot, rel);
      if (fs.existsSync(abs)) {
        return abs;
      }
    }
    // 自当前文件向上探测：任意祖先下存在 rel
    let dir = fileDir;
    for (let i = 0; i < 24; i += 1) {
      const candidate = path.join(dir, rel);
      if (fs.existsSync(candidate)) {
        return candidate;
      }
      const parent = path.dirname(dir);
      if (parent === dir) {
        break;
      }
      dir = parent;
    }
    // 工作区搜索
    const folders = vscode.workspace.workspaceFolders || [];
    for (const folder of folders) {
      const candidate = path.join(folder.uri.fsPath, rel);
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    }
    return undefined;
  }

  // 相对导入：dots 个点 → 从当前文件目录上溯 dots-1 层
  let base = fileDir;
  for (let i = 0; i < dots - 1; i += 1) {
    const parent = path.dirname(base);
    if (parent === base) {
      break;
    }
    base = parent;
  }
  const target = path.join(base, rest.replace(/\./g, path.sep) + ".pyml");
  if (fs.existsSync(target)) {
    return target;
  }
  return target;
}

/**
 * 在目标文件中查找导出符号（根级 def/inline/var）。
 */
function findExportInFile(filePath, name) {
  if (!fs.existsSync(filePath)) {
    return undefined;
  }
  const text = fs.readFileSync(filePath, "utf8");
  const { symbols } = parseDocumentSymbols(text);
  const exported = symbols.filter(
    (s) =>
      s.name === name &&
      (s.kind === "def" || s.kind === "inline" || (s.kind === "var" && s.indent === 0)),
  );
  if (exported.length === 0) {
    return undefined;
  }
  // 优先 def/inline
  exported.sort((a, b) => {
    const score = (k) => (k === "def" || k === "inline" ? 0 : 1);
    return score(a.kind) - score(b.kind) || a.line - b.line;
  });
  return { filePath, symbol: exported[0] };
}

exports.findExportInFile = findExportInFile;
