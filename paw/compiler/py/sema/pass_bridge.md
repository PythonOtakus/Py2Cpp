# Passes 迁移桥接说明（N3）

## 原则

1. 新 pass 只接受 `HirModule` / `MidModule`。
2. 旧 `src/passes/*` 在 N3 期间仍读 `ast.*`，输入来自 `ast_module_from_mid`（**已删** span `materialize_ast`）。
3. 迁移顺序（与现有 translator 一致）：enum → union → dataclass/record → descriptor → decorator → generators → analyze。
4. `TypeNode`：去掉 Python `Enum`/`dataclass` 运行时依赖后再减少字符串反解析。

## 已接通

| 项 | 状态 |
|---|---|
| 类内 `static`/`native`/`def` → `FunctionDecl` → `MidClass.methods` | 是 |
| `MidEnum` / `MidClass` → `ast_from_mid` | 是（含 PEP695 / `friends=`） |
| `type_params_source` / 类头 keywords | 是 |
| `expand_enums_from_mid` | 是（简单/flag 枚举；带 enum 基类仍走 AST） |
| `apply_mid_class_flags` | 是（union/protocol/mixin/final/native/refcount/record；在 expand_dataclass 之前） |
| Mid record → `expand_dataclass` | 是（`is_record_from_mid` 可无 `@dataclass` 装饰器） |
| 生产树直构 | **P5**：一律 `ast_module_from_mid`；门闩 `structure.module_fully_structured` |
| C0 seed | `span_tokens`…`lexer` + `syntax_nodes` + `parser`；PRIMARY + 空树 |
| seed 绝对 import | `from compiler.paw.…`（stdlib 未命中后回退仓库顶层包） |
| 结构化探测 | `tools/paw_mid_rewrite_probe.py`（A/B + seed 须 `structured=True`） |

## 验收

- `python main.py lib/paw/__init__.paw -o out --no-main` 不经过全文 `surface_rewrite`
- A/B：`test_paw_a_batch` / `test_paw_record` 类体 MidIR 直构（`_class_needs_rewrite==False`）
- `python tools/paw_c0_seed_smoke.py`；`python tools/paw_mid_rewrite_probe.py`
- `build.bat lang\test_paw_seed_span lang\test_paw_seed_lexer --seq`
- `python tools/paw_ast_ban_checklist.py` 中 hot-path `ast.parse` 债务递减
