"""``finalize_module_headers`` 表驱动实现（破环 ``str`` ↔ 容器 include）。"""
from __future__ import annotations

from ..constant.header_fixups_data import (
  HEADER_FORWARD_DECLS,
  HEADER_FORWARD_GROUPS,
  MODULE_HEADER_FIXUPS,
)
from ..constant.stdlib_discovery import stdlib_module_paths_for_rel_paths
from ..constant.stdlib_modules import (
  BYTES_POST_CLASS_MODULES,
  PKG_ROOT_FRONT_SKIP_RELS,
  PYSTR_FORWARD_ONLY_MODULES,
  SLICE_FRONT_MODULES_REL,
)
from ..constant.stdlib_layout import CORE_PKG, RUNTIME_PKG, stdlib_header_include, stdlib_module_path

_PROTOCOL_TRAITS_H = f"{CORE_PKG}/protocol_traits.h"
_UMBRELLA_H = f"{RUNTIME_PKG}/minimal.h"
_PKG_ROOT_H = stdlib_header_include(RUNTIME_PKG)
_STR_HEADER = stdlib_header_include("text/str")
_OPS_H = f"{RUNTIME_PKG}/operators.h"
_PY_TYPES_H = f"{RUNTIME_PKG}/py_types.h"
_PROT_H = stdlib_header_include("core/protocols")
_SLICE_H = stdlib_header_include("util/slice")

_HDR_KEYS: dict[str, str] = {
  "traits": _PROTOCOL_TRAITS_H,
  "umbrella": _UMBRELLA_H,
  "operators": _OPS_H,
  "py_types": _PY_TYPES_H,
  "str": _STR_HEADER,
}

_BYTES_POST_CLASS_HEADERS: tuple[str, ...] = (
  _PROTOCOL_TRAITS_H,
  *(stdlib_header_include(m) for m in BYTES_POST_CLASS_MODULES),
)

_PYSTR_FORWARD_ONLY_FULL: frozenset[str] = frozenset(
  stdlib_module_path(m) for m in PYSTR_FORWARD_ONLY_MODULES
)

_PKG_ROOT_FRONT_SKIP: frozenset[str] = frozenset({RUNTIME_PKG}) | stdlib_module_paths_for_rel_paths(
  PKG_ROOT_FRONT_SKIP_RELS,
)

_SLICE_FRONT_MODULES: frozenset[str] = stdlib_module_paths_for_rel_paths(
  SLICE_FRONT_MODULES_REL,
)


def _rel_module_path(module_path: str) -> str | None:
  if module_path == RUNTIME_PKG:
    return RUNTIME_PKG
  prefix = f"{RUNTIME_PKG}/"
  if module_path.startswith(prefix):
    return module_path[len(prefix):]
  return None


def _append_unique(dst: list[str], items: str | tuple[str, ...]) -> None:
  seq = (items,) if isinstance(items, str) else items
  for item in seq:
    if item not in dst:
      dst.append(item)


def _remove_all(lst: list[str], item: str) -> None:
  while item in lst:
    lst.remove(item)


def _resolve_forward(keys: str | tuple[str, ...]) -> tuple[str, ...]:
  seq = (keys,) if isinstance(keys, str) else keys
  return tuple(HEADER_FORWARD_DECLS[k] for k in seq)


def _apply_action(
  action: tuple,
  pre: list[str],
  forward: list[str],
  post: list[str],
) -> None:
  op = action[0]
  if op == "move_pre_to_post_mods":
    for mod in action[1:]:
      h = stdlib_header_include(mod)
      if h in pre:
        pre.remove(h)
        post.append(h)
    return
  if op == "move_pre_to_post_mod":
    h = stdlib_header_include(action[1])
    if h in pre:
      pre.remove(h)
      if h not in post:
        post.append(h)
    return
  if op == "bytes_post_class_move":
    for h in _BYTES_POST_CLASS_HEADERS:
      if h in pre:
        pre.remove(h)
      if h not in post:
        post.append(h)
    return
  if op == "remove_pre_mod":
    _remove_all(pre, stdlib_header_include(action[1]))
    return
  if op == "remove_pre_traits":
    _remove_all(pre, _PROTOCOL_TRAITS_H)
    return
  if op == "remove_post_traits":
    _remove_all(post, _PROTOCOL_TRAITS_H)
    return
  if op == "remove_pre_key":
    _remove_all(pre, _HDR_KEYS[action[1]])
    return
  if op == "remove_post_key":
    _remove_all(post, _HDR_KEYS[action[1]])
    return
  if op == "remove_both_key":
    for key in action[1:]:
      h = _HDR_KEYS[key]
      _remove_all(pre, h)
      _remove_all(post, h)
    return
  if op == "remove_pre_forward_mod":
    h = stdlib_header_include(action[1])
    if h in pre:
      pre.remove(h)
      _append_unique(forward, _resolve_forward(action[2]))
    return
  if op == "forward":
    _append_unique(forward, _resolve_forward(action[1]))
    return
  if op == "forward_multi":
    _append_unique(forward, _resolve_forward(action[1:]))
    return
  if op == "forward_group_if_post":
    if post:
      _append_unique(forward, _resolve_forward(HEADER_FORWARD_GROUPS[action[1]]))
    return
  if op == "insert_front_mod_if_missing":
    h = stdlib_header_include(action[1])
    if h not in pre:
      pre.insert(0, h)
    return
  if op == "insert_front_hdr":
    h = action[1]
    if h not in pre:
      pre.insert(0, h)
    return
  if op == "insert_front_key_if_missing":
    h = _HDR_KEYS[action[1]]
    if h not in pre:
      pre.insert(0, h)
    return
  if op == "reinsert_prot_at_1":
    if _PROT_H in pre:
      pre.remove(_PROT_H)
      pre.insert(1, _PROT_H)
    return
  if op == "insert_mod_after_mod":
    h = stdlib_header_include(action[1])
    anchor = stdlib_header_include(action[2])
    _remove_all(pre, h)
    if anchor in pre:
      pre.insert(pre.index(anchor) + 1, h)
    else:
      _append_unique(pre, h)
    return
  raise ValueError(f"unknown header fixup action: {op!r}")


def apply_header_fixups(
  module_path: str,
  includes: list[str],
) -> tuple[list[str], list[str], list[str]]:
  """打破 ``str`` ↔ 容器循环依赖，并保证 ``str.h`` 内 ``PyStr`` 先于容器 ``*.inl``。"""
  pre = list(includes)
  forward: list[str] = []
  post: list[str] = []

  rel = _rel_module_path(module_path)
  if rel is not None:
    for action in MODULE_HEADER_FIXUPS.get(rel, ()):
      _apply_action(action, pre, forward, post)

  if module_path in _PYSTR_FORWARD_ONLY_FULL:
    _remove_all(pre, _STR_HEADER)
    if module_path != stdlib_module_path("core/iter_result"):
      _append_unique(forward, _resolve_forward("pystr"))

  if module_path == RUNTIME_PKG or module_path.startswith(f"{RUNTIME_PKG}/"):
    if _PY_TYPES_H not in pre:
      pre.insert(0, _PY_TYPES_H)

  if module_path in _SLICE_FRONT_MODULES:
    if _SLICE_H not in pre and _SLICE_H not in post:
      pre.insert(0, _SLICE_H)

  if (
    module_path not in _PKG_ROOT_FRONT_SKIP
    and _PKG_ROOT_H in pre
  ):
    pre.remove(_PKG_ROOT_H)
    pre.insert(0, _PKG_ROOT_H)

  return pre, forward, post
