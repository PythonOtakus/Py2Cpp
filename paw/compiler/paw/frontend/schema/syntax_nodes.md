# Paw Syntax AST schema（paw-frontend-0.2.0）

节点只描述「源码写了什么」。HIR / MidIR / TypeNode 另层。实现见 `compiler/py/frontend/syntax_nodes.py`。

生产路径：**禁止** `rewrite_paw_to_legacy` / `ast.parse` 整文件；`.paw` → Lexer → Parser → `SyntaxModule` → Binder → HIR → MidIR。

## 公共

| 节点 | 字段 |
|---|---|
| `Span` | `file_id`, `start`, `end`（半开字节） |
| `SyntaxModule` | `items: list[ModuleItem]`, `span`, `unsupported` |
| `Diagnostic` | `code`, `span`, `message` |

## 声明

| 节点 | 字段 |
|---|---|
| `EnumDecl` | `name`, `is_type_enum`, `base_source?`, `flag`, `members`, `span` |
| `EnumMember` | `name`, `value_source?`, `span` |
| `ClassDecl` | `name`, `bases_source?`, `object_model`, `is_final`, `is_record`, `is_frozen`, `is_ordered`, `is_lazy`, `is_protocol`, `is_mixin`, `is_union`, `is_variant`, `members`, `span`, `header_source` |
| `ConstField` | `name`, `type_syntax?`, `value_source`, `span` |
| `FunctionDecl` | `name`, `decorators_source`, `params_source`, `params`, `return_source?`, `return_type?`, `body_source`, `body`, `is_async`, flags, `span` |
| `ParamDecl` | `name`, `type_syntax?`, `default_source?`, `span`, `is_vararg`, `is_kwarg`, `kind` |
| `FieldDecl` | `name`, `type_syntax?`, `value_source`, `span`（类体实例字段） |
| `IfExp` / `MatchStmt` / `ListExpr` / `SliceExpr` / `AugAssignStmt` | 见 `syntax_nodes.py`；P2+ 已落地 |
| `ImportStmt` | `source`, `span` |
| `OpaqueMember` | `source`, `span`（类体内尚未细分的成员行） |
| `OpaqueStmt` | `source`, `span`（模块级尚未细分的语句；不得含 Paw 声明头） |

## 类型表面

| 节点 | 字段 |
|---|---|
| `NameTypeSyntax` | `name`, `span` |
| `GenericApplyTypeSyntax` | `head`, `arguments`, `span`（类型应用；≠ 值下标） |
| `ReferenceTypeSyntax` | `inner`, `span`（`ref T`） |
| `LazyTypeSyntax` | `inner`, `span`（`lazy T` / `lazy ref T`） |
| `NullableTypeSyntax` | `inner`, `span`（`T?`） |
| `TupleTypeSyntax` | `items`, `trailing_comma`, `span` |
| `ParenthesizedTypeSyntax` | `inner`, `span` |
| `CallableTypeSyntax` | `parameter_types`, `return_type`, `span` |
| `TypeAttrSyntax` | `name`, `args_source?`, `span` |
| `AttributedTypeSyntax` | `inner`, `attributes`, `span`（`T @Meta`；≠ 表达式 `a @ b`） |

## 表达式 / 语句（N1+ 增量）

| 节点 | 字段 | 状态 |
|---|---|---|
| `NameExpr` | `name`, `span` | 规划 |
| `LiteralExpr` | `kind`, `text`, `span` | 规划 |
| `BinaryExpr` / `UnaryExpr` / `CallExpr` | 运算数与算子 | 规划 |
| `AssignStmt` / `AnnAssignStmt` / `ReturnStmt` / `IfStmt` / `ForStmt` / `MatchStmt` | 标准语句形 | 规划 |
| `MatchExpr` | `subject`, `arms`, `span` | 规划（P3） |

未建模构造记入 `OpaqueStmt`/`OpaqueMember` 并可选列入 `unsupported`；**禁止** silently 回退全文 rewrite。

Schema 变更须 bump `SCHEMA_VERSION`（`compiler/py/frontend/__init__.py`）并更新 [docs/paw/baseline.md](../../../docs/paw/baseline.md)。
