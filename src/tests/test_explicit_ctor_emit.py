"""用户类 ``explicit`` 构造与 ``explicit operator Py*`` 声明 emit。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ExplicitCtorEmitTests(unittest.TestCase):
  def _translate(self, src: str, *, with_import: bool = False) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      body = f"from py2cpp import *\n\n{src}" if with_import else src
      py.write_text(body, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      return h_path.read_text(encoding="utf-8") + cpp_path.read_text(encoding="utf-8")

  def test_init_overload_self_forward_delegate_ctor(self):
    cpp = self._translate(
      '''class Pair:
  a: int
  b: int

  @overload
  def __init__(self, a: int):
    self.__init__(a, 0)

  @overload
  def __init__(self, a: int, b: int):
    self.a = a
    self.b = b


def main():
  p: Pair = new(1)
  return p.a + p.b
''',
      with_import=True,
    )
    self.assertIn("PyPair::PyPair(PyInt a) : PyPair(a, 0)", cpp)

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
    self.assertIn("explicit PyBox(PyInt x);", h)
    self.assertIn("explicit PyEmpty();", h)

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
