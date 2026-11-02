"""list 元素赋给局部变量后 ``@property`` 读取。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class PropertyListLocalTests(unittest.TestCase):
  def test_local_from_list_subscript_property_read(self):
    src = """
from py2cpp import *

@refcount
class Slot:
  _id: int64 = 0

  @property
  def slot_id(self) -> int64:
    return self._id

class Sched:
  _slots: list[Slot] = []

  def find(self, tid: int64) -> Slot:
    for i in range(len(self._slots)):
      slot: Slot = self._slots[i]
      if slot.slot_id == tid:
        return slot
    raise RuntimeError("missing")

def main():
  pass
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py),
        output_dir=str(out),
        include_stdlib=False,
        strict=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("slot_id__get()", cpp)
      self.assertNotRegex(cpp, r"slot->slot_id[^_]")


if __name__ == "__main__":
  unittest.main()
