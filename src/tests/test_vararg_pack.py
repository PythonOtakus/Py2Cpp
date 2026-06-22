"""``*args: T[:]`` 译器：签名、空调用空包、多实参 IIFE 打包、非法注解报错。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translation_error import TranslationError
from src.translator import Translator


class VarargPackEmitTests(unittest.TestCase):
  def _translate(self, extra: str, *, entry_body: str = "") -> str:
    src = f"""
def only_vararg(*nums: int[:]) -> int:
  return len(nums)

def with_head(first: int, *rest: int[:]) -> int:
  return first + len(rest)

def main():
{entry_body or "    pass\n"}
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src + extra, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      return text

  def test_signature_includes_pyarray_param(self):
    cpp = self._translate("")
    self.assertRegex(
      cpp,
      re.compile(r"only_vararg\s*\(\s*PyArray<PyInt>\s+nums\s*\)"),
    )

  def test_empty_call_empty_array(self):
    cpp = self._translate("", entry_body="    only_vararg()\n")
    self.assertIn("only_vararg(PyArray<PyInt>())", cpp.replace("\n", ""))

  def test_multi_positional_pack_iife(self):
    cpp = self._translate("", entry_body="    only_vararg(1, 2, 3)\n")
    self.assertIn("PyArray<PyInt>", cpp)
    self.assertIn("__setitem__", cpp)
    self.assertRegex(cpp, re.compile(r"\[\&\]\(\)\s*->\s*PyArray<PyInt>"))

  def test_fixed_plus_vararg_split(self):
    cpp = self._translate("", entry_body="    with_head(10, 20, 30)\n")
    self.assertRegex(cpp, re.compile(r"with_head\s*\(\s*10\s*,"))

  def test_interleave_scalars_and_starred_packs(self):
    src = """
def pack(*nums: int[:]) -> int:
  return len(nums)

def mix(a: int[:], b: int[:]) -> int:
  return pack(3, *a, 4, *b, 5)

def main():
  x: int[:] = pack(1, 2)
  y: int[:] = pack(7)
  mix(x, y)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
    self.assertIn("__getitem__", text)
    self.assertGreaterEqual(text.count("__setitem__"), 2)

  def test_forward_starred_call(self):
    src = """
def inner(*nums: int[:]) -> int:
  return len(nums)

def outer(*nums: int[:]) -> int:
  return inner(*nums)

def main():
  outer(1, 2)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
    self.assertRegex(
      text,
      re.compile(
        r"PyInt outer\(PyArray<PyInt> nums\)\s*\{\s*return inner\(nums\)",
      ),
    )

  def test_forward_to_fixed_param_fails(self):
    src = """
def inner(x: int) -> int:
  return x

def outer(*nums: int[:]) -> int:
  return inner(*nums)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=True,
        )
      msg = str(ctx.exception)
      self.assertTrue(
        "普通形参" in msg or "不能把可变参数整包" in msg,
        msg,
      )

  def test_non_array_vararg_annotation_fails(self):
    src = """
def bad(*nums: int) -> int:
  return 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=True,
        )
      self.assertIn("T[:]", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
