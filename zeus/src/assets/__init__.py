"""Zeus 资产约定：场景等用 ``.zas``，模型用 ``.fbx``。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.io.path import Path


ZAS_SUFFIX: str = ".zas"
FBX_SUFFIX: str = ".fbx"
ZAS_VERSION: int = 1


def ensure_suffix(path: str, suffix: str) -> str:
  """无后缀时补上；已有后缀则原样返回。"""
  p: Path = new(path)
  if p.suffix == suffix:
    return path
  if not p.suffix:
    out: str = path
    out += suffix
    return out
  return path


def has_suffix(path: str, suffix: str) -> bool:
  p: Path = new(path)
  return p.suffix == suffix


def is_zas(path: str) -> bool:
  return has_suffix(path, ZAS_SUFFIX)


def is_fbx(path: str) -> bool:
  return has_suffix(path, FBX_SUFFIX)
