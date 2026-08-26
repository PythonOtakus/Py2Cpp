# Py2Cpp Architect（可视化大规模重构）设计方案

> **状态**：**方案已定，未实现**（后续另开落地 PR）。  
> **受众**：译器维护者、`py2cpp-nav` / 重构工具链、标准库大规模 API 演进。  
> **相关**：[py2cpp-nav.md](./py2cpp-nav.md)（符号跳转与索引）、[selector.md](./selector.md)（路径查询 DSL）、[runtime-libs.md](./runtime-libs.md)（bootstrap 增量）、[编码规范.md](./编码规范.md)、[参考手册 §4 翻译流水线](./参考手册.md#4-翻译流水线)。

本文是 **元信息、语义图、RefactorPlan、可视化重构** 的单一真相源；插件安装与日常使用见 [`plugins/py2cpp-architect/README.md`](../plugins/py2cpp-architect/README.md)（占位，待实现）。

---

## 1. 背景与动机

Py2Cpp 将受限 Python **静态**译为 C++11，**无 CPython 解释器**，标准库与用户代码的单一真相源为 `py2cpp/` 与 `src/`；`generated/` 仅由 `main.py` 生成，**勿手改**。

大规模演进（标准库域拆分、字段重命名、`@dataclass` schema 变更、`select` 路径批量更新）若依赖手工搜索替换，成本高且易漏改。业界「快速重构 + 数据迁移」的共性是：

| 模式 | 代码侧 | 数据侧 |
|------|--------|--------|
| 单一真相源 + 再生成 | 改 spec → bootstrap | 改 schema → migration 链 |
| 版本化变换 | AST pass / codemod | `v1 → v2` 迁移脚本 |
| 增量失效图 | 脏模块重译 | 脏分区重迁 |
| 稳定边界 | 宿主 ABI 不变，换 plugin | 载荷带 `version` 字段 |

Py2Cpp **已具备一半基础设施**（见 §2）；Architect 补齐 **语义图 → 重构计划 → AST 改写 → 译器/MSVC 验收** 闭环，并通过 VS Code / Cursor 扩展 **py2cpp-architect** 提供可视化入口。

**与进程内热更无关**：代码热更见 [hot-reload.md](./hot-reload.md)；Architect 面向 **源树重构**，验收方式为 bootstrap + `build.bat` / `build_all.bat` + `run *`。

---

## 2. 已有能力（不重复造轮子）

### 2.1 元信息分层

| 层级 | 形态 | 消费方 | 示例 |
|------|------|--------|------|
| **A** | 类型与装饰器 | 译器 codegen | `@dataclass`、`@protocol`、`@enum`、`@serializable`、`@mixin` |
| **B** | 字段级 `@annotation` | 特定 pass | `ProtoFieldMeta`、`PosArgMeta`、`AnimateMeta`；`Self.iterFields` / `Self.getFieldAnnotation` |
| **C** | 译期专用 API | pass 脱糖 | `assign`、`select`、`build`（`TRANSLATOR_ONLY_METHODS`） |
| **D** | 工具索引 | IDE 只读 | `generated/.cache/nav/`（[py2cpp-nav](./py2cpp-nav.md)） |

### 2.2 相关组件

| 组件 | 路径 | 与 Architect 关系 |
|------|------|-------------------|
| 导航索引 | `src/codegen/nav_index.py` | **扩展为语义图**（符号 + 引用 + import 边） |
| 路径选择器 | `src/passes/selector_parse.py`、`src/emit/selector_emit.py` | 重构 UI 的查询 DSL 原型；重命名需同步字符串路径 |
| 静态反射折叠 | `src/passes/static_reflect.py` | `getattr`/`setattr` 编译期解析；重构须保持可折叠 |
| 仓库级 codemod | `scripts/migrate_*.py` | RefactorPlan 批处理的后端参考实现 |
| 跳转扩展 | `plugins/py2cpp-nav` | 共享 `nav` 缓存与 `translateRunner`；Architect **承接** Rename / Find References |

### 2.3 明确不做

| 项 | 说明 |
|----|------|
| 运行时反射驱动重构 | 无 `eval` / 动态 `getattr`；改写须在翻译前完成 |
| 在 `generated/` 上重构 | 派生物可删可再生；只改 `py2cpp/`、`test/`、`examples/`（及必要时 `src/`） |
| 函数体内逐行 Python↔C++ 映射 | 与 nav 非目标一致；语句级拖拽排序不在范围 |
| 替代译器 pass | 业务语义仍由现有 pass 展开；Architect 改 **源码**，不绕过 analyze |
| 一文件一 DLL / 进程内热更 | 见 [hot-reload.md](./hot-reload.md) |

---

## 3. 目标架构

```text
┌──────────────────────────────────────────────────────────────┐
│  py2cpp-architect（VS Code / Cursor 扩展）                    │
│  · 模块依赖图  · @dataclass 字段表  · select 路径构建器       │
│  · Rename / Find References  · RefactorPlan 预览与应用        │
└────────────────────────────┬─────────────────────────────────┘
                             │ RefactorPlan JSON（§5）
┌────────────────────────────▼─────────────────────────────────┐
│  重构引擎（Python：`scripts/apply_refactor_plan.py` 或译器子命令）│
│  · AST 改写（libcst / ast）                                   │
│  · 交叉校验：nav 符号、import 图、select 字面量、@annotation    │
│  · 输出 unified diff；禁止写 generated/                       │
└────────────────────────────┬─────────────────────────────────┘
                             │ 改写后的 .py
┌────────────────────────────▼─────────────────────────────────┐
│  现有验收流水线（单一真相）                                     │
│  bootstrap → build.bat / build_all.bat → run * → nav 索引刷新   │
└──────────────────────────────────────────────────────────────┘
```

### 3.1 设计原则

1. **索引由译器写、扩展只读**（与 nav 一致）；Architect 消费的 `graph.json` 由 `nav_index` 扩展写出，不手改缓存。
2. **冲突须根治**：重构在源树与译器根因处完成，不把绕行 API 扩散到业务代码（见 [编码规范](./编码规范.md)）。
3. **验收 = MSVC 全绿**：UI「应用」仅表示 AST 已写入；完成定义是 `build_all` + `run *` exit 0。
4. **元信息分轨**：影响 codegen 的元信息走源内 `@annotation` / 装饰器；纯 UI 布局走侧车 JSON，应用时须写回 `.py` 或丢弃。

### 3.2 与 Zeus 分工

| 产品 | 职责 |
|------|------|
| **py2cpp-architect** | 程序员向：源码 AST 重构、标准库 API 演进、测试批量更新 |
| **Zeus Editor** | 场景/组件向：`.zas` 等资源、Inspector 改对象名（非源码 AST） |
| **共用** | `@serializable` / `@dataclass` schema 可作为两边读的**类型契约**；磁盘数据迁移在序列化层，不进译器 |

---

## 4. 元信息设计

### 4.1 源内元信息（推荐）

继续扩展现有模式，**不**引入新 Python 语法。

| 形态 | 用途 | 示例 |
|------|------|------|
| 字段 `@annotation` | schema、迁移、UI 分组 | `field: T @RefactorMeta(renamed_from="old")` |
| 类/模块装饰器 | 废弃、域标签 | `@deprecated("use py2cpp.util.list2")` |
| 类型注解 | 重构边界 | `list[Member]` 约束 `select` 末步类型 |
| 译期注释（可选） | IDE 提示 | `# py2cpp:refactor=move_to:py2cpp/alg/foo` |

**判据**：能由译期 `Self.iterFields` / analyze 消费的，放源内；仅影响编辑器展示的，放侧车（§4.2）。

首版 **不强制** 新增 `@RefactorMeta` 装饰器；P0 以 nav 符号表 + 文本/AST 规则为主，避免未实现装饰器被误用。

### 4.2 侧车元信息（IDE 草稿）

```text
generated/.cache/architect/
  graph.json              # 全库语义图（§6）
  plans/<id>.json         # RefactorPlan 草稿（§5）
  plans/<id>.preview.diff # 应用前预览
```

侧车 **不参与 codegen**；「应用计划」必须将变更写回 `py2cpp/` / `test/` / `examples/` 并删除或归档 plan。

---

## 5. RefactorPlan（重构计划 JSON）

### 5.1 顶层结构

```json
{
  "version": 1,
  "id": "rename-member-score-2026-08-26",
  "description": "Member.score → points across dataclass + select paths",
  "created_at": "2026-08-26T15:47:00+08:00",
  "ops": []
}
```

| 字段 | 说明 |
|------|------|
| `version` | Plan schema 版本；引擎不支持则拒绝应用 |
| `id` | 唯一标识，用于日志与 CI |
| `ops` | 有序操作列表；失败时 **整单回滚**（不写盘） |

### 5.2 操作类型（首版子集）

#### `rename_symbol`

```json
{
  "op": "rename_symbol",
  "kind": "field",
  "module": "py2cpp/alg/team.py",
  "owner": "Member",
  "from": "score",
  "to": "points",
  "update_select_literals": true,
  "update_tests": true
}
```

| `kind` | 范围 |
|--------|------|
| `field` / `method` / `class` / `function` | 单模块内符号 |
| `module` | 模块路径重命名（联动 import） |

约束：遵守 [编码规范 §1.0](./编码规范.md#10-标识符命名强制)；`TRANSLATOR_ONLY_METHODS` 内名字禁止作为用户符号。

#### `update_select_path`

```json
{
  "op": "update_select_path",
  "module": "test/alg/test_team.py",
  "from": ".members{.score > 0}",
  "to": ".members{.points > 0}"
}
```

仅当 `from`/`to` 为**完整字符串字面量**且 `parse_selector_path` 可解析时允许；否则翻译期报错，Plan 应用阶段须预检。

#### `move_module`

```json
{
  "op": "move_module",
  "from": "py2cpp/util/foo.py",
  "to": "py2cpp/alg/foo.py",
  "rewrite_imports": true
}
```

须更新 `STDLIB_REL_PATHS` 发现结果所覆盖的所有 import；应用后 **强制 bootstrap**。

#### `replace_text`（逃生阀）

```json
{
  "op": "replace_text",
  "glob": "py2cpp/**/*.py",
  "from": "old_api",
  "to": "new_api",
  "word_boundary": true
}
```

仅用于已有 `scripts/migrate_*.py` 同等场景；应用前须输出 match 计数并由 UI 确认。

### 5.3 应用流程

```text
1. 加载 graph.json + nav manifest（符号存在性）
2. 对每条 op 生成 AST 变更 → 合并为 per-file patch
3. 干跑：parse + 可选单文件 translate（--no-main）预检
4. 用户确认 diff → 写盘
5. 提示：bootstrap（若动 py2cpp/）+ build.bat 触达模块
```

CLI 草案：

```bat
python scripts/apply_refactor_plan.py plans/rename.json --check
python scripts/apply_refactor_plan.py plans/rename.json --apply
```

---

## 6. 语义图（graph.json）扩展

在 [nav_index](./py2cpp-nav.md) shard 之外，bootstrap 或全量索引 pass 写出聚合图：

```json
{
  "version": 1,
  "modules": {
    "py2cpp/util/list": {
      "imports": ["py2cpp/core/protocols", "py2cpp/text/str"],
      "exports": ["list", "PyList"]
    }
  },
  "refs": [
    {
      "from": { "module": "test/misc/test_containers.py", "symbol": "ContainersTests.test_append" },
      "to": { "module": "py2cpp/util/list.py", "symbol": "list.append" },
      "kind": "call"
    }
  ]
}
```

| 边 `kind` | 用途 |
|-----------|------|
| `call` / `read` / `write` | Rename 影响分析 |
| `inherit` / `mixin` | 提取 @mixin 预览 |
| `select_path` | 字符串字面量引用字段名（静态扫描） |

**版本**：`ARCHITECT_GRAPH_VERSION`；与 `NAV_INDEX_VERSION` 独立，但 manifest 可互相引用路径。

---

## 7. 可视化功能（py2cpp-architect 扩展）

### 7.1 命令（草案）

| 命令 | 说明 |
|------|------|
| **Py2Cpp Architect: Show Module Graph** | Webview：模块 import 依赖 |
| **Py2Cpp Architect: Rename Symbol** | 基于 nav + refs 重命名并预览 diff |
| **Py2Cpp Architect: Find All References** | 符号引用列表（跳转 F12 仍走 nav） |
| **Py2Cpp Architect: Edit Dataclass Schema** | 表格式编辑 `@dataclass` 字段（生成 rename/add 计划） |
| **Py2Cpp Architect: Build Select Path** | 点选字段树 → 插入 `receiver.select("…")` 字面量 |
| **Py2Cpp Architect: Apply Refactor Plan** | 加载 `plans/*.json` 并执行 §5.3 |

### 7.2 设置（草案）

| 键 | 默认 | 说明 |
|----|------|------|
| `py2cpp-architect.repoRoot` | （空） | 仓库根；空则探测 `main.py` |
| `py2cpp-architect.generatedDir` | `generated` | 与 nav 一致 |
| `py2cpp-architect.pythonPath` | `python` | 运行 `apply_refactor_plan.py` / `main.py` |
| `py2cpp-architect.autoValidate` | `onApply` | 应用后自动 translate 触达文件 |

### 7.3 与 py2cpp-nav 协作

```text
py2cpp-nav          py2cpp-architect
    │                      │
    ├─ translateRunner ────┤  共享
    ├─ indexStore ─────────┤  只读 nav shard
    └─ DefinitionProvider  └─ ReferenceProvider / RenameProvider / Webview
```

nav 文档中的「Rename / Find All References / 补全 → 后续可选」**迁移至本文**；nav 保持跳转单一职责。

---

## 8. 典型重构场景

| 场景 | UI 操作 | 底层 | 验收 |
|------|---------|------|------|
| `@dataclass` 字段重命名 | 字段表改名 | `rename_symbol` + `update_select_literals` | 域内 `test_*.py` + MSVC |
| 提取 `@mixin` | 勾选方法 → Extract | 生成新模块 + `expand_mixins` 可分析静态方法集 | `test/lang` mixin 测例 |
| 模块搬家 | 拖拽模块节点 | `move_module` + `rewrite_imports` | **全量 bootstrap** + `build_all` |
| API 批量替换 | 规则表 | `replace_text` 或 `migrate_*.py` | `scripts/migrate_* --check` 同等 |
| 序列化 schema 演进 | 字段增删 + version | 源内 `@annotation` + serde pass（非 Architect 实现体） | `test/serde/*` |
| 废弃 API 清扫 | 引用图标红 | `graph.refs` + 可选 `@deprecated` pass（远期） | grep + build |

---

## 9. 落地路线

### P0 — 语义图 + 单模块 Rename（MVP）

- [ ] `nav_index` 或 sibling `architect_graph.py` 写出 `generated/.cache/architect/graph.json`（import 边 + 基础 refs）
- [ ] `scripts/apply_refactor_plan.py`：实现 `rename_symbol`（单模块 field/method/class）
- [ ] `plugins/py2cpp-architect`：Rename 命令 + diff 预览；复用 nav 的 `translateRunner`
- [ ] 文档与 `src/tests/test_architect_plan.py`（plan 解析与干跑）

**验收**：对 `test/misc/test_containers.py` 内局部重命名（测试分支）→ translate + `cl` 通过。

### P1 — 跨文件与 select 联动

- [ ] `graph.refs` 跨模块引用
- [ ] `update_select_path`、`rename_symbol.update_select_literals`
- [ ] Find All References 面板
- [ ] Dataclass Schema 编辑器（只读 → 生成 plan）

### P2 — 模块图与批量迁移

- [ ] `move_module`、Webview 模块依赖图
- [ ] Select 路径构建器
- [ ] CI 钩子：`apply_refactor_plan.py --check` 于 PR
- [ ] 与 `scripts/migrate_*.py` 统一 plan 格式（可选）

---

## 10. 开放问题（待决议）

| ID | 问题 | 倾向 |
|----|------|------|
| Q1 | AST 库选 `libcst`（保留格式）还是仅 `ast`（与译器一致）？ | 首版 `ast` + `ast.unparse`；格式差异用最小 black 式规则或接受 diff 噪声 |
| Q2 | `graph.refs` 精度：仅定义级还是含函数体内调用？ | 定义级 + 函数体内**简单名**调用（与 nav 符号对齐），不做完整类型推断 |
| Q3 | Plan 应用是否默认跑 `build_all`？ | 否；默认 translate 触达文件 + 提示用户跑 `build.bat PATTERN` |
| Q4 | `@deprecated` 是否纳入 P0？ | 否；P2 与引用图联动 |
| Q5 | 插件与 nav 合并为一个扩展？ | **否**；独立 `py2cpp-architect`，共享缓存与 runner 代码（可复制后抽 `py2cpp-common`） |

---

## 11. PR 检查单（实现阶段）

```text
[ ] docs/py2cpp-architect.md 与 plugins/py2cpp-architect/README.md 已同步
[ ] 只改源树；未手改 generated/ 充数（缓存 JSON 由译器/脚本写入除外）
[ ] RefactorPlan version 与 graph version 已文档化
[ ] rename / plan 干跑有 src/tests 覆盖
[ ] 触达模块 bootstrap + MSVC 全绿
[ ] py2cpp-nav.md 已交叉引用本文（Rename/Refs 归属）
```

---

## 12. 关键路径速查

| 用途 | 路径 |
|------|------|
| 本方案 | `docs/py2cpp-architect.md` |
| 插件说明 | `plugins/py2cpp-architect/README.md` |
| 导航索引（依赖） | `src/codegen/nav_index.py`、`docs/py2cpp-nav.md` |
| 路径 DSL | `src/passes/selector_parse.py`、`docs/selector.md` |
| Codemod 参考 | `scripts/migrate_type_pred.py` 等 |
| Plan 应用（待建） | `scripts/apply_refactor_plan.py` |
| 语义图缓存 | `generated/.cache/architect/graph.json` |
| 验收 | `scripts/_bootstrap_runtime.bat`、`build_all.bat`、`run.bat` |

---

## 13. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-08-26 | 初稿：架构、元信息、RefactorPlan、graph 扩展、路线 P0–P2、与 nav/Zeus 分工 |
