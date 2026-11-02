"""``obj.assign(kw=…)`` 脱糖为字段赋值，不生成 C++ ``assign`` 成员。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.passes.kwargs_options import expand_kwargs_options
from src.translator import Translator


class KwargsAssignInlineTests(unittest.TestCase):
  def test_assign_no_cpp_method_in_header(self):
    src = '''
from py2cpp import copyable

@copyable
class Box:
  def __init__(self):
    self.width: int = 0
    self.title: str = ""

def use(b: Box):
  b.assign(width=9, title="x")
'''
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      h = h_path.read_text(encoding="utf-8")
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertNotIn("void assign(", h)
      self.assertNotIn(" assign(", h)
      self.assertIn("b.width =", cpp)
      self.assertIn("b.title =", cpp)


  def test_assign_positional_rejected(self):
    src = '''
from py2cpp import copyable

@copyable
class Box:
  def __init__(self):
    self.width: int = 0

def use(self: Box, opts: Box):
  self.assign(opts)
'''
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      code = py.read_text(encoding="utf-8")
      tr = Translator("mod", str(py))
      tr._parse_modules([("mod", code)])
      with self.assertRaises(NotImplementedError) as ctx:
        expand_kwargs_options(tr)
      self.assertIn("位置参数", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
