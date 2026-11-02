# compiler/ — Paw 可自举前端与内核

规划见 [docs/parser-self-hosting.md](../docs/parser-self-hosting.md)、[docs/paw/dual-impl.md](../docs/paw/dual-impl.md)（**Py×Paw 双实现对照**）。

| 路径 | 职责 |
|---|---|
| `py/` | **Py 参考轨**（`*.py` / `__init__.py`） |
| `paw/` | **Paw 自举轨**：与 `py/` **路径 1:1**（`*.paw` / `__init__.paw`） |
| `dual/` | 对照脚手架（`paw_dual_compare` 校验 tree_parity） |
| `stages/` | 自编译产物 stage1/2/3、c1_emit、driver |
| `bootstrap_profile.md` | 实现语言冻结子集 |

**禁止**：生产路径调用 `py/frontend/surface_rewrite.py`（仅离线迁移/对照）。

```bat
python scripts/paw_dual_compare.py
scripts\paw_stage1_c1_link.bat
```

宿主入口：`src/frontend` 调用 `compiler.py.*`。完整无 Python 构建见 N6。
