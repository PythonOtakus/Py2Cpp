# Py2Cpp Architect（VS Code / Cursor）

在 Py2Cpp 魔改 Python 源上提供 **UE Content Browser 式依赖图** 与 **可视化重构**（`*.arch.json` RefactorPlan）。

> **状态**：P0 + **P1.5 依赖图画布**；详见 [`docs/py2cpp-architect.md`](../../docs/py2cpp-architect.md)。

## 可视化（P1.5）

命令面板：**Py2Cpp Architect: Show Dependency Graph**

| 区域 | 内容 |
|------|------|
| **画布** | L1 **模块 DAG**（import 有向边，pan/zoom，分层布局） |
| **符号图** | 双击模块 → 类/字段节点 + inherit / field_type 边 |
| **检视器** | 选中节点详情；字段可加入 rename 计划 |
| **计划栏** | 待执行 `ops`；橙色虚线 = 可视化预览边 |

**重构文件**：``generated/.cache/architect/plans/<id>.arch.json``（含 `visual.edges` + `ops`）。

符号图中：**从字段橙色引脚拖线**到另一引脚或空白处 → 生成 `rename_symbol` → 预览 diff → 应用。

**范围**：工具栏可选「焦点 2-hop / 当前域 / 全部模块」。

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
