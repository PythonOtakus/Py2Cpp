"""万能头 ``minimal.h`` include 顺序与 bulk 跳过集。"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from .stdlib_discovery import STDLIB_REL_PATH_SET
from .stdlib_modules import UMBRELLA_IO_LATE_IF_PRESENT, UMBRELLA_MSVC_COMPAT_BEFORE_MODULE
from .stdlib_discovery import STDLIB_REL_PATH_SET
from .stdlib_layout import CORE_PKG, RUNTIME_PKG, stdlib_header_include
from .runtime_libs import header_only_mode

UmbrellaSpecKind = Literal["primitive", "module", "special"]
UmbrellaEarlyKind = Literal[
  "always",
  "if_member",
  "if_all_members",
  "if_any_protocols",
]

UMBRELLA_PREFIX_SPECS: tuple[tuple[UmbrellaSpecKind, str], ...] = (
  ("primitive", "char.h"),
  ("primitive", "byte.h"),
  ("primitive", "c_str.h"),
  ("primitive", "py_types.h"),
  ("primitive", "member_access.h"),
  ("module", "builtins"),
  ("module", "core/exceptions"),
)

UMBRELLA_EARLY_SPECS: tuple[tuple[UmbrellaEarlyKind, str | tuple[str, ...]], ...] = (
  ("always", "core/iter_result"),
  ("if_member", "text/str"),
  ("always", "core/generator"),
  ("always", "core/coroutine"),
  ("always", "core/async_generator"),
  ("always", "core/optional"),
  ("always", "core/none"),
  ("always", "core/result"),
  ("if_any_protocols", "protocol_traits"),
  ("if_member", "util/slice"),
  ("if_all_members", ("system/datetime", "system/time")),
  ("if_member", "test/unittest"),
)

UMBRELLA_SUFFIX_PRIMITIVE_SPECS: tuple[str, ...] = (
  "operators.h",
  "operators.inl",
)


def _umbrella_modules_from_specs() -> frozenset[str]:
  mods: set[str] = set()
  for kind, name in UMBRELLA_PREFIX_SPECS:
    if kind == "module" and name != "py2cpp":
      mods.add(name)
  for kind, payload in UMBRELLA_EARLY_SPECS:
    if kind == "always":
      mods.add(str(payload))
    elif kind == "if_member":
      mods.add(str(payload))
    elif kind == "if_all_members":
      assert isinstance(payload, tuple)
      mods.update(payload)
    elif kind == "if_any_protocols":
      mods.add("core/protocols")
  mods.update(UMBRELLA_IO_LATE_IF_PRESENT)
  mods.add("io")
  return frozenset(mods)


UMBRELLA_BULK_SKIP: frozenset[str] = _umbrella_modules_from_specs()


def _umbrella_early_matches(
  kind: UmbrellaEarlyKind,
  payload: str | tuple[str, ...],
  stdlib_set: set[str],
) -> bool:
  if kind == "always":
    return True
  if kind == "if_member":
    return str(payload) in stdlib_set
  if kind == "if_all_members":
    assert isinstance(payload, tuple)
    return all(m in stdlib_set for m in payload)
  if kind == "if_any_protocols":
    return "core/protocols" in stdlib_set or any("protocols" in n for n in stdlib_set)
  return False


def expand_umbrella_include_paths(
  runtime_prefix: str,
  stdlib_modules: Sequence[str],
) -> list[str]:
  """万能头 ``#include "…"`` 路径（不含引号与指令），顺序与 ``build_py2cpp_umbrella_header`` 一致。"""
  stdlib_set = set(stdlib_modules)
  paths: list[str] = []

  for kind, name in UMBRELLA_PREFIX_SPECS:
    if kind == "primitive":
      paths.append(f"{runtime_prefix}/{name}")
    elif kind == "module":
      paths.append(stdlib_header_include(name))

  for kind, payload in UMBRELLA_EARLY_SPECS:
    if not _umbrella_early_matches(kind, payload, stdlib_set):
      continue
    if kind == "if_any_protocols":
      paths.append(f"{runtime_prefix}/operators.h")
      paths.append(f"{CORE_PKG}/protocol_traits.h")
      # ``protocol_erase`` 使用裸 ``PyNone``；库 TU 跳过中段 inl 后须显式 using。
      paths.append("__py2cpp_using_pynone__")
      paths.append(f"{CORE_PKG}/protocol_erase.h")
      paths.append(stdlib_header_include("core/protocols"))
    elif kind == "if_all_members":
      assert isinstance(payload, tuple)
      payload_set = frozenset(payload)
      if payload_set >= frozenset({"system/datetime", "system/time"}):
        paths.append(stdlib_header_include("system/time"))
        paths.append(stdlib_header_include("system/datetime"))
      else:
        for mod in payload:
          paths.append(stdlib_header_include(mod))
    else:
      paths.append(stdlib_header_include(str(payload)))
    # ``ExcType`` / ``PyIterResult`` 的 ``str`` 实现须在 ``PyStr`` 完整定义之后
    # 库 TU（``PY2CPP_LIBRARY_TU``）跳过，避免与胖库 / 测例重复定义
    if payload == "text/str" and "core/exceptions" in stdlib_set:
      if header_only_mode():
        paths.append(f"{runtime_prefix}/core/exceptions.inl")
      else:
        paths.append(f"__py2cpp_guard_inl__:{runtime_prefix}/core/exceptions.inl")
    if payload == "text/str" and "core/iter_result" in stdlib_set:
      if header_only_mode():
        paths.append(f"{runtime_prefix}/core/iter_result.inl")
      else:
        paths.append(f"__py2cpp_guard_inl__:{runtime_prefix}/core/iter_result.inl")

  for name in stdlib_modules:
    if name in UMBRELLA_BULK_SKIP or name not in STDLIB_REL_PATH_SET:
      continue
    paths.append(stdlib_header_include(name))
    if (
      name == "numeric/varint"
      and _umbrella_early_matches("if_any_protocols", "protocol_traits", stdlib_set)
    ):
      paths.append(f"{CORE_PKG}/protocol_erase_domain.h")

  for mod in UMBRELLA_IO_LATE_IF_PRESENT:
    if mod in stdlib_set:
      paths.append(stdlib_header_include(mod))

  # 包根 ``py2cpp/__init__.py`` 再导出须在各子模块声明之后
  paths.append(stdlib_header_include(RUNTIME_PKG))

  for name in UMBRELLA_SUFFIX_PRIMITIVE_SPECS:
    paths.append(f"{runtime_prefix}/{name}")

  return paths
