"""Paw 工程根与 monorepo 根路径。

布局：``<mono>/paw/``（译器 / 标准库）与 ``<mono>/zeus/``（引擎）并列。
``_REPO_ROOT`` / ``PAW_ROOT`` 指向 ``paw/``；跨树引用 Zeus 用 ``MONOREPO_ROOT``。
"""
from __future__ import annotations

from pathlib import Path

PAW_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = PAW_ROOT  # 兼容旧名：译器工程根（原仓库根）


def _monorepo_root(paw: Path = PAW_ROOT) -> Path:
  parent = paw.parent
  if paw.name == "paw" and (parent / "zeus").is_dir():
    return parent
  return paw


MONOREPO_ROOT = _monorepo_root()
PY2CPP_ROOT = _REPO_ROOT / "py2cpp"
