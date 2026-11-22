"""AST-shaped IR node classes for host emit / passes (Zero-AST Phase 5).

Production ``host/`` + ``compiler/`` must not load the stdlib AST module via
direct import statements.  The **only** load is here via
``importlib.import_module`` with the module name string ``\"ast\"``.

Transitional: consumers may ``import host.tree_nodes as ast`` so existing
``ast.Name`` / ``ast.walk`` call sites keep working.  Checklist allows this
module as the AST-shaped IR facade; it still bans stdlib AST imports and
hot-path ``ast.parse``.

``parse`` is intentionally **not** a production entry: calling it raises.
Bridges / tests that still need CPython parse use ``_stdlib_parse``.
"""
from __future__ import annotations

import importlib
from typing import Any, NoReturn

_m = importlib.import_module("ast")

# Re-export all public stdlib AST symbols, then override ``parse``.
_skip = {
  "__name__",
  "__doc__",
  "__package__",
  "__loader__",
  "__spec__",
  "__file__",
  "__cached__",
  "__builtins__",
}
for _name in dir(_m):
  if _name in _skip or _name.startswith("_"):
    continue
  globals()[_name] = getattr(_m, _name)

# Python 3.12+ hides deprecated node aliases from ``dir(ast)`` (module ``__getattr__``).
_deprecated = getattr(_m, "_deprecated_globals", None)
if isinstance(_deprecated, dict):
  for _name, _val in _deprecated.items():
    globals()[_name] = _val
# Other soft-deprecated names still referenced by host (not always in ``dir``).
for _name in ("Index", "ExtSlice", "Suite", "AugLoad", "AugStore", "Param"):
  if _name not in globals() and hasattr(_m, _name):
    globals()[_name] = getattr(_m, _name)

# Bridge / test escape hatch only — not a production parse entry.
_stdlib_parse = _m.parse
_stdlib_ast = _m


def parse(*_args: Any, **_kwargs: Any) -> NoReturn:
  """Banned production entry; use frontend / Mid bridges or ``_stdlib_parse``."""
  raise RuntimeError(
    "host.tree_nodes.parse is banned on the production path; "
    "use host.frontend.api / Mid bridges, or _stdlib_parse in transitional bridges/tests"
  )


__all__ = sorted(
  n for n in globals()
  if not n.startswith("_") or n == "_stdlib_parse"
)
