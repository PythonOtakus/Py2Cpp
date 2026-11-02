# 内核迁移清单（原生编译器 / 原 P4）

目标：生产路径 **不依赖** CPython AST 与 Paw→legacy 文本改写；`src/` 能力迁入可自举的 `compiler/`。

| 模块族 | 现状 | 迁入条件 |
|---|---|---|
| `compiler/py/frontend/*` | Lexer/Parser（声明+import/def）；`surface_rewrite` 仅离线 | 保持 bootstrap profile；生产不调用 rewrite |
| `compiler/py/hir/*` / `compiler/py/sema/*` | Syntax→HIR 绑定 | 补齐 RecordPlan / CachePlan |
| `compiler/py/mid/*` | MidIR + `ast_from_mid` / `emit_cpp`（P5 已删 span materialize） | passes 直读 MidIR |
| `src/frontend/*` | 薄驱动；PAW 走 MidIR | 最终变薄或删除 |
| `src/analysis/type_node.py` 等 | 仍绑 CPython AST | 先去 Enum/dataclass 运行时依赖 |
| `src/passes/*` | 消费 `ast.*` | 改为消费 HIR / MidIR |
| `src/codegen/expand_py2cpp_template.py` | 宿主 exec | 收敛模板子集 + 原生求值器 |
| `src/translator.py` | 总控；仍读 `parsed.tree` | 改为读 MidIR；保留为 C0 参考 |

验收：

1. `python scripts/paw_ast_ban_checklist.py` → api 无 rewrite
2. `python scripts/paw_bootstrap_stages.py` 在 C1 写入 `compiler/stages/stage1/` 后，`compare stage2 stage3` 对真实 manifest 通过
