"""``@property.postsetter`` 合成 getter/setter 与用户 ``name__postset``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class PropertyPostsetterEmitTests(unittest.TestCase):
  def test_emits_synthetic_setter_and_postset(self):
    src = """
class Counter:
  last_set: int = 0

  @property.postsetter
  def x(self, value: int) -> None:
    self.last_set = value
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      h = cpp_path.with_suffix(".h").read_text(encoding="utf-8")
      compact = cpp.replace(" ", "")
      compact_h = h.replace(" ", "")
      self.assertIn("x__get()const", compact_h)
      self.assertIn("x__set(PyIntvalue)", compact_h)
      self.assertIn("x__postset(PyIntvalue)", compact_h)
      self.assertIn("this->x__value=value;", compact)
      self.assertIn("this->x__postset(value);", compact)
      self.assertIn("this->last_set=value;", compact)
      self.assertNotIn("__value__", cpp)

  def test_field_annotation_shorthand(self):
    src = """
class Counter:
  last_set: int = 0

  def on_x(self, value: int) -> None:
    self.last_set = value

  x: int @property.postsetter(on_x) = 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      compact = cpp.replace(" ", "")
      self.assertIn("this->x__postset(value);", compact)
      self.assertIn("this->last_set=value;", compact)

  def test_field_shorthand_conflicts_with_method(self):
    src = """
class Bad:
  x: int @property.postsetter(on_x) = 0
  last_set: int = 0

  def on_x(self, value: int) -> None:
    self.last_set = value

  @property.postsetter
  def x(self, value: int) -> None:
    pass
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(Exception) as ctx:
        Translator.translate_file(str(py), output_dir=str(out), include_stdlib=False)
      self.assertIn("冲突", str(ctx.exception))

  def test_rejects_postsetter_with_getter(self):
    src = """
class Bad:
  @property
  def x(self) -> int:
    return 0

  @property.postsetter
  def x(self, value: int) -> None:
    pass
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(ValueError) as ctx:
        Translator.translate_file(str(py), output_dir=str(out), include_stdlib=False)
      self.assertIn("@property.postsetter", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
