"""同类 protected 访问：局部 ``Self`` 变量与 ``abs(self)`` 接收者。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.access import collect_external_protected_accesses
from src.analysis.ir import ClassInfo
from src.passes.access import expand_member_access
from src.passes.mixins import expand_mixins
from src.translator import Translator


class SameClassProtectedAccessTests(unittest.TestCase):
  def _build(self, src: str) -> Translator:
    mod = ast.parse(src)
    tr = Translator("test/long_access", "test/long_access.py")
    for node in mod.body:
      if isinstance(node, ast.ClassDef):
        tr.classes[node.name] = ClassInfo(node, "test/long_access")
    expand_mixins(tr)
    return tr

  def test_local_self_var_may_call_protected_method(self):
    src = """
from py2cpp import Self, copyable, immutable

@copyable
class long:
  @immutable
  def _peek(self) -> int:
    return 1

  def demo(self, other: Self) -> int:
    sa: Self = abs(self)
    sb: Self = abs(other)
    return sa._peek() + sb._peek()
"""
    tr = self._build(src)
    ext = collect_external_protected_accesses(
      tr.classes, tr.module_functions, tr.module_asts, tr.import_bindings,
    )
    self.assertEqual(ext, set())
    expand_member_access(tr)

  def test_new_static_protected_same_class(self):
    src = """
from py2cpp import Self, copyable, immutable

@copyable
class long:
  @staticmethod
  @immutable
  def _zero() -> Self:
    return new()

  def demo(self) -> Self:
    mag: Self = new._zero()
    return mag
"""
    tr = self._build(src)
    ext = collect_external_protected_accesses(
      tr.classes, tr.module_functions, tr.module_asts, tr.import_bindings,
    )
    self.assertEqual(ext, set())

  def test_abs_chain_may_call_protected_method(self):
    src = """
from py2cpp import Self, copyable, immutable

@copyable
class long:
  @immutable
  def _divmod_abs(self, other: Self) -> int:
    return 0

  def demo(self, other: Self) -> int:
    parts: int = abs(self)._divmod_abs(abs(other))
    return parts
"""
    tr = self._build(src)
    ext = collect_external_protected_accesses(
      tr.classes, tr.module_functions, tr.module_asts, tr.import_bindings,
    )
    self.assertEqual(ext, set())


if __name__ == "__main__":
  unittest.main()
