"""``return new(kw=…)`` 与泛型返回注解脱糖为临时变量。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class KwargsReturnNewTests(unittest.TestCase):
  def test_return_new_kw_with_subscript_return_ann(self):
    src = '''
from py2cpp import *

@copyable
class Task:
  taskId: int = 0

def make() -> Task[int]:
  tid: int = 7
  return new(taskId=tid)
'''
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("__py2cpp_opts", cpp)
      self.assertIn("taskId =", cpp)
      self.assertIn("return __py2cpp_opts", cpp)

  def test_new_ctor_default_keeps_delegate_generic(self):
    src = '''
from py2cpp import *

@copyable
class Delegate[Element]:
  pass

@dataclass
class Box:
  hook: Delegate[bool] = new()

def use() -> None:
  x: Box = new()
'''
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("PyDelegate<PyBool>", cpp)
      self.assertNotRegex(cpp, r"PyDelegate\s*\(\s*\)")


if __name__ == "__main__":
  unittest.main()
