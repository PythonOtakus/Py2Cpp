"""推导式与字面量容器类型对齐（``deque`` / ``frozen*``）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ComprehensionContainerEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_deque_comp_uses_pydeque(self):
    cpp = self._translate(
      "def f() -> int:\n"
      "  src: list[int] = [1, 2]\n"
      "  dq: deque[int] = [x for x in src]\n"
      "  return len(dq)\n",
    )
    self.assertIn("PyDeque<", cpp)
    self.assertNotIn("PyList<PyInt> dq", cpp.replace(" ", ""))

  def test_frozenlist_comp_initFromList(self):
    cpp = self._translate(
      "def f() -> int:\n"
      "  src: list[int] = [1]\n"
      "  fl: frozenlist[int] = [x for x in src]\n"
      "  return len(fl)\n",
    )
    self.assertIn("initFromList", cpp)


if __name__ == "__main__":
  unittest.main()
