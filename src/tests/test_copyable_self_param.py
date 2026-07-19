"""``@copyable`` 类实例方法 ``Self`` 形参须 ``const T&``（避免按值拷贝递归）。"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from src.analysis.analyzer import SignatureBuilder, TypeParser
from src.analysis.ir import ClassInfo, FuncTypeParams
from src.translator import Translator


class CopyableSelfParamTests(unittest.TestCase):
  def test_instance_method_self_param_is_const_ref(self):
    src = """
from py2cpp import copyable, Self

@copyable
class Widget:
  def touch(self, other: Self) -> None:
    pass
"""
    tree = ast.parse(src)
    cls = tree.body[1]
    method = cls.body[0]
    info = ClassInfo(cls, module_path="t/w")
    sb = SignatureBuilder(TypeParser())
    sb.set_classes({"Widget": info})
    func_ft = FuncTypeParams.collect(method)
    arg = method.args.args[1]
    cpp = sb._param_cpp_type(
      arg, class_type_params=[], func_ft=func_ft, info=info, method=method,
    )
    self.assertEqual(cpp, "const Widget&")

  def test_staticmethod_self_param_by_value(self):
    src = """
from py2cpp import copyable, Self, staticmethod

@copyable
class Widget:
  @staticmethod
  def clone(src: Self) -> Self:
    return src
"""
    tree = ast.parse(src)
    cls = tree.body[1]
    method = cls.body[0]
    info = ClassInfo(cls, module_path="t/w")
    sb = SignatureBuilder(TypeParser())
    sb.set_classes({"Widget": info})
    func_ft = FuncTypeParams.collect(method)
    arg = method.args.args[0]
    cpp = sb._param_cpp_type(
      arg, class_type_params=[], func_ft=func_ft, info=info, method=method,
    )
    self.assertEqual(cpp, "Widget")

  def test_decimal_compare_emits_const_ref(self):
    src = """
from py2cpp import *

@copyable
class Decimal:
  def __eq__(self, other: Self) -> bool:
    return True
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("__eq__(constPyDecimal&other)", cpp.replace(" ", ""))


if __name__ == "__main__":
  unittest.main()
