"""Paw 工程根与 monorepo 根路径。

布局：``<mono>/paw/``（语言产品）与 ``<mono>/zeus/``（引擎）并列。
``PAW_ROOT`` 指向产品根；标准库源在 ``lib/paw/``（导入名仍为 ``paw``）。
"""
from __future__ import annotations

from pathlib import Path

PAW_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = PAW_ROOT  # 兼容旧名：译器工程根


def _monorepo_root(paw: Path = PAW_ROOT) -> Path:
  parent = paw.parent
  if paw.name == "paw" and (parent / "zeus").is_dir():
    return parent
  return paw


MONOREPO_ROOT = _monorepo_root()
# 标准库包根：``lib/paw/``（``from paw import *``）
STDLIB_ROOT = _REPO_ROOT / "lib" / "paw"
PY2CPP_ROOT = STDLIB_ROOT  # 兼容旧名
