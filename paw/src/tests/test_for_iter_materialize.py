"""``for x in expr``：右值 ``list``（如调用返回值）须物化后再迭代。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ForIterMaterializeTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_for_in_call_returns_list_index_loop(self):
    cpp = self._translate(
      '''
from py2cpp.util.list import list

def neighbors() -> list[int]:
  out: list[int] = []
  out.append(1)
  return out

def run() -> int:
  s: int = 0
  for x in neighbors():
    s = x
  return s
''',
    )
    self.assertIn("seq", cpp)
    self.assertIn("neighbors()", cpp)
    self.assertIn("for (PyInt", cpp)
    self.assertIn(".__getitem__", cpp)
    run_body = cpp.split("PyInt run()")[1]
    self.assertNotIn("PyListIterator<", run_body)

  def test_for_in_call_no_ampersand_on_temp(self):
    cpp = self._translate(
      '''
from py2cpp.util.list import list

def items() -> list[int]:
  xs: list[int] = []
  xs.append(3)
  return xs

def take() -> int:
  v: int = 0
  for n in items():
    v = n
  return v
''',
    )
    self.assertNotIn("&items()", cpp)
    self.assertNotIn("&neighbors()", cpp)


if __name__ == "__main__":
  unittest.main()
