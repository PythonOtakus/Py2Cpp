"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PymlHoverProvider = void 0;
const vscode = require("vscode");
const symbolIndex_1 = require("./symbolIndex");
const util_1 = require("./util");

const DIRECTIVE_DOCS = {
  from: {
    title: "@from",
    body: [
      "按 Python 风格模块路径导入用户符号（变量 / `@def` / `@inline`）。",
      "语法：`@from [.]pkg.mod import $name [as $alias]` 或 `import *`。",
      "相对路径以当前模块包为基准；绝对路径自 `moduleRoot` 解析。",
    ],
  },
  def: {
    title: "@def $name(args):",
    body: [
      "定义返回标量的用户函数；主体可含局部变量、增强赋值、`@if` / `@for` 与 `@return`。",
      "不得直接输出 YAML 节点，也不得使用 `@expand`。",
      "调用：在 `= expr` 等表达式中写 `$name(...)`。",
    ],
  },
  inline: {
    title: "@inline $name(args):",
    body: [
      "定义可复用容器片段（mapping 或 sequence）；不使用 `@return`。",
      "主体中非 `$` 开头项组成结果；通过 `@expand $name(...)` 写入目标容器。",
    ],
  },
  expand: {
    title: "@expand expr",
    body: [
      "在 mapping 中按 `dict.update` 浅更新；在 sequence 中按 `list.extend` 插入。",
      "操作数须匹配当前容器类型；标记本身不进入展开后的 YAML。",
    ],
  },
  return: {
    title: "@return expr",
    body: [
      "结束当前 `@def` 调用并返回标量（str / 整数 / 浮点 / bool / null）。",
      "出现在 `@def` 外、返回容器或缺少返回时抛 `PymlError`。",
    ],
  },
  if: {
    title: "@if expr:",
    body: ["条件分支；只能作为完整 mapping / sequence 节点，不可嵌入 scalar。", "可接 `@elif` / `@else`。"],
  },
  elif: {
    title: "@elif expr:",
    body: ["`@if` 链的后续分支。"],
  },
  else: {
    title: "@else:",
    body: ["`@if` / `@elif` 的兜底分支。"],
  },
  for: {
    title: "@for $x in iterable:",
    body: [
      "循环展开；支持 `range`、`.items()` 解包等受限形态。",
      "每轮创建子作用域，循环体输出按序拼接到当前容器。",
    ],
  },
};

const KIND_LABEL = {
  def: "标量函数",
  inline: "容器片段",
  var: "模板变量",
  param: "形参",
  loopvar: "循环变量",
  import: "导入符号",
};

function mdLines(title, lines) {
  const md = new vscode.MarkdownString();
  md.appendMarkdown(`**${title}**\n\n`);
  for (const line of lines) {
    md.appendMarkdown(`${line}\n\n`);
  }
  md.isTrusted = false;
  return md;
}

class PymlHoverProvider {
  provideHover(document, position) {
    if (!(0, util_1.isPymlDocument)(document)) {
      return undefined;
    }
    const line = document.lineAt(position.line).text;
    const dir = (0, util_1.directiveAt)(line, position.character);
    if (dir && DIRECTIVE_DOCS[dir.directive]) {
      const d = DIRECTIVE_DOCS[dir.directive];
      return new vscode.Hover(mdLines(d.title, d.body));
    }

    const dollar = (0, util_1.dollarNameAt)(line, position.character);
    if (dollar) {
      const indent = (0, util_1.indentWidth)(line);
      const def = (0, symbolIndex_1.findDefinition)(document, dollar.name, position.line, indent);
      if (def) {
        const label = KIND_LABEL[def.kind] || def.kind;
        const extra = [];
        if (def.kind === "def" || def.kind === "inline") {
          const params = (def.params || []).map((p) => `$${p}`).join(", ");
          extra.push(`签名：\`${def.dollarName}(${params})\``);
        }
        if (def.kind === "import") {
          extra.push(`来自：\`@from ${def.source}\``);
          if (def.aliasOf) {
            extra.push(`别名自：\`$${def.aliasOf}\``);
          }
        }
        if (def.kind === "var") {
          const raw = document.lineAt(def.line).text;
          const stripped = (0, util_1.stripComment)(raw).trim();
          extra.push(`定义：\`${stripped}\``);
        }
        return new vscode.Hover(mdLines(`$${def.name}`, [`${label}`, ...extra]));
      }
      return new vscode.Hover(
        mdLines(`$${dollar.name}`, ["模板用户符号（`$` 前缀）。未在当前可见作用域找到定义。"]),
      );
    }

    const exprEq = /=/.test(line) && line.indexOf("=") >= 0;
    if (exprEq) {
      const eqIdx = line.indexOf(": =");
      const aug = line.match(/:\s*((?:\+|\-|\*|\/|%)=)/);
      const dynKey = line.match(/^\s*=\s+/);
      if (
        (eqIdx >= 0 && position.character >= eqIdx + 2 && position.character <= eqIdx + 3) ||
        (aug && position.character >= line.indexOf(aug[1]) && position.character <= line.indexOf(aug[1]) + aug[1].length) ||
        (dynKey && position.character >= (0, util_1.indentWidth)(line) && position.character <= (0, util_1.indentWidth)(line) + 1)
      ) {
        if (aug) {
          return new vscode.Hover(
            mdLines(aug[1], [
              "增强赋值：右侧按模板表达式求值；不会创建新变量。",
              "命中外层变量时在当前子作用域遮蔽，不回写外层。",
            ]),
          );
        }
        return new vscode.Hover(
          mdLines("= expr", [
            "模板表达式求值标记；字面量赋值不写等号。",
            "动态 mapping key 写作 `= expr:`。",
          ]),
        );
      }
    }

    return undefined;
  }
}
exports.PymlHoverProvider = PymlHoverProvider;
