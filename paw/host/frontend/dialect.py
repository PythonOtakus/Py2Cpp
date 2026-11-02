"""源文件方言判定。"""
from __future__ import annotations

from enum import Enum
from pathlib import Path


class Dialect(Enum):
  LEGACY = "legacy"  # *.py / *.pyi
  PAW = "paw"  # *.paw


_PAW_SUFFIXES = {".paw"}
_LEGACY_SUFFIXES = {".py", ".pyi"}


def dialect_from_path(path: str | Path) -> Dialect:
  suf = Path(path).suffix.lower()
  if suf in _PAW_SUFFIXES:
    return Dialect.PAW
  if suf in _LEGACY_SUFFIXES:
    return Dialect.LEGACY
  # 无后缀或未知：按 legacy 文本尝试（兼容历史调用）
  return Dialect.LEGACY


def is_source_suffix(path: str | Path) -> bool:
  return Path(path).suffix.lower() in _PAW_SUFFIXES | _LEGACY_SUFFIXES
