"""``*pack: T[:N]`` mixin 注入展开为 ``__arg_{pack}i``。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.ir import ClassInfo
from src.passes.fixed_vararg import expand_fixed_vararg


def _parse_class(src: str) -> ClassInfo:
  mod = ast.parse(src)
  node = mod.body[0]
  assert isinstance(node, ast.ClassDef)
  return ClassInfo(node)


class ExpandFixedVarargTests(unittest.TestCase):
  def test_expands_axis_pack_for_host_dim(self):
    host = _parse_class(
      """
class Matrix3:
  _dim: int @const = 3
""",
    )
    method = ast.parse(
      """
def from_axes_origin(*axis: Vec[:Self._dim - 1], origin: Vec = new.zero):
  x = axis[0]
""",
    ).body[0]
    assert isinstance(method, ast.FunctionDef)
    out = expand_fixed_vararg(method, host)
    assert out is not None
    assert out.args.vararg is None
    self.assertEqual([a.arg for a in out.args.args], ["__arg_axis0", "__arg_axis1", "origin"])
    sub = out.body[0].value  # type: ignore[attr-defined]
    assert isinstance(sub, ast.Subscript)
    assert isinstance(sub.value, ast.List)
    self.assertEqual(len(sub.value.elts), 2)


if __name__ == "__main__":
  unittest.main()
