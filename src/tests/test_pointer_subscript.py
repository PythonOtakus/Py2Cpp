"""``Pointer[T]`` / ``T*`` 裸下标 → ``ptr[i]``（非 ``.__getitem__``）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class PointerSubscriptTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True, strict=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_container_view_uses_view_get(self):
    cpp = self._translate(
      '''
from py2cpp import *

def f() -> int:
  buf: int[:4] = new()
  buf[0] = 1
  vw = buf.view
  return vw[0]
'''
    )
    self.assertIn("view__get()", cpp)
    self.assertNotRegex(cpp, r"buf\.view[^_]")

  def test_property_ptr_subscript_assign(self):
    cpp = self._translate(
      '''
from py2cpp import *

@copyable
class Holder:
  _ptr: Pointer[int] = None

  @property
  def buf(self) -> Pointer[int]:
    return self._ptr

  def set_at(self, i: int, v: int) -> None:
    self.buf[i] = v
'''
    )
    self.assertIn("buf__get()[i]=v", cpp.replace(" ", ""))
    self.assertNotIn("__setitem__", cpp)

  def test_nested_property_ptr_subscript_assign(self):
    cpp = self._translate(
      '''
from py2cpp import *

@copyable
class Inner:
  _ptr: Pointer[int] = None

  @property
  def buf(self) -> Pointer[int]:
    return self._ptr

@copyable
class Outer:
  inner: Inner

  def set_at(self, i: int, v: int) -> None:
    self.inner.buf[i] = v
'''
    )
    self.assertIn("inner.buf__get()[i]=v", cpp.replace(" ", ""))
    self.assertNotIn("__setitem__", cpp)

  def test_property_ptr_subscript_iadd(self):
    cpp = self._translate(
      '''
from py2cpp import *

@copyable
class Holder:
  _ptr: Pointer[int] = None

  @property
  def buf(self) -> Pointer[int]:
    return self._ptr

  def bump(self, i: int) -> None:
    self.buf[i] += 1
'''
    )
    self.assertIn("buf__get()[i]+=1", cpp.replace(" ", ""))
    self.assertNotIn("__setitem__", cpp)

  def test_span_data_subscript(self):
    cpp = self._translate(
      '''
from py2cpp import *

def f() -> int:
  sub: span[int] = new()
  return sub.at()[0]
'''
    )
    self.assertIn(".at()[0]", cpp)
    self.assertNotIn(".__getitem__(0)", cpp)


if __name__ == "__main__":
  unittest.main()
