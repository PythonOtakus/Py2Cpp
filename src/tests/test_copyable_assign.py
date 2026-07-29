"""``@copyable`` 同类赋值须走拷贝，勿在 ``const`` 方法里误生成 ``__move__``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class CopyableAssignTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    src = f"""
from py2cpp import *

@copyable
class varint:
  def __init__(self):
    self._x: int = 0

  def __copy__(self, other: Self):
    self._x = other._x

  def __move__(self, other: Self):
    self._x = other._x
    other._x = 0

  def run(self):
{body}
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_ann_assign_same_class_uses_copy_ctor(self):
    cpp = self._translate("    b: Self = self\n")
    self.assertTrue("PyVarInt b(self)" in cpp or "PyVarInt b = *this" in cpp)
    self.assertNotIn("b.__move__(self)", cpp)

  def test_reassign_uses_copy_not_move(self):
    cpp = self._translate(
      "    e: Self = self\n"
      "    half: Self = self\n"
      "    e = half\n",
    )
    self.assertIn("e.__copy__(half)", cpp)
    self.assertNotIn("e.__move__(half)", cpp)


if __name__ == "__main__":
  unittest.main()
