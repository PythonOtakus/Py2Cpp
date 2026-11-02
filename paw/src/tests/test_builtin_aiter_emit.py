"""``aiter`` / ``anext`` 全局内置 emit。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class BuiltinAiterEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_aiter_anext_call(self):
    cpp = self._translate(
      '''
from py2cpp import aiter, anext

async def gen():
  yield 1

async def step() -> int:
  it = aiter(gen())
  r = anext(it)
  return r.value
''',
    )
    self.assertIn("__aiter__()", cpp)
    self.assertIn("__anext__()", cpp)


if __name__ == "__main__":
  unittest.main()
