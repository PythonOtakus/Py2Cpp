# MidIR schema（paw-mid-0.1.0）

发射器目标 IR。字段见 `compiler/py/mid/nodes.py`。

| 节点 | 字段摘要 |
|---|---|
| `MidModule` | `path`, `items`, `diagnostics` |
| `MidEnum` | `decl_id`, `name`, `is_type_enum`, `flag`, `members`, `base_source?` |
| `MidClass` | 修饰位 + `const_fields` + `opaque_members` |
| `MidFunction` | 装饰器/参数/返回/体源片段（N3 改为结构化 Stmt） |
| `MidImport` / `MidOpaque` | 源片段 |

生产路径：`ast_module_from_mid` 直构 `ast.Module`（已删 span `materialize_ast`）。结构化门闩见 `structure.py`。
N4 目标：删除物化，`src/emit` 直接读 MidIR。
