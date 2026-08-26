# Py2Cpp Navigation（符号双向跳转）完整方案

状态：**v3 已落地**（A–G：property/staticproperty、type alias、enum、union variant、protocol/mixin/delegate、解析体验）。  
本文是 **索引格式、覆盖矩阵与验收** 的单一真相源；插件安装与日常使用见 [`plugins/py2cpp-nav/README.md`](../plugins/py2cpp-nav/README.md)。

相关文档：[参考手册 §8 装饰器](./参考手册.md#8-装饰器与翻译期展开)、[编码规范 §4 / §6.2](./编码规范.md)、译器索引实现 `src/codegen/nav_index.py`。

**VS Code / Cursor 扩展打包**（仓库根，无需 npm）：

| 扩展 | 打包脚本 | 插件目录 `package.bat` |
|------|----------|------------------------|
| py2cpp-nav | `pkg-nav.bat` | `plugins/py2cpp-nav/package.bat` |
| py2cpp-pyml | `pkg-pyml.bat` | `plugins/py2cpp-pyml/package.bat` |
| py2cpp-template | `pkg-temp.bat` | `plugins/py2cpp-template/package.bat` |
| py2cpp-architect | `pkg-arch.bat` | `plugins/py2cpp-architect/package.bat` |

---

## 1. 目标与非目标

### 1.1 目标

在 **Python 源**（`py2cpp/`、`test/`、`examples/`、`ffi/**/*.pyi`）与 **`generated/` 生成 C++**（`.h` / `.inl` / 入口 `.cpp`）之间提供符号级 **Go to Definition**（F12 / Ctrl+点击）双向跳转：

| 方向 | 典型场景 |
|------|----------|
| **Python → C++** | `class list` / `def reverse` / 字段 / property / `AggModeEnum.Min` / `Result.Ok` → `.h` / `.inl` |
| **C++ → Python** | `PyList::append`、`capacity__set`、`enum class AggModeEnum` 成员 → 对应 `.py` / `.pyi` 行 |

覆盖粒度：**定义级符号**（类、成员、模块函数、别名、枚举成员、union 变体、delegate 等），**不是**函数体内逐行映射。

### 1.2 非目标（明确不做）

| 项 | 说明 |
|----|------|
| 函数体内任意语句行映射 | 调试轨迹用 `--debug`，不属于 nav |
| `templates/**` 编辑与跳转 | 归 [py2cpp-template](../plugins/py2cpp-template/README.md) |
| Rename / Find All References / 大规模重构 | 归 [py2cpp-architect](./py2cpp-architect.md) |
| 补全 | 后续可选 |
| 手改 `generated/` 作为索引源 | 索引仅由译器在翻译结束时写入 |

### 1.3 设计原则

1. **索引由译器写、扩展只读 JSON**（`generated/.cache/nav/`）。
2. **路径与模块同形**：shard 为 `modules/<module_path>.json`。
3. **冲突须根治**：前向声明 / 调用点误匹配等在索引或解析层修。
4. **与生成物命名一致**：property 用 `patterns.property_*_method_for`（`name__get` / `name__set`）。
5. **无 C++ 类型的构造**：`@protocol` 仅 Python；`@mixin` 方法可附宿主 `.inl`；`@annotation` 不索引 C++。

---

## 2. 架构

```text
Python 保存 / 命令 Translate
        │
        ▼
python main.py <file> -o generated [--no-main]
        │  translate 结束
        ▼
src/codegen/nav_index.py  →  write_nav_index(translator)
        │
        ▼
generated/.cache/nav/
  manifest.json
  modules/<module_path>.json
        │  FileSystemWatcher / reload
        ▼
plugins/py2cpp-nav
  extension.js → definitionProvider.js → indexStore.js
                 symbolParse.js（光标上下文）
```

| 组件 | 路径 | 职责 |
|------|------|------|
| 索引写入 | `src/codegen/nav_index.py` | `ClassInfo` / 别名 / 枚举 / 变体 / delegate / 模块函数 → `.h`/`.inl` 行号；`.h`/`.inl` 未新于 shard 则跳过该模块 |
| 挂钩 | `src/translator.py`（`translate_file` 末尾） | 调用 `write_nav_index` |
| 译器单测 | `src/tests/test_nav_index.py` | A–E 关键路径 + 前向声明 / impl 调用点 |
| 扩展 | `plugins/py2cpp-nav/out/*.js` | DefinitionProvider、限定名、setter 优先 |
| 打包 | `pkg-nav.bat` / `plugins/py2cpp-nav/package.bat` | 打 vsix（无需 npm） |

### 2.1 工作流要点

- 标准库单文件翻译：`project_root` 须为仓库根，否则 `module_order` 空、索引不更新。
- `py2cpp/` 翻译附加 `--no-main`；`test/`、`examples/` 保留 `main()`。
- 全量标准库索引：`python main.py py2cpp\__init__.py -o generated --no-main`。
- 未翻译模块无 shard，跳转静默失败并交给其它 provider（如 clangd）。

---

## 3. 索引格式

### 3.1 目录布局

```text
generated/.cache/nav/
  manifest.json
  modules/
    py2cpp/util/list.json
    py2cpp/alg/agg_mode.json
    test/misc/test_chr_ord.json
    ffi/sqlite/sqlite3.json
```

- **禁止**旧扁平名 `py2cpp__util__list.json`（写入新路径时删除同模块 legacy 文件）。
- `NAV_INDEX_VERSION`：当前 **3**（A–G：新 kind、`role`、variant `tag`/`payload`）。

### 3.2 `manifest.json`（摘要）

```json
{
  "version": 3,
  "generatedRoot": "generated",
  "repoRoot": ".",
  "updatedAt": "…",
  "modules": {
    "py2cpp/util/list": {
      "shard": "modules/py2cpp/util/list.json",
      "pyFile": "py2cpp/util/list.py",
      "artifacts": {
        "h": "generated/runtime/py2cpp/util/list.h",
        "inl": "generated/runtime/py2cpp/util/list.inl",
        "cpp": null
      },
      "symbolCount": 120,
      "updatedAt": "…"
    }
  }
}
```

### 3.3 模块 shard：符号条目

| 字段 | 说明 |
|------|------|
| `kind` | 见 §3.4 |
| `module` | 模块路径 |
| `name` / `cppName` | Python / C++ 名 |
| `cppQual` | 可选全限定 |
| `owner` | 所属类 / union / enum / variant |
| `role` | 可选：`getter` / `setter` / `postsetter` / `enum` / `union` / `mixin` / `protocol` 等 |
| `py` | `{ file, line, endLine, column? }` |
| `cpp` | `{ decl?, impl?, tag?, payload?, implModule? }`；路径取自模块 `artifacts`（mixin 宿主可用 `implModule`） |

### 3.4 `kind` 一览

| `kind` | 状态 | 含义 |
|--------|------|------|
| `class` | ✅ | 实体类 / `@enum`（`role=enum`）/ `@union`（`role=union`） |
| `method` | ✅ | 实例/静态方法、dunder allowlist |
| `field` | ✅ | 实例字段；union 变体载荷字段 `owner=Variant` |
| `property` | ✅ | `@property` / `@staticproperty`；`role` 区分 get/set/postset |
| `function` | ✅ | 模块级函数 |
| `type_alias` | ✅ | 类内 / 模块 `type`（含条件别名）→ `using` |
| `enum_member` | ✅ | `@enum` 成员 → `Enum::Member` |
| `variant` | ✅ | `@union` 内 `@variant`；优先工厂声明，附 `tag`/`payload` |
| `delegate` | ✅ | `@delegate` → `class UIEventDelegate` / `using` |
| `protocol` | ✅ | 仅 Python（无伪 C++ 类） |
| `mixin` | ✅ | 类仅 Python；方法可附宿主 `.inl` |
| `descriptor` | ✅ | 描述符源仅 Python（宿主展开见宿主 property） |

扩展查询：`member` 匹配 method/field/property/type_alias/enum_member/variant/delegate；`class` 匹配 class/protocol/mixin/descriptor/delegate。

### 3.5 C++ 行号匹配规则

| 规则 | 说明 |
|------|------|
| 类声明 | 跳过前向声明；支持 `enum class Name` |
| 方法实现 | 跳过 `this->fn(`；优先 `::fn(` |
| property | `name__get` / `name__set` / `name__postset` |
| variant | 优先 `static … Ok(`；无则 Tag；`jumpPreference=both` 时加 tag/payload |

---

## 4. 覆盖矩阵

| 构造 | Python 示例 | C++ 形态 | Nav |
|------|-------------|----------|-----|
| 实体类 | `class list[T]` | `class PyList` | ✅ |
| `@native_name` | `@native_name("PyList")` | 重命名类 | ✅ |
| 实例方法 | `def reverse` | `PyList::reverse` | ✅ |
| 字段 | `data: T[:]` | 成员 | ✅ |
| `@property` getter | `def capacity` | `capacity__get` | ✅ |
| `@property.setter` | `@property.setter` | `capacity__set` | ✅ |
| `@staticproperty` | `def zero` | `static zero__get` | ✅ |
| 模块函数 | `def open` | 自由函数 | ✅ |
| 类内 `type` | `type Item = int` | `using Item` | ✅ |
| 模块 `type`（含条件） | `type OkOf[…] = …` | `using` | ✅ |
| `@enum` 类型 | `class AggModeEnum` | `enum class AggModeEnum` | ✅ |
| `@enum` 成员 | `Min = 0` | `AggModeEnum::Min` | ✅ |
| `@union` / `@variant` | `Result.Ok` | 工厂 / Tag / Payload | ✅ 工厂优先 |
| `@mixin` | mixin 方法 | 宿主 `.inl` | ✅ py + 宿主 |
| `@descriptor` | 描述符源 | — | ✅ 仅 Python |
| `@annotation` | 元数据 | — | ❌ 不索引 |
| `@protocol` | `IteratorType` | — | ✅ 仅 Python |
| `@delegate` | `def UIEventDelegate` | `class UIEventDelegate` | ✅ |
| `@overload` | 同名多签名 | 多重载 | ✅ 全部列出 |
| `@native` + 模板 | FFI / paste | `.inl` | ⚠ impl 可能在模板 |
| FFI `.pyi` | `sqlite3.pyi` | `ffi::…` | ⚠ 大库未全验 |
| `friends=` | 友元 | `friend class` | ❌ 不单独索引 |

---

## 5. 已修缺陷（历史）

| ID | 现象 | 修复 |
|----|------|------|
| BUG-1 | `list.reverse` → 错误文件 | enclosing class 缩进 + method owner |
| BUG-2 | `_timComputeMinrun` → 调用点 | `_impl_definition_line` 跳过 `this->` |
| BUG-3 | 前向声明 | `_class_decl_line` 跳过 `class Foo;` |
| BUG-4 | setter 用 `set_*` | `property_setter_method_for` → `name__set` |
| BUG-5 | `@staticproperty` 缺失 | 索引 `static_properties` |
| BUG-6 | protocol 伪 C++ | `kind=protocol`，无 cpp 锚点 |
| BUG-7 | delegate 空 shard | `kind=delegate` 匹配 `class UIEventDelegate` |

---

## 6. 扩展解析约定（v3）

| 场景 | 行为 |
|------|------|
| `obj.attr =` 赋值左值 | 优先 `role=setter` |
| 读位点 property | 优先 getter，去掉同名 setter |
| `Cls.attr` / `E.MEM` / `U.Variant` | `qualified` → enum_member / variant / property |
| `new.Ok` / `Self.Ok` | `kind=variant` |
| `capacity__get` / `__set`（C++） | 回跳 Python property |
| `enum class` / `Min = 0` | 回跳 enum / enum_member |
| `@overload` | 同分全部列出（Q5） |
| `jumpPreference=both` | variant 附加 tag/payload 行 |

---

## 7. 已决议开放问题

| ID | 决议 |
|----|------|
| **Q1** | 变体优先静态工厂/`Ok` 声明；无则 Tag；`both` 时附加 tag/payload |
| **Q2** | mixin 类仅 Python；方法 → Python + 能解析时的宿主 `.inl` |
| **Q3** | protocol 仅 Python（去掉伪 C++ `class`） |
| **Q4** | 条件类型别名与普通 `using` 一样进索引 |
| **Q5** | overload 全部列出（按行号） |

迭代 A–G 已在 v3 落地；后续仅修回归与 FFI/native 边缘。

---

## 8. 验收与回归

### 8.1 最小命令

```bat
python -m unittest src.tests.test_nav_index -v
python main.py py2cpp\util\list.py -o generated --no-main
python main.py py2cpp\alg\agg_mode.py -o generated --no-main
python main.py py2cpp\core\result.py -o generated --no-main
python main.py py2cpp\ui\events.py -o generated --no-main
REM 全量索引
python main.py py2cpp\__init__.py -o generated --no-main
```

扩展：Reload Window；下列位点 F12 抽检。

### 8.2 抽检表

| 位点 | 期望 |
|------|------|
| `class list` | `list.h` 类定义（非前向声明） |
| `def reverse` / `_timComputeMinrun` | `list.inl` **定义**行 |
| `capacity` getter/setter | `capacity__get` / `capacity__set` |
| `Matrix3.zero` / `Vector2.zero` | `zero__get` |
| `type Item` / 自动 `Element` | `using …` |
| `AggModeEnum.Min` | `AggModeEnum::Min` |
| `Result.Ok` / `new.Ok` | 工厂 `static … Ok(` |
| `ui/events.py` → `UIEventDelegate` | `class UIEventDelegate` |
| `@protocol` 类名 | 仅 Python 定义行 |

### 8.3 PR 检查单

```text
[x] 开放问题 Q1–Q5 已决议并写入本文
[ ] 只改源树（nav_index / 扩展 / tests / docs），未手改 generated/ 充数
[ ] test_nav_index 全绿；触达模块已重译验证 shard
[ ] docs/py2cpp-nav.md 与 plugins/py2cpp-nav/README.md 已同步
[ ] NAV_INDEX_VERSION = 3
```

---

## 9. 关键路径速查

| 用途 | 路径 |
|------|------|
| 本方案 | `docs/py2cpp-nav.md` |
| 插件说明 | `plugins/py2cpp-nav/README.md` |
| 索引生成 | `src/codegen/nav_index.py` |
| 挂钩 | `src/translator.py` → `write_nav_index` |
| 扩展实现 | `plugins/py2cpp-nav/out/` |
| 打包 | `pkg-nav.bat` |
| 缓存 | `generated/.cache/nav/` |
| 重构方案（Rename/Refs） | `docs/py2cpp-architect.md` |

---

## 10. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-07-20 | 初稿：架构、格式、覆盖矩阵、缺陷、迭代 A–G、开放问题 |
| 2026-07-20 | v3：落地 A–G；决议 Q1–Q5；kind 扩展；扩展限定名/setter 优先 |
| 2026-08-26 | 交叉引用 py2cpp-architect（Rename/Refs/大规模重构归属） |
