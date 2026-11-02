"""成员 ``attr()``：仅方法或可调用类型字段/属性合法。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator
from src.translation_error import TranslationError


class MemberCallValidationTests(unittest.TestCase):
  def test_staticproperty_empty_call_rejected(self):
    src = """
from py2cpp import copyable, Self, int64

@copyable
class Task:
  @staticproperty
  def period_count() -> int64:
    return 0

def use() -> int64:
  return Task.period_count()
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises((NotImplementedError, TranslationError)) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=False, strict=False,
        )
      self.assertIn("@staticproperty", str(ctx.exception))
      self.assertIn("Task.period_count", str(ctx.exception))

  def test_staticproperty_attr_read_ok(self):
    src = """
from py2cpp import copyable, int64

@copyable
class Task:
  @staticproperty
  def period_count() -> int64:
    return 0

def use() -> int64:
  return Task.period_count
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("period_count__get()", cpp)
      self.assertNotIn("period_count()", cpp.replace("period_count__get()", ""))

  def test_instance_property_empty_call_rejected(self):
    src = """
from py2cpp import copyable, Self

@copyable
class Node:
  @property
  def parent(self) -> Self:
    return self

def use(n: Node) -> Node:
  return n.parent()
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises((NotImplementedError, TranslationError)) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=False, strict=False,
        )
      self.assertIn("@property", str(ctx.exception))
      self.assertIn("n.parent()", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
