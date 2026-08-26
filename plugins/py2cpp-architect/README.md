# Py2Cpp Architect（VS Code / Cursor）

在 Py2Cpp 魔改 Python 源上提供 **大规模重构** 与 **可视化语义操作**（模块依赖图、`@dataclass` 字段编辑、Rename、Find References、`select` 路径构建、RefactorPlan 预览与应用）。

> **状态**：**未实现** — 当前仅为设计占位；完整方案见 [`docs/py2cpp-architect.md`](../../docs/py2cpp-architect.md)。

## 与 py2cpp-nav 的关系

| 扩展 | 职责 |
|------|------|
| [py2cpp-nav](../py2cpp-nav/) | Python ↔ C++ **跳转**（F12）；保存时翻译并更新 nav 索引 |
| **py2cpp-architect**（本文） | **重构**与语义图；消费 `generated/.cache/nav/` 与 `generated/.cache/architect/` |

两者共享仓库根、`main.py` 翻译与缓存目录约定；**不合并**为单一扩展（见设计文档 §10 Q5）。

## 依赖（计划）

- VS Code / Cursor ≥ 1.85
- Python 3.10+（运行 `scripts/apply_refactor_plan.py` 与 `main.py`）
- 已安装 [py2cpp-nav](../py2cpp-nav/)（推荐，非硬依赖）
- 工作区为 Py2Cpp 仓库根

## 安装

实现前无 `.vsix`。落地后预期：

```bat
cd plugins\py2cpp-architect
package.bat
```

或仓库根 `pkg-architect.bat`（待建）。

## 计划命令

| 命令 | 说明 |
|------|------|
| **Py2Cpp Architect: Show Module Graph** | 模块 import 依赖 Webview |
| **Py2Cpp Architect: Rename Symbol** | 重命名并预览 diff |
| **Py2Cpp Architect: Find All References** | 符号引用列表 |
| **Py2Cpp Architect: Apply Refactor Plan** | 应用 `RefactorPlan` JSON |

详见 [`docs/py2cpp-architect.md`](../../docs/py2cpp-architect.md) §7。

## 架构（计划）

```text
out/extension.js  →  planRunner.js     →  scripts/apply_refactor_plan.py
                 →  graphView.js       →  generated/.cache/architect/graph.json
                 →  indexStore.js      →  generated/.cache/nav/（只读，与 nav 共享）
```

## 开发状态

| 项 | 状态 |
|----|------|
| 设计文档 | ✅ `docs/py2cpp-architect.md` |
| `apply_refactor_plan.py` | ⏳ 未建 |
| `architect_graph` 译器写出 | ⏳ 未建 |
| 扩展 `out/` | ⏳ 未建 |

实现时请同步更新本文与 `docs/py2cpp-architect.md` §11 PR 检查单。
