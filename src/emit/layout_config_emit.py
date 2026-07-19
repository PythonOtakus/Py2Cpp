"""``generated/runtime`` 布局常量（``translator`` / ``emit.layout_emit`` 共用）。"""
from __future__ import annotations

from ..constant.stdlib_discovery import (
  stdlib_module_paths_for_rel_paths,
)
from ..constant.stdlib_modules import (
  HEADER_INL_BEFORE_NS_CLOSE_PKG,
  HEADER_SKIP_OPERATORS_BEFORE_INL_REL,
  HEADER_TAIL_SKIP_UMBRELLA_REL,
  INL_EXTRA_OPERATORS_INL_REL,
  INL_EXTRA_STDINCLUDES_REL,
  INL_SKIP_OPERATORS_H_REL,
  INL_SKIP_UMBRELLA_REL,
  IO_FILE_PATH_MODULE_REL,
  IO_PATH_MODULE_REL,
  JSON_API_EXTRA_HEADER_INCLUDE_RELS,
  JSON_API_MODULE_REL,
  MODULE_INL_PY_STR_TO_CBUF_REL,
  PROTOCOL_TRAITS_MODULE_REL,
  PROTOCOL_TRAITS_SOURCE_MODULES,
  SYSTEM_DATETIME_MODULE_REL,
)
from ..constant.stdlib_methods import JSON_API_METHODS_NEED_TYPE_ARG
from ..constant.stdlib_layout import CORE_PKG, RUNTIME_PKG, RUNTIME_BUILTINS_MODULE, stdlib_header_include, stdlib_module_path

RUNTIME_PREFIX = RUNTIME_PKG
RUNTIME_CPP = "py2cpp.cpp"
GENERATED_DIR = "generated"
RUNTIME_OUTPUT_SUBDIR = "runtime"

# 与 ``py2cpp/slice.py`` 中 ``SLICE_*_UNSET`` 一致
SLICE_START_UNSET = -2000000001
SLICE_STOP_UNSET = -2000000002

_OS_PATH_MODULE = stdlib_module_path(IO_FILE_PATH_MODULE_REL)
_IO_PATH_OO_MODULE = stdlib_module_path(IO_PATH_MODULE_REL)
_DATETIME_MODULE = stdlib_module_path(SYSTEM_DATETIME_MODULE_REL)
_PROTOCOL_TRAITS_MODULE = stdlib_module_path(PROTOCOL_TRAITS_MODULE_REL)
_MODULE_INL_PY_STR_TO_CBUF = stdlib_module_path(MODULE_INL_PY_STR_TO_CBUF_REL)

_JSON_API_MODULE = stdlib_module_path(JSON_API_MODULE_REL)
_JSON_API_METHODS_NEED_TYPE_ARG = JSON_API_METHODS_NEED_TYPE_ARG
_JSON_API_EXTRA_HEADER_INCLUDES = tuple(
  stdlib_header_include(rel) for rel in JSON_API_EXTRA_HEADER_INCLUDE_RELS
)

UMBRELLA_HEADER = f"{RUNTIME_PREFIX}/minimal.h"
PROTOCOL_TRAITS_HEADER = f"{CORE_PKG}/protocol_traits.h"
PROTOCOL_TRAITS_GUARD = "PY2CPP_PROTOCOL_TRAITS_H"
PROTOCOL_TRAITS_SOURCE_MODULE_PATHS: frozenset[str] = frozenset(
  stdlib_module_path(rel) for rel in PROTOCOL_TRAITS_SOURCE_MODULES
)

_HEADER_SKIP_OPERATORS_BEFORE_INL = stdlib_module_paths_for_rel_paths(
  HEADER_SKIP_OPERATORS_BEFORE_INL_REL,
)
_HEADER_INL_BEFORE_NS_CLOSE: frozenset[str] = frozenset({
  RUNTIME_PKG,
})
_HEADER_SKIP_INL_IN_MODULE_H: frozenset[str] = frozenset({
  stdlib_module_path("core/exceptions"),
  stdlib_module_path("core/iter_result"),
})

_HEADER_TAIL_SKIP_UMBRELLA = stdlib_module_paths_for_rel_paths(HEADER_TAIL_SKIP_UMBRELLA_REL)
_INL_SKIP_UMBRELLA = stdlib_module_paths_for_rel_paths(INL_SKIP_UMBRELLA_REL)
_INL_SKIP_OPERATORS_H = stdlib_module_paths_for_rel_paths(INL_SKIP_OPERATORS_H_REL)
_INL_EXTRA_OPERATORS_INL = stdlib_module_paths_for_rel_paths(INL_EXTRA_OPERATORS_INL_REL)
_INL_EXTRA_STDINCLUDES: dict[str, tuple[str, ...]] = {
  stdlib_module_path(rel): tuple(stdlib_header_include(inc) for inc in includes)
  for rel, includes in INL_EXTRA_STDINCLUDES_REL.items()
}


def module_inl_extra_include_lines(module_path: str) -> list[str]:
  """表驱动 ``.inl`` 额外 ``#include``（不含万能头 / ``operators.*`` 通用规则）。"""
  if module_path == _MODULE_INL_PY_STR_TO_CBUF:
    return [
      f'#include "{PROTOCOL_TRAITS_HEADER}"',
      f'#include "{stdlib_header_include("util/dict")}"',
      f'#include "{stdlib_header_include("util/memory")}"',
      f'#include "{RUNTIME_PREFIX}/operators.h"',
      "#include <stdio.h>",
      "#include <string.h>",
    ]
  return [f'#include "{inc}"' for inc in _INL_EXTRA_STDINCLUDES.get(module_path, ())]
