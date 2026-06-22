"""同类 ``new`` / ``Self()`` 须译成全名 C++ 构造，勿生成 ``Self(...)``。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class SameClassNewCtorTests(unittest.TestCase):
  def _translate(self, src: str, *, strict: bool = True) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True, strict=strict,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      return text

  def test_copy_new_self_emits_cpp_ctor_not_self(self):
    cpp = self._translate(
      '''
from py2cpp import Self, immutable, new

class DSU:
  @immutable
  def copy(self) -> Self:
    out: Self = new(0)
    return out
'''
    )
    self.assertRegex(cpp, re.compile(r"DSU\s+out\s*=\s*DSU\(0\)"))
    self.assertNotIn("Self(0)", cpp)

  def test_copy_self_call_emits_cpp_ctor(self):
    cpp = self._translate(
      '''
from py2cpp import Self, immutable

class Trie:
  @immutable
  def copy(self) -> Self:
    out: Self = Self()
    return out
''',
      strict=False,
    )
    self.assertRegex(cpp, re.compile(r"Trie\s+out\s*=\s*Trie\(\)"))
    self.assertNotIn("Self()", cpp)

  def test_template_copy_new_uses_specialization(self):
    cpp = self._translate(
      '''
from py2cpp import Self, immutable, new

class Heap[T]:
  @immutable
  def copy(self) -> Self:
    out: Self = new()
    return out
'''
    )
    self.assertRegex(cpp, re.compile(r"Heap<T>\s+out\s*=\s*Heap<T>\(\)"))
    self.assertNotIn("Self()", cpp)


if __name__ == "__main__":
  unittest.main()
