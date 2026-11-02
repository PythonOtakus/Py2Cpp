"""模板函数 / 方法返回类型：decltype 与 -> None 策略。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.analyzer import SignatureBuilder, TypeParser
from src.analysis.ir import ClassInfo
from src.analysis.type_emit import sig_return_storage_cpp


class TemplateReturnTypeTests(unittest.TestCase):
  def _sig(self, src: str) -> tuple[ClassInfo, SignatureBuilder]:
    cls = ast.parse(src).body[0]
    assert isinstance(cls, ast.ClassDef)
    info = ClassInfo(cls, "test/mod")
    tp = TypeParser()
    sb = SignatureBuilder(tp)
    sb.set_classes({info.name: info})
    return info, sb

  def test_template_method_with_return_uses_decltype(self) -> None:
    info, sb = self._sig("""
class Box[T]:
  def map(self, x):
    return x + 1
""")
    sig = sb.build_method_sig(info, info.methods["map"])
    self.assertEqual(sig_return_storage_cpp(sig), "auto")
    self.assertIn("decltype", sig.ret_trail)

  def test_template_void_method_infers_void(self) -> None:
    info, sb = self._sig("""
class Doc[T]:
  def replace_at(self, steps, value):
    pass
""")
    sig = sb.build_method_sig(info, info.methods["replace_at"])
    self.assertEqual(sig_return_storage_cpp(sig), "void")
    self.assertEqual(sig.ret_trail, "")

  def test_implicit_void_dunder_skips_none_annotation(self) -> None:
    info, sb = self._sig("""
class Cur[T]:
  def __setattr__(self, name, value):
    pass
""")
    sig = sb.build_method_sig(info, info.methods["__setattr__"])
    self.assertEqual(sig_return_storage_cpp(sig), "void")
    self.assertEqual(sig.ret_trail, "")

  def test_explicit_none_annotation_is_void(self) -> None:
    info, sb = self._sig("""
class Doc[T]:
  def replace_at(self, steps, value) -> None:
    pass
""")
    sig = sb.build_method_sig(info, info.methods["replace_at"])
    self.assertEqual(sig_return_storage_cpp(sig), "void")


if __name__ == "__main__":
  unittest.main()
