"""MidIR 结构化判定（供 ``can_emit_mid`` / 覆盖率；原 ``materialize_ast`` 门闩）。"""
from __future__ import annotations

from .nodes import MidClass, MidModule, MidOpaque

_PAW_OPAQUE_HEADS = (
  "enum ",
  "record ",
  "union ",
  "variant ",
  "protocol ",
  "mixin ",
  "native ",
  "static ",
  "ref ",
  "lazy ",
  "final ",
  "frozen ",
  "ordered ",
  "property ",
  "type enum",
  "type union",
)


def opaque_needs_rewrite(source: str) -> bool:
  for ln in source.splitlines():
    s = ln.lstrip()
    if not s or s.startswith("#"):
      continue
    for h in _PAW_OPAQUE_HEADS:
      if s.startswith(h):
        return True
    if s.startswith("const ") and ":" in s:
      return True
  if (
    ": ref " in source
    or ": lazy " in source
    or "-> ref " in source
    or "-> lazy " in source
    or ":ref " in source
    or ":lazy " in source
    or "->ref " in source
    or "->lazy " in source
  ):
    return True
  return False


def class_needs_rewrite(item: MidClass) -> bool:
  """仍含未结构化的 Paw 表面（嵌套声明、残缺装饰器行等）。"""
  for mem in item.opaque_members:
    s = mem.strip()
    if not s or s.startswith("#"):
      continue
    if s.startswith(
      (
        "def ",
        "async def ",
        "static ",
        "native ",
        "override ",
        "virtual ",
        "abstract ",
        "final ",
        "property ",
        "lazy ",
        "class ",
        "record ",
        "enum ",
        "protocol ",
        "mixin ",
        "union ",
        "variant ",
      )
    ):
      return True
    if opaque_needs_rewrite(s):
      return True
    if s.startswith("@") and not s.startswith("@optional"):
      if s.lstrip().startswith(
        (
          "@variant",
          "@protocol",
          "@mixin",
          "@union",
          "@dataclass",
          "@enum",
          "@frozen",
          "@refcount",
        )
      ):
        continue
      return True
  return False


def module_fully_structured(mid: MidModule) -> bool:
  """全部声明可 MidIR 直构（无 Paw 表面残留）。"""
  for item in mid.items:
    if isinstance(item, MidClass) and class_needs_rewrite(item):
      return False
    if isinstance(item, MidOpaque) and opaque_needs_rewrite(item.source):
      return False
  return True


# 兼容旧私有名
_opaque_needs_rewrite = opaque_needs_rewrite
_class_needs_rewrite = class_needs_rewrite
_module_fully_structured = module_fully_structured
