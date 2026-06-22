"""函数签名 ``T @Desc(...)`` 注入 ``__set__`` 校验体。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class DescriptorSignatureTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_param_and_return_validate_injected(self):
    cpp = self._translate(
      '''
from py2cpp import descriptor

@descriptor
class ClampedIntVar:
  def __init__(self, lo: int, hi: int):
    self._lo = lo
    self._hi = hi
  def __get__(self):
    ...
  def __set__(self, value: int):
    if value < self._lo or value > self._hi:
      raise ValueError("out of range")

def f(x: int @ClampedIntVar(0, 10)) -> int @ClampedIntVar(0, 10):
  return x
'''
    )
    self.assertIn("throw py2cpp::core::exceptions::ValueError", cpp)
    self.assertIn("__py2cpp_return", cpp)
    self.assertIn("__set_f_param_x(PyInt& x)", cpp)
    self.assertIn("__set_f_return(PyInt& value)", cpp)
    self.assertIn("__set_f_param_x(x)", cpp)
    self.assertIn("__set_f_return(__py2cpp_return)", cpp)
    param_pos = cpp.index("__set_f_param_x(PyInt& x)")
    fn_pos = cpp.index("PyInt f(PyInt x)")
    self.assertLess(param_pos, fn_pos, "校验辅助函数须在 f 之前定义")

  def test_nested_matmult_with_annotation_name_ignored(self):
    cpp = self._translate(
      '''
from py2cpp import descriptor, annotation

@annotation
class Meta:
  pass

@descriptor
class ClampedIntVar:
  def __init__(self, lo: int, hi: int):
    self._lo = lo
    self._hi = hi
  def __get__(self):
    ...
  def __set__(self, value: int):
    if value < self._lo or value > self._hi:
      raise ValueError("bad")

def g(x: int @Meta @ClampedIntVar(0, 1)) -> int:
  return x
'''
    )
    self.assertIn("throw py2cpp::core::exceptions::ValueError", cpp)

  def test_if_or_compare_without_excess_parens(self):
    cpp = self._translate(
      '''
def f(v: int) -> int:
  if v < 0 or v > 9:
    v = -1
  return v
'''
    )
    self.assertIn("if (v < 0 || v > 9)", cpp)
    self.assertNotIn("((((", cpp)

  def test_class_static_method_uses_named_helpers(self):
    cpp = self._translate(
      '''
from py2cpp import descriptor, staticmethod

@descriptor
class ClampedIntVar:
  def __init__(self, lo: int, hi: int):
    self._lo = lo
    self._hi = hi
  def __get__(self):
    ...
  def __set__(self, value: int):
    if value < self._lo or value > self._hi:
      raise ValueError("bad")

class Svc:
  @staticmethod
  def pick(n: int @ClampedIntVar(1, 5)) -> int @ClampedIntVar(1, 5):
    return n * 2
'''
    )
    self.assertIn("Svc::__set_pick_param_n", cpp)
    self.assertIn("Svc::__set_pick_return", cpp)
    self.assertIn("Svc::__set_pick_param_n(n)", cpp)
    self.assertIn("Svc::__set_pick_return(__py2cpp_return)", cpp)
    pick_body = cpp.split("Svc::pick(PyInt n)")[1].split("Svc::")[0]
    self.assertNotIn("throw py2cpp::core::exceptions::ValueError", pick_body)

  def test_replace_if_bad_param_helper_uses_mutable_ref(self):
    cpp = self._translate(
      '''
from py2cpp import descriptor

@descriptor
class ReplaceIfBadVar:
  def __init__(self, lo: int, hi: int, bad: int):
    self._lo = lo
    self._hi = hi
    self._bad = bad
  def __get__(self):
    ...
  def __set__(self, value: int):
    if value < self._lo or value > self._hi:
      self.__value__ = self._bad

class Svc:
  def store(self, v: int @ReplaceIfBadVar(0, 9, -1)) -> None:
    self._v = v
  _v: int = 0
'''
    )
    self.assertIn("Svc::__set_store_param_v(PyInt& v)", cpp)


if __name__ == "__main__":
  unittest.main()
