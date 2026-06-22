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
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_container_view_uses_view_get(self):
    cpp = self._translate(
      '''
from py2cpp import new

def f() -> int:
  buf: int[:4] = new()
  buf[0] = 1
  vw = buf.view
  return vw[0]
'''
    )
    self.assertIn("buf.view__get()", cpp)
    self.assertNotIn("buf.view", cpp)

  def test_span_data_subscript(self):
    cpp = self._translate(
      '''
from py2cpp import span, new

def f() -> int:
  sub: span[int] = new()
  return sub.at()[0]
'''
    )
    self.assertIn(".at()[0]", cpp)
    self.assertNotIn(".__getitem__(0)", cpp)


if __name__ == "__main__":
  unittest.main()
