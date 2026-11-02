"""Parity with ``compiler/paw/passes/check.paw`` (name-uniqueness proto-bind)."""

from __future__ import annotations

from typing import Any


def checkModule(mod: Any) -> list[str]:
  out: list[str] = []
  seen_fn: list[str] = []
  for fn in getattr(mod, "functions", []) or []:
    name = getattr(fn, "name", "") or ""
    if not name:
      continue
    if name in seen_fn:
      out.append("duplicate function " + name)
    else:
      seen_fn.append(name)
  seen_en: list[str] = []
  for en in getattr(mod, "enums", []) or []:
    name = getattr(en, "name", "") or ""
    if not name:
      continue
    if name in seen_en:
      out.append("duplicate enum " + name)
    else:
      seen_en.append(name)
  seen_cl: list[str] = []
  for cls in getattr(mod, "classes", []) or []:
    name = getattr(cls, "name", "") or ""
    if not name:
      continue
    if name in seen_cl:
      out.append("duplicate class " + name)
    else:
      seen_cl.append(name)
  return out


def checkOk(mod: Any) -> bool:
  return len(checkModule(mod)) == 0
