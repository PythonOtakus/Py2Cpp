"""mixin 内联后 ``PySet``/``PyFrozenSet`` 注解按宿主 ``template_cpp_type()`` 解析。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.analyzer import SemanticAnalyzer, TypeParser
from src.analysis.ir import ClassInfo, resolve_host_cpp_type
from src.analysis.type_emit import sig_return_storage_cpp
from src.passes.mixins import expand_mixins
from src.translator import Translator


class MixinInlinedHostCppTypeTests(unittest.TestCase):
  def test_resolve_host_cpp_type_maps_cpp_base_name(self):
    self.assertEqual(
      resolve_host_cpp_type("PySet", "PySet<T>"),
      "PySet<T>",
    )
    self.assertEqual(
      resolve_host_cpp_type("Self", "PyFrozenSet<T>"),
      "PyFrozenSet<T>",
    )
    self.assertIsNone(resolve_host_cpp_type("PyList", "PySet<T>"))

  def test_mixin_inlined_or_return_type_has_template_args(self):
    src = """
from py2cpp import mixin, Self, immutable

@mixin
class FrozenSetMixin[T]:
  @immutable
  def __or__(self, other: Self) -> Self:
    out: Self = Self()
    return out

class set[T](FrozenSetMixin[T]):
  pass
"""
    tr = Translator("mod", "mod.py")
    tr._parse_modules([("mod", src)])
    expand_mixins(tr)
    host = tr.classes["set"]
    method = host.methods["__or__"]
    self.assertIsInstance(method.returns, ast.Name)
    self.assertEqual(method.returns.id, "Self")

    host_cpp = host.template_cpp_type()
    SemanticAnalyzer().analyze(tr)
    self.assertEqual(sig_return_storage_cpp(host.method_sigs["__or__"]), host_cpp)

  def test_mixin_multi_type_param_substitution(self):
    src = """
from py2cpp import mixin, Self, immutable, new

@mixin
class TransformMixin[Vec, Rot, Mat]:
  @immutable
  def local_to_world_point(self, point: Vec) -> Vec:
    return point

  @property
  @immutable
  def rotation(self) -> Rot:
    r: Rot = new()
    return r

class Transform2D(TransformMixin[Vector2, Rotator, Matrix3]):
  pass

class Vector2:
  pass

class Rotator:
  pass

class Matrix3:
  pass
"""
    tr = Translator("mod", "mod.py")
    tr._parse_modules([("mod", src)])
    expand_mixins(tr)
    host = tr.classes["Transform2D"]
    method = host.methods["local_to_world_point"]
    self.assertEqual(method.args.args[1].annotation.id, "Vector2")
    self.assertEqual(method.returns.id, "Vector2")
    rot_getter = host.properties["rotation"].getter
    self.assertEqual(rot_getter.returns.id, "Rotator")

  def test_host_subscript_uses_slice_type_args_not_host_instantiation(self):
    tp = TypeParser()
    node = ast.parse("ECSComponentTable[U]", mode="eval").body
    out = tp.parse_type(node, {"T", "U"}, self_class="ECSComponentTable<T>")
    self.assertEqual(out, "ECSComponentTable<U>")

  def test_self_stack_array_open_slice_resolves_host_type(self):
    tp = TypeParser()
    node = ast.parse("Self[:]", mode="eval").body
    self.assertEqual(tp.parse_type(node, set()), "PyArray<Self>")
    self.assertEqual(
      tp.parse_type(node, set(), self_class="PyStr"),
      "PyArray<PyStr>",
    )
    self.assertEqual(
      tp.parse_type(node, set(), self_class="Vector4"),
      "PyArray<Vector4>",
    )

  def test_self_fixed_stack_array_resolves_host_elem(self):
    tp = TypeParser()
    node = ast.parse("Self[:4]", mode="eval").body
    self.assertEqual(
      tp.parse_type(node, set(), self_class="PyStr"),
      "PyStackArray<PyStr, 4, 0>",
    )

  def test_self_const_dim_stack_array2d(self):
    src = """
class Matrix3:
  _dim: int @const = 3
"""
    tr = Translator("py2cpp/spatial/matrix", "matrix.py")
    tr._parse_modules([("py2cpp/spatial/matrix", src)])
    host = tr.classes["Matrix3"]
    tp = TypeParser()
    tp.set_classes(tr.classes)
    node = ast.parse("float64[:Self._dim, :Self._dim]", mode="eval").body
    self.assertEqual(
      tp.parse_type(node, set(), self_class=host.template_cpp_type()),
      "PyStackArray2D<PyFloat64, 3, 3, 0, 0>",
    )
    node2 = ast.parse("float64[:Self._dim, :Self._dim * 2]", mode="eval").body
    self.assertEqual(
      tp.parse_type(node2, set(), self_class=host.template_cpp_type()),
      "PyStackArray2D<PyFloat64, 3, 6, 0, 0>",
    )

  def test_list_self_type_arg_resolves_host(self):
    tp = TypeParser()
    node = ast.parse("list[Self]", mode="eval").body
    self.assertEqual(
      tp.parse_type(node, set(), self_class="PyStr"),
      "PyList<PyStr>",
    )

  def test_self_in_subscript_and_tuple_return_types(self):
    src = """
from py2cpp import Self, copyable, immutable

@copyable
class str:
  @immutable
  def split(self, sep: Self = "") -> list[Self]:
    out: list[Self] = []
    return out

  @immutable
  def partition(self, sep: Self) -> (Self, Self, Self):
    return (self, sep, self)
"""
    tr = Translator("py2cpp/text/str", "py2cpp/text/str.py")
    tr._parse_modules([("py2cpp/text/str", src)])
    info = tr.classes["str"]
    SemanticAnalyzer().analyze(tr)
    host_cpp = info.template_cpp_type()
    self.assertEqual(sig_return_storage_cpp(info.method_sigs["split"]), f"PyList<{host_cpp}>")
    self.assertEqual(
      sig_return_storage_cpp(info.method_sigs["partition"]),
      f"PyTuple<{host_cpp}, {host_cpp}, {host_cpp}>",
    )


if __name__ == "__main__":
  unittest.main()
