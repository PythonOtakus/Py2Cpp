# Py2Cpp Template Linter（VS Code）

对 `templates/**/*.h` / `templates/**/*.inl` 提供：

- **Problems 诊断**：复用仓库 `src/codegen/template_conventions.py` 的译期 **R\*** 规则（bootstrap 同款）
- **悬停提示**：`PY2CPP_*` 宏、`ctx_*` 键、常见 `[Rxxxx]` 规则说明
- **配对宏高亮**：`PY2CPP_BEGIN`/`END`、`IGNORE`、`INJECT_CLASS`、`BEGIN_SCOPE`/`END_SCOPE` 按嵌套深度三级配色（由外向内黄→紫→蓝），光标所在块的开/闭宏加强强调
- **块折叠**：每个配对宏块可折叠（行首 gutter 折叠控件）

## 依赖

- VS Code / CursorType ≥ 1.85
- Python 3.10+（与 Py2Cpp 译器相同），且能 `import src.codegen.template_conventions`
- 工作区为 Py2Cpp 仓库根，或在设置中指定 `py2cpp-template.repoRoot`

## 安装

### 从源码打包（仅需 Python，无需 npm）

```bat
cd plugins\py2cpp-template
package.bat
```

或仓库根：

```bat
pkg-tpl.bat
```

`package.py` 按 `.vscodeignore` 收集 `out/`、`python/`、`package.json` 等，生成 OPC 格式 `py2cpp-template-0.2.0.vsix`。在 VS Code / CursorType 中选择 **Extensions → … → Install from VSIX…** 安装。

## 开发调试

1. 在 VS Code / CursorType 中打开 `plugins/py2cpp-template`
2. 扩展源码为 **纯 JavaScript**（`out/*.js`），直接编辑即可，无需 TypeScript / npm 编译
3. 本目录 `package.json` 为 VS Code 扩展清单（非 Node 工程）；仓库根已 `npm.exclude` 本路径，插件目录内 `npm.autoDetect` 为 `off`
4. 按 F5 启动 Extension Development Host
5. 在新窗口打开 Py2Cpp 仓库，编辑 `templates/` 下文件

打包扩展：`python package.py` 或 `package.bat`（`package.json` 的 `scripts.package` 同义，仅供 npm 任务检测兼容）。

## 命令

| 命令 | 说明 |
|------|------|
| **Py2Cpp: Lint Current Template File** | 仅检查当前打开的模板 |
| **Py2Cpp: Lint All Templates** | 全量 T* 扫描；已打开模板文件的诊断会更新 |

保存文件、编辑时（500ms 防抖）也会自动 lint 当前文件。

## 设置

| 键 | 默认 | 说明 |
|----|------|------|
| `py2cpp-template.pythonPath` | `python` | Python 可执行文件 |
| `py2cpp-template.repoRoot` | （空） | 仓库根；空则自动查找含 `main.py` + `templates/` 的目录 |
| `py2cpp-template.enableDiagnostics` | `true` | 是否自动诊断 |
| `py2cpp-template.includeWarnings` | `true` | 是否显示 warning（如 R0202） |
| `py2cpp-template.enableMacroPairs` | `true` | 配对宏三级高亮与 DocumentType Highlight |
| `py2cpp-template.enableMacroFolding` | `true` | 配对宏块代码折叠 |

## 架构

```
out/extension.js  →  lintRunner.js  →  python/lint_cli.py
                →  macroPairs.js / macroHighlight.js / macroFolding.js
                                      ↓
                         src/codegen/template_conventions.py
```

| 文件 | 作用 |
|------|------|
| `out/extension.js` | 激活、lint 调度、注册 provider |
| `out/lintRunner.js` | 调用 Python lint CLI |
| `out/hoverProvider.js` | 宏与 T* 悬停 |
| `out/macroPairs.js` | 配对宏栈解析 |
| `out/macroHighlight.js` | 三级装饰高亮 |
| `out/macroFolding.js` | 块折叠 |
| `out/util.js` | 仓库根探测、模板路径判定 |

规则详情见仓库根 `docs/codegen-templates.md` §11.1。
