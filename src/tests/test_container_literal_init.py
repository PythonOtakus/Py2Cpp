"""``MutableMapping`` / ``Appendable`` / ``add`` 字面量初始化（非仅 ``PyDict`` / ``PyList``）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ContainerLiteralInitTests(unittest.TestCase):
  def _translate(self, src: str, *, include_stdlib: bool = False) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=include_stdlib,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_counter_dict_literal_ann_assign(self):
    cpp = self._translate(
      """
from py2cpp import *
from py2cpp.util.misc import Counter

def f():
  c: Counter[str] = {"a": 3, "b": 1}
""",
      include_stdlib=True,
    )
    self.assertIn("Counter<", cpp)
    self.assertIn("__setitem__", cpp)

  def test_counter_update_dict_literal_arg(self):
    cpp = self._translate(
      """
from py2cpp import *
from py2cpp.util.misc import Counter

def f():
  c: Counter[str] = new()
  c.update({"x": 1, "y": 2})
""",
      include_stdlib=True,
    )
    self.assertIn("update(", cpp)
    self.assertIn("__setitem__", cpp)

  def test_custom_set_with_add_literal(self):
    cpp = self._translate(
      """
from py2cpp import *

class Bag[T: DictKey]:
  def __init__(self):
    pass

  def add(self, item: T):
    pass

def f():
  s: Bag[int] = {1, 2, 3}
""",
    )
    self.assertIn("Bag<", cpp)
    self.assertIn(".add(", cpp)

  def test_custom_list_with_append_literal(self):
    cpp = self._translate(
      """
from py2cpp import *

class Stack[T]:
  def __init__(self):
    pass

  def append(self, item: T):
    pass

def f():
  st: Stack[int] = [1, 2, 3]
""",
    )
    self.assertIn("Stack<", cpp)
    self.assertIn(".append(", cpp)

  def test_module_level_list_literal_ann(self):
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        """
from py2cpp import *

_items: list[int] = []
""",
        encoding="utf-8",
      )
      header_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = header_path.read_text(encoding="utf-8")
    self.assertIn("static PyList<", cpp)
    self.assertIn("_items", cpp)


if __name__ == "__main__":
  unittest.main()
