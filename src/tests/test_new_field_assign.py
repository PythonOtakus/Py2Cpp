"""``other._field = new(...)`` 须从接收者字段类型推断，勿报 ``new() 需类型上下文``。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class MakeFieldAssignTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    src = f"""
from py2cpp import Self, copyable, new

@copyable
class Grid:
  def __init__(self, h: int, w: int):
    self._cells: int[:,:] = new(h, w)

  def __move__(self, other: Self):
{body}
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      return text

  def test_other_field_new_assign(self):
    cpp = self._translate("    other._cells = new(0, 0)\n")
    self.assertRegex(
      cpp,
      re.compile(r"other\._cells\s*=\s*PyArray2D<PyInt>\(0,\s*0\)"),
    )
    self.assertNotIn("new() 需类型上下文", cpp)

  def test_self_field_new_assign(self):
    cpp = self._translate("    self._cells = new(1, 2)\n")
    self.assertRegex(
      cpp,
      re.compile(r"this->_cells\s*=\s*PyArray2D<PyInt>\(1,\s*2\)"),
    )


class FieldLiteralAssignTests(unittest.TestCase):
  def _translate(self, body: str, *, fields: str) -> str:
    src = f"""
from py2cpp import Self, copyable, new
from py2cpp.util.list import list

@copyable
class Box:
{fields}

  def __move__(self, other: Self):
{body}
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      return text

  def test_other_nested_list_empty(self):
    fields = "  _adj: list[list[int]]\n"
    cpp = self._translate("    other._adj = []\n", fields=fields)
    self.assertRegex(
      cpp,
      re.compile(r"other\._adj\s*=\s*PyList<PyList<PyInt>>\(\)"),
    )
    self.assertNotIn("PyList<PyInt>()", cpp)

  def test_other_dict_empty(self):
    fields = "  _m: dict[int, int]\n"
    cpp = self._translate("    other._m = {}\n", fields=fields)
    self.assertIn("other._m = PyDict<PyInt, PyInt>()", cpp.replace("\n", ""))


if __name__ == "__main__":
  unittest.main()
