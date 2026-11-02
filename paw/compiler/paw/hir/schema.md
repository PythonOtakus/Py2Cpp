# Paw HIR schema（paw-hir-0.1.0）

HIR 表达「源码意味着什么」：绑定后的声明、符号与计划对象。由 `compiler/py/sema` 从 `SyntaxModule` 生成。

## 标识

| 类型 | 含义 |
|---|---|
| `NodeId` | 一次编译内稳定整数；不可作跨版本缓存键 |
| `SymbolId` | 绑定后的名称 |
| `DeclId` | 声明身份（类/函数/枚举/字段） |
| `TypeId` | 绑定后类型（对接 TypeNode / MidIR） |

## 模块

| 节点 | 字段 |
|---|---|
| `HirModule` | `path`, `decls: list[HirDecl]`, `span` |
| `HirEnum` | `decl_id`, `name`, `is_type_enum`, `flag`, `members`, `span`, `base_source?` |
| `HirClass` | `decl_id`, `name`, `object_model`, `modifiers`（final/record/frozen/ordered/lazy/protocol/mixin/union/variant）, `fields`, `methods`, `span` |
| `HirFunction` | `decl_id`, `name`, `params_source`, `return_source?`, `body_source`, `decorators`, `is_async`, `span` |
| `HirImport` | `source`, `span` |
| `HirOpaque` | `source`, `span`（尚未语义化；物化阶段按片段处理） |

## 计划对象（绑定后）

| 计划 | 用途 |
|---|---|
| `RecordPlan` | record 字段顺序、构造、比较、序列化 |
| `CachePlan` | 声明缓存 |
| `SingletonPlan` | lazy class 单例 |

首期竖切可只填充 `HirEnum` / `HirClass` 修饰信息；完整计划随 N2/N3 补齐。

## 与 MidIR / ClassInfo 对照

| HIR | MidIR（`compiler/py/mid`） | 旧 ClassInfo（演进中） |
|---|---|---|
| `HirClass.decl_id` | `MidClass.decl_id` | （目标）不再用 `ast.ClassDef` 作身份 |
| `HirClass.object_model` | `MidClass.object_model` | `is_refcount` 等 |
| `HirClass.modifiers.final` | `MidClass.is_final` | `@final` 元数据 |
| `HirEnum` | `MidEnum` | `@enum` / `@enum.mro` |
| `HirFunction` | `MidFunction` | `module_functions` 项 |
| `HirOpaque` | `MidOpaque` | 片段 `ast.parse`（过渡） |

生产路径目标：emit 只读 MidIR；删除对 `ast.ClassDef` 的长期依赖（N3–N4）。
