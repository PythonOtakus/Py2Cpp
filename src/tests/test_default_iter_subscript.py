"""``default_iter`` 注入的 ``_host[i]`` 须生成 ``__getitem__``，勿 C 指针下标。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class DefaultIterSubscriptTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_host_ptr_uses_getitem_in_iterator_next(self):
    cpp = self._translate(
      '''from py2cpp import *

class Box:
  def __len__(self) -> int:
    return 1

  def __getitem__(self, i: int) -> int:
    return 7

def run() -> int:
  b: Box = new()
  for x in b:
    return x
  return 0
''',
    )
    self.assertIn("__getitem__", cpp)
    self.assertNotIn("_host[this->_index]", cpp)


if __name__ == "__main__":
  unittest.main()
