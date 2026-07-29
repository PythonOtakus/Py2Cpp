"""``@dataclass(frozen=True)`` → 全字段 ``T @final``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translation_error import TranslationError
from src.translator import Translator


class DataclassFrozenTests(unittest.TestCase):
  def _translate(self, extra: str) -> str:
    src = f"""
from py2cpp import *

{extra}
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      out = Path(tmp) / "out"
      h_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return h_path.read_text(encoding="utf-8")

  def test_frozen_fields_emit_const_members(self):
    h = self._translate(
      """
@dataclass(frozen=True)
class FrozenPoint:
  x: int
  y: int = 0
""",
    )
    self.assertIn("const PyInt x", h)
    self.assertIn("const PyInt y", h)

  def test_explicit_final_on_frozen_field(self):
    h = self._translate(
      """
@dataclass(frozen=True)
class Mixed:
  a: int @final
  b: int
""",
    )
    self.assertIn("const PyInt a", h)
    self.assertIn("const PyInt b", h)

  def test_frozen_copyable_rejected(self):
    src = """
from py2cpp import *

@copyable
@dataclass(frozen=True)
class FrozenBox:
  x: int
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(Path(tmp) / "out"), include_stdlib=True,
        )
      self.assertIn("@copyable 与 @dataclass(frozen=True) 不能同用", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
