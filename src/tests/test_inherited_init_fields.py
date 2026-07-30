"""子类 ``__init__`` 赋值基类字段时勿再声明 ``void*`` 遮蔽字段。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


def _class_body(header: str, name: str) -> str:
  """取 ``class Name … { … };`` 体（跳过 ``class Name;`` 前向声明）。"""
  m = re.search(
    rf"class {re.escape(name)}\s*(?::[^{{]+)?\s*\{{(.*?)\n  \}};",
    header,
    re.S,
  )
  if m is None:
    raise AssertionError(f"class {name} body not found")
  return m.group(1)


class InheritedInitFieldTests(unittest.TestCase):
  def test_subclass_init_assigns_base_str_field(self):
    src = """
from py2cpp import *

@refcount
class Base:
  kind: str = "Base"
  enabled: bool = True

@refcount
class Child(Base):
  extra: int = 0

  def __init__(self):
    self.kind = "Child"
    self.enabled = True
    self.extra = 1
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      header = Path(h_path).read_text(encoding="utf-8")
      self.assertIn("class Child", header)
      child_block = _class_body(header, "Child")
      self.assertNotIn("void* kind", child_block)
      self.assertNotIn("PyStr kind", child_block)
      self.assertNotIn("PyBool enabled", child_block)
      self.assertIn("PyInt extra", child_block)
      inl = cpp_path.with_suffix(".inl")
      text = cpp_path.read_text(encoding="utf-8")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      self.assertIn('PyStr("Child")', text.replace(" ", ""))

  def test_subclass_new_inherited_refcount_field(self):
    """子类 ``__init__`` 对基类字段 ``self.f = new(...)`` 须沿 MRO 取类型。"""
    src = """
from py2cpp import *

@refcount
class Inner:
  def __init__(self, tag: str = "x"):
    self.tag: str = tag

@refcount
class Base:
  space: Inner = new("base")

  def __init__(self):
    self.space = new("base")

@refcount
class Child(Base):
  def __init__(self):
    self.space = new("child")
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      header = Path(h_path).read_text(encoding="utf-8")
      child_block = _class_body(header, "Child")
      self.assertNotIn("space", child_block)
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      self.assertIn("makeRefCount", text)
      self.assertIn("child", text)

  def test_mixin_method_fields_do_not_drop_host_typed_fields(self):
    """mixin 方法体 ``self.x = …`` 不得导致宿主带注解字段被当作遮蔽删掉。"""
    src = """
from py2cpp import *

@mixin
class HostMixin:
  def reset(self):
    self.buf = new(4)

@refcount
class Host(HostMixin):
  def __init__(self):
    self.buf: int[:] = new(4)

  def grow(self):
    self.buf = new(8)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      header = Path(h_path).read_text(encoding="utf-8")
      host_block = _class_body(header, "Host")
      self.assertNotIn("void* buf", host_block)
      self.assertIn("buf", host_block)
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      self.assertIn("new", text)


if __name__ == "__main__":
  unittest.main()
