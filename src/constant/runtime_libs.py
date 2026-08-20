"""标准库链接模型：``header_only`` vs ``library``（见 ``docs/runtime-libs.md``）。

默认：白名单非模板模块进胖库 ``py2cpp_runtime.lib``；其余（含全部模板模块）header-only。
``PY2CPP_HEADER_ONLY=1`` 恢复纯头文件模型（回滚）。

P1 白名单宜小、可验证；扩容见文档 P2。
"""
from __future__ import annotations

import os
from typing import Literal

from .stdlib_discovery import STDLIB_REL_PATH_SET
from .stdlib_layout import RUNTIME_PKG, stdlib_module_path

LinkKind = Literal["header_only", "library"]

# P1：显式白名单（无模板、实现量大、依赖图简单）。扩容前须单独编过库 TU。
_LIBRARY_REL_PATHS: frozenset[str] = frozenset({
  "system/time",
  "system/datetime",
  "system/environ",
  "util/memory",
  "util/range",
  "util/arena",
  "util/types",
  "io",
  "io/path",
  "sql/sqlite",
})

FAT_LIB_NAME = "py2cpp_runtime.lib"
FAT_LIB_SUBDIR = "lib"
LIBRARY_TU_MACRO = "PY2CPP_LIBRARY_TU"


def header_only_mode() -> bool:
  """纯 header-only（不生成库 TU / 不链胖库）。

  - ``PY2CPP_HEADER_ONLY=1``：强制回滚 header-only
  - 默认开启 P1 胖库（见 ``docs/runtime-libs.md``）
  """
  v = os.environ.get("PY2CPP_HEADER_ONLY", "").strip().lower()
  return v in ("1", "true", "yes", "on")


def _rel_from_module_path(module_path: str) -> str:
  norm = module_path.replace("\\", "/").strip("/")
  prefix = f"{RUNTIME_PKG}/"
  if norm.startswith(prefix):
    return norm[len(prefix) :]
  return norm


def module_link_kind(module_path: str) -> LinkKind:
  """标准库模块链接类别；非 ``py2cpp/…`` 路径视为 ``header_only``。"""
  if header_only_mode():
    return "header_only"
  rel = _rel_from_module_path(module_path)
  if rel in _LIBRARY_REL_PATHS and rel in STDLIB_REL_PATH_SET:
    return "library"
  return "header_only"


def is_library_module(module_path: str) -> bool:
  return module_link_kind(module_path) == "library"


def library_module_paths() -> tuple[str, ...]:
  """``py2cpp/<rel>`` 形式的 library 模块路径（稳定排序）。"""
  out = [
    stdlib_module_path(rel)
    for rel in sorted(_LIBRARY_REL_PATHS)
    if rel in STDLIB_REL_PATH_SET and module_link_kind(stdlib_module_path(rel)) == "library"
  ]
  return tuple(out)


def wrap_inl_include_for_header(inl_include_line: str) -> list[str]:
  """header-only：``#include ".inl"`` 在库 TU 中跳过，避免 LNK2005。"""
  return [
    f"#ifndef {LIBRARY_TU_MACRO}",
    inl_include_line,
    "#endif",
  ]
