"""源文件方言判定（生产仅 Paw/Mid）。"""
from __future__ import annotations

from enum import Enum
from pathlib import Path


class Dialect(Enum):
  PAW = "paw"  # *.paw；*.py / *.pyi 亦走 Paw 前端（拒 CPython ast.parse）


_PAW_SUFFIXES = {".paw"}
# 仍可能出现的兼容后缀：一律按 Paw 解析；语法不接受则报错，不回退 ast.parse
_COMPAT_SUFFIXES = {".py", ".pyi"}


def dialect_from_path(path: str | Path) -> Dialect:
  """生产入口一律 ``Dialect.PAW``（无 LEGACY / ``ast.parse`` 分支）。"""
  suf = Path(path).suffix.lower()
  if suf in _PAW_SUFFIXES or suf in _COMPAT_SUFFIXES or not suf:
    return Dialect.PAW
  raise ValueError(
    f"不支持的源后缀 {suf!r}（{path}）；生产仅接受 .paw"
    f"（兼容尝试 .py/.pyi 须能被 Paw 语法接受）"
  )


def is_source_suffix(path: str | Path) -> bool:
  return Path(path).suffix.lower() in _PAW_SUFFIXES | _COMPAT_SUFFIXES


def is_production_suffix(path: str | Path) -> bool:
  """生产推荐后缀（``.paw``）；``.py``/``.pyi`` 非推荐入口。"""
  return Path(path).suffix.lower() in _PAW_SUFFIXES
