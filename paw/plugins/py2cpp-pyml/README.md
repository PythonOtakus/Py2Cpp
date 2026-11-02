# Py2Cpp PyML（VS Code）

为 `.pyml`（PyML）提供：

- **语法高亮**：YAML 基底 + `$name`、`= expr` / 增强赋值、`@if` / `@for` / `@def` / `@inline` / `@expand` / `@from` / f-string；按 C++/Python 习惯区分函数 / inline / 形参 / 变量 / `and`·`or`·`not`·`if`·`else` 等 scope
- **悬停提示**：指令与 `$` 符号说明（含本文件内定义种类；不链到仓库文档）
- **跳转定义**：`$name` → `@def` / `@inline` / 变量 / 形参 / 循环变量；导入符号与 `@from` 模块路径 → 目标 `.pyml`
- **代码折叠**：指令块 + mapping 缩进块（`offSide` + FoldingRangeProvider）

## 依赖

- VS Code / Cursor ≥ 1.85
- 无需 Python / npm（扩展为纯 JavaScript）

## 安装

```bat
cd plugins\py2cpp-pyml
package.bat
```

或仓库根：

```bat
pkg-pyml.bat
```

生成 `py2cpp-pyml-0.1.2.vsix` 后，在扩展视图选择 **Install from VSIX…**。

## 开发调试

1. 打开 `plugins/py2cpp-pyml`
2. 直接编辑 `out/*.js`（无 TypeScript 编译）
3. F5 启动 Extension Development Host
4. 在新窗口打开含 `.pyml` 的工作区（可用 `test/serde/pyml_modules/`）

## 设置

| 键 | 默认 | 说明 |
|----|------|------|
| `py2cpp-pyml.moduleRoot` | （空） | 绝对模块路径解析根；空则自当前文件向上探测 |
| `py2cpp-pyml.enableFolding` | `true` | 指令/缩进块折叠 |

## 架构

```
out/extension.js
  → hoverProvider.js
  → definitionProvider.js
  → foldingProvider.js
  → symbolIndex.js
syntaxes/pyml.tmLanguage.json
language-configuration.json
```

语法语义见仓库 `docs/serde-pyml.md`。
