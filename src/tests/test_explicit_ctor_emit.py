"""用户类 ``explicit`` 构造与 ``explicit operator Py*`` 声明 emit。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ExplicitCtorEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      return h_path.read_text(encoding="utf-8")

  def test_init_and_default_ctor_explicit(self):
    h = self._translate(
      '''
class Box:
  x: int
  def __init__(self, x: int) -> None:
    self.x = x

class Empty:
  def __init__(self) -> None:
    pass
''',
    )
    self.assertIn("explicit Box(PyInt x);", h)
    self.assertIn("explicit Empty();", h)

  def test_conversion_operators_explicit(self):
    h = self._translate(
      '''
class N:
  def __bool__(self) -> bool:
    return True
  def __int__(self) -> int:
    return 1
  def __str__(self) -> str:
    return "n"
''',
    )
    self.assertIn("explicit operator PyBool() const;", h)
    self.assertIn("explicit operator PyInt() const;", h)
    self.assertIn("explicit operator PyStr() const;", h)


if __name__ == "__main__":
  unittest.main()
