# P3 / 原生管道验证快照

更新 2026-10-31。

| 项 | 状态 |
|---|---|
| `parse_module` 无 `paw_source_to_ast` | 通过（`tools/paw_ast_ban_checklist.py`） |
| Syntax→HIR→MidIR | `compiler/py/sema` + `compiler/py/mid` |
| A 批 `test_paw_a_batch.paw` | 翻译 + MSVC + exe exit 0 |
| B 批 `test_paw_record.paw` | 翻译 + MSVC + exe exit 0 |
| stdlib bootstrap | `python main.py lib/paw/__init__.paw -o out --no-main` |
| C0 tree | `MidEnum` + `MidClass` MidIR 直构（含 PEP695 / `friends=`）；失败回退 rewrite |
| 类内方法结构化 | `FunctionDecl` → `MidClass.methods`；`static`/`native` 进物化 |
| Passes 直读 MidIR | `expand_enums_from_mid` + `apply_mid_*_flags`（dataclass 前）；见 `compiler/py/sema/pass_bridge.md` |
| C0 seed 冒烟 | `python tools/paw_c0_seed_smoke.py`；`test_paw_seed_span` / `lexer` / `parser` / `class` / `import_def` |
| MidIR rewrite 探测 | `python tools/paw_mid_rewrite_probe.py`（A/B+seed 全 structured） |
| seed 包 import | `from compiler.paw.frontend.lexer import Lexer` 等可被测试解析 |
| P0 类型表面 | `src/tests/test_paw_type_parse.py`；去桥路线 [debridge-roadmap.md](./debridge-roadmap.md) |
