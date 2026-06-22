"""``new(类型/类名)`` 任意上下文须翻译失败。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translation_error import TranslationError
from src.translator import Translator


class NewTypeArgRejectTests(unittest.TestCase):
  def _expect_fail(self, body: str) -> None:
    src = f"""
from py2cpp import copyable, dataclass, new

@dataclass
@copyable
class Box:
  x: int = 0

{body}
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(str(py), output_dir=tmp, include_stdlib=True)
      self.assertIn("不得以类型或类名", str(ctx.exception))

  def test_new_subscript_type(self):
    self._expect_fail(
      "def f() -> None:\n    xs: list[int] = new(list[int])\n",
    )

  def test_new_class_name(self):
    self._expect_fail(
      "def f() -> None:\n    b: Box = new(Box)\n",
    )

  def test_new_builtin_type_name(self):
    self._expect_fail(
      "def f() -> None:\n    n: int = new(int)\n",
    )

  def test_new_enum_member_ok(self):
    src = """
from py2cpp import enum, new

@enum
class Mode:
  A = 1
  B = 2

def f() -> None:
    m: Mode = new(Mode.A)
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      Translator.translate_file(str(py), output_dir=tmp, include_stdlib=True)

  def test_new_capacity_still_ok(self):
    src = """
from py2cpp import new

def f() -> None:
    buf: int[:] = new(4)
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      Translator.translate_file(str(py), output_dir=tmp, include_stdlib=True)

  def test_new_scalar_static_attr_ok(self):
    src = """
from py2cpp import *

def f() -> float:
    return new(float.NaN)
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      Translator.translate_file(str(py), output_dir=tmp, include_stdlib=True)

  def test_new_complex_static_attr_ok(self):
    src = """
from py2cpp import *

def f() -> complex:
    return new(complex.NaNj)
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      Translator.translate_file(str(py), output_dir=tmp, include_stdlib=True)


if __name__ == "__main__":
  unittest.main()
