# Py2Cpp Architect（VS Code / Cursor）

在 Py2Cpp 魔改 Python 源上提供 **UE Content Browser 式依赖图** 与 **可视化重构**（`*.arch.json` RefactorPlan）。

> **状态**：P0 + **P1.5 依赖图画布**；详见 [`docs/py2cpp-architect.md`](../../docs/py2cpp-architect.md)。

## 可视化（P1.5）

命令面板：**Py2Cpp Architect: Show Dependency Graph**

| 能力 | 说明 |
|------|------|
| **模块 DAG** | import 边、pan/zoom、双击进符号图 |
| **字段 rename** | 类内字段：右橙引脚 → 左蓝引脚拖线；右键「重命名」 |
| **计划编辑** | 底部可折叠浮层：加载/保存 `*.arch.json`、单项移除、清空、预览 diff、应用 |
| **select 路径** | 字段右键「追加路径」→ 工具栏芯片 + 复制 |
| **Dataclass Schema** | 类节点右键或独立命令 |

**重构文件**：``generated/.cache/architect/plans/<id>.arch.json``（含 `visual.edges` + `ops`）。

符号图中：**从字段橙色引脚拖线**到另一引脚或空白处 → 生成 `rename_symbol` → 预览 diff → 应用。

**范围**：顶部图标工具栏；符号图默认只显示类/字段（FFI 模块函数需点「≡」开启）；右键节点操作，无侧栏。

**前置**：须已有 `generated/.cache/architect/graph.json`（bootstrap 或翻译任意 `.py` 后生成，**v2** 含 `symbols`/`refs`）。

## 与 py2cpp-nav 的关系

| 扩展 | 职责 |
|------|------|
| [py2cpp-nav](../py2cpp-nav/) | F12 跳转；保存时翻译 |
| **py2cpp-architect** | 依赖图画布 + `*.arch.json` / Rename |

## 安装

### 从源码打包（仅需 Python，无需 npm）

```bat
cd plugins\py2cpp-architect
package.bat
```

或仓库根：

```bat
pkg-arch.bat
```

生成 `py2cpp-architect-*.vsix` 后，在扩展视图选择 **Install from VSIX…**。

## 命令

| 命令 | 说明 |
|------|------|
| **Py2Cpp Architect: Show Dependency Graph** | UE 式依赖图画布 |
| **Py2Cpp Architect: Apply Refactor Plan** | 加载 `*.arch.json` → diff → 应用 |
| **Py2Cpp Architect: Rename Symbol (Preview)** | 生成 `*.arch.json` 并预览 |
| **Py2Cpp Architect: Find All References** | 基于 graph + 文本搜索列出引用 |
| **Py2Cpp Architect: Edit Dataclass Schema** | 表格式编辑 @dataclass 字段并重命名 |

## CLI

```bat
python scripts\apply_refactor_plan.py path\to\plan.arch.json --check
python scripts\apply_refactor_plan.py path\to\plan.arch.json --apply
```

## 架构

```text
out/extension.js           →  showDependencyGraph / apply / rename
out/graphStore.js          →  读 graph.json v2
out/architectCanvasPanel.js → Webview 画布 + 计划栏
out/planRunner.js          →  apply_refactor_plan.py
```

译器：`src/codegen/architect_graph.py` → `generated/.cache/architect/graph.json`
