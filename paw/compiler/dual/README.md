# dual — 双实现对照脚手架

见 [docs/paw/dual-impl.md](../../docs/paw/dual-impl.md)。

| 路径 | 用途 |
|---|---|
| `pairs.json` | 重点模块对照层级（全树 1:1 由脚本校验） |
| `fixtures/` · `goldens/` | 共享输入与期望输出 |

```bat
python tools/paw_dual_compare.py
```
