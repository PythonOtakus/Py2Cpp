"""``new.方法(...)``：由注解/返回类型解析 ``Cls[T]::method``。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class NewReceiverStaticTests(unittest.TestCase):
  def _translate(self, src: str, *, strict: bool = True) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=strict,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      return text

  def test_ann_assign_new_open(self):
    cpp = self._translate(
      '''
from py2cpp import Self, dataclass, new

@dataclass
class Org:
  title: str = ""

class Doc[T]:
  @staticmethod
  def open(path: str, mode: str = "r") -> Self:
    out: Self = new()
    return out

def load_doc(path: str) -> None:
  doc: Doc[Org] = new.open(path, "r")
'''
    )
    self.assertRegex(cpp, re.compile(r"Doc<[^>]+>::open\("))
    self.assertNotIn("new.open", cpp)

  def test_return_new_open(self):
    cpp = self._translate(
      '''
from py2cpp import Self, dataclass, new

@dataclass
class Org:
  title: str = ""

class Doc[T]:
  @staticmethod
  def open(path: str, mode: str = "r") -> Self:
    out: Self = new()
    return out

def load_doc(path: str) -> Doc[Org]:
  return new.open(path, "r")
'''
    )
    self.assertRegex(cpp, re.compile(r"return .*Doc<[^>]+>::open\("))

  def test_strict_rejects_explicit_subscript_static(self):
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        '''
from py2cpp import Self, dataclass, new

@dataclass
class Org:
  title: str = ""

class Doc[T]:
  @staticmethod
  def open(path: str, mode: str = "r") -> Self:
    out: Self = new()
    return out

def load_doc(path: str) -> None:
  doc: Doc[Org] = Doc[Org].open(path, "r")
''',
        encoding="utf-8",
      )
      with self.assertRaises(Exception) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=False, strict=True,
        )
      self.assertIn("[S06b]", str(ctx.exception))
      self.assertIn("new.open", str(ctx.exception))

  def test_ann_assign_new_union_variant(self):
    cpp = self._translate(
      '''
from py2cpp import union, variant, new

@union
class Message:
  @variant
  class Quit:
    pass

  @variant
  class Move:
    x: int
    y: int

def make_quit() -> None:
  q: Message = new.Quit()
  m: Message = new.Move(1, 2)
''',
    )
    self.assertRegex(cpp, re.compile(r"Message::Quit\("))
    self.assertRegex(cpp, re.compile(r"Message::Move\("))
    self.assertNotIn("new.Quit", cpp)
    self.assertNotIn("new.Move", cpp)

  def test_strict_rejects_explicit_union_ctor(self):
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        '''
from py2cpp import union, variant, new

@union
class Message:
  @variant
  class Quit:
    pass

def make_quit() -> None:
  q: Message = Message.Quit()
''',
        encoding="utf-8",
      )
      with self.assertRaises(Exception) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=False, strict=True,
        )
      self.assertIn("[S06b]", str(ctx.exception))
      self.assertIn("new.Quit", str(ctx.exception))

  def test_strict_rejects_explicit_union_match(self):
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        '''
from py2cpp import union, variant, new

@union
class Message:
  @variant
  class Quit:
    pass

  @variant
  class Move:
    x: int
    y: int

def dispatch(msg: Message) -> int:
  match msg:
    case Message.Quit:
      return 0
    case Message.Move(x, y):
      return x + y
''',
        encoding="utf-8",
      )
      with self.assertRaises(Exception) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=False, strict=True,
        )
      self.assertIn("[S06b]", str(ctx.exception))
      self.assertIn("new.Quit", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
