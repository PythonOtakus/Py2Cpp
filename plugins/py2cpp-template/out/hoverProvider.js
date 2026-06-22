"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateHoverProvider = void 0;
const vscode = require("vscode");
const MACRO_DOCS = {
    PY2CPP_BEGIN: doc("PY2CPP_BEGIN(…)", "块展开：`for` / `if` / `elif` / `else` / `def fn_PascalCase(in_PascalCase…)`。", "T11/T12/T14：须与 `PY2CPP_END` 配对；`elif`/`else` 不可孤立。"),
    PY2CPP_END: doc("PY2CPP_END", "结束当前 `BEGIN` / `IGNORE` / `INJECT_CLASS` 块。", "T11：须与匹配的 `PY2CPP_BEGIN` / `PY2CPP_IGNORE` 成对。"),
    PY2CPP_EVAL: doc("PY2CPP_EVAL(expr)", "构建期 CPython 表达式 → C++ 字面量或 f-string 插值。", "用于 `BEGIN(for|if)` 体内行内常量/循环变量。"),
    PY2CPP_EXEC: doc("PY2CPP_EXEC(stmt)", "独立一行 CPython 语句或已注册 `def` 调用。"),
    PY2CPP_ECHO: doc("PY2CPP_ECHO(expr)", "构建期求值后原样粘贴 C++ 片段；动态键用 `ctx_PascalCase`。", "T25：IGNORE `#define ctx_*` 与 `PY2CPP_ECHO(ctx_*)` 键集合双向一致。"),
    PY2CPP_INCLUDE: doc('PY2CPP_INCLUDE("path")', "相对当前模板目录内联另一片段。", "T8：路径须用 `/`、落在 templates/ 内且目标存在。"),
    PY2CPP_TYPE: doc("PY2CPP_TYPE(ShortName)", "registry 短名 → 限定 C++ 类型（如 `PyStr`）。", "T17：禁止 `PY2CPP_TYPE(PY2CPP_EVAL(…))`；T24：勿手写 core/util/text 全限定名。"),
    PY2CPP_IGNORE: doc("PY2CPP_IGNORE", "clangd 专用块：`#include`、`#define ctx_*` 等；展开时整段剔除。", "T19/T20：`+/-` inject 模板内 `#include py2cpp/…` 与 `#define ctx_*` 须在此块内。"),
    PY2CPP_INJECT_CLASS: doc("PY2CPP_INJECT_CLASS(CppClass)", "仅 `+<stem>.h`：块内 C++ 注入类体尾部。"),
    PY2CPP_BEGIN_SCOPE: doc("PY2CPP_BEGIN_SCOPE", "按模板路径套 `namespace py2cpp::…`。", "T13：须与 `PY2CPP_END_SCOPE` 配对。"),
    PY2CPP_END_SCOPE: doc("PY2CPP_END_SCOPE", "结束 `PY2CPP_BEGIN_SCOPE` 引入的 namespace。"),
};
const RULE_DOCS = {
    T1: "镜像 `~` 文件名不得以 `~`/`+`/`-` 开头（skip 登记除外）",
    T8: "PY2CPP_INCLUDE 路径须 `/`、存在且不越界",
    T14: "BEGIN(def) helper 须 fn_PascalCase，形参 in_PascalCase",
    T16: "BEGIN(for) 名称列表循环变量须 var_PascalCase",
    T17: "禁止 PY2CPP_TYPE(PY2CPP_EVAL(…))",
    T18: "禁止 STL 容器",
    T19: "+/- inject：`#include py2cpp/…` 须在 IGNORE 内",
    T20: "+/- inject：`#define ctx_*` 须在 IGNORE 内",
    T23: "禁止模板内 #pragma once / 手写 include guard",
    T24: "禁止 core/util/text 全限定类型名；用 PY2CPP_TYPE(短名)",
    T25: "ctx_* 须 PascalCase；IGNORE #define 与 PY2CPP_ECHO 键集合一致",
};
function doc(title, ...lines) {
    const md = new vscode.MarkdownString();
    md.appendMarkdown(`**${title}**\n\n`);
    for (const line of lines) {
        md.appendMarkdown(`${line}\n\n`);
    }
    md.appendMarkdown("详见仓库 `docs/codegen-templates.md`。");
    md.isTrusted = true;
    return md;
}
function macroAtPosition(line, character) {
    const re = /\b(PY2CPP_[A-Z_]+)\b/g;
    let match;
    while ((match = re.exec(line)) !== null) {
        const start = match.index;
        const end = start + match[1].length;
        if (character >= start && character <= end) {
            return match[1];
        }
    }
    return undefined;
}
function ruleAtPosition(line, character) {
    const re = /\[(T\d+)\]/g;
    let match;
    while ((match = re.exec(line)) !== null) {
        const start = match.index + 1;
        const end = start + match[1].length;
        if (character >= start && character <= end) {
            return match[1];
        }
    }
    return undefined;
}
class TemplateHoverProvider {
    provideHover(document, position) {
        const line = document.lineAt(position.line).text;
        const rule = ruleAtPosition(line, position.character);
        if (rule && RULE_DOCS[rule]) {
            const md = new vscode.MarkdownString(`**译期规则 ${rule}**：${RULE_DOCS[rule]}`);
            md.isTrusted = true;
            return new vscode.Hover(md);
        }
        const macro = macroAtPosition(line, position.character);
        if (macro && MACRO_DOCS[macro]) {
            return new vscode.Hover(MACRO_DOCS[macro]);
        }
        const ctxRe = /\b(ctx_[A-Za-z0-9_]+)\b/g;
        let ctxMatch;
        while ((ctxMatch = ctxRe.exec(line)) !== null) {
            const start = ctxMatch.index;
            const end = start + ctxMatch[1].length;
            if (position.character >= start && position.character <= end) {
                const md = new vscode.MarkdownString("**ctx 键**：须 `ctx_` + PascalCase（如 `ctx_MakeFn`）。\n\n" +
                    "IGNORE 内 `#define` 与 `PY2CPP_ECHO(ctx_*)` 键集合须双向一致（T25）。");
                md.isTrusted = true;
                return new vscode.Hover(md);
            }
        }
        return undefined;
    }
}
exports.TemplateHoverProvider = TemplateHoverProvider;
