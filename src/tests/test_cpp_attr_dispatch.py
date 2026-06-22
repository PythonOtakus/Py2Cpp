"""无法绑定 ``ClassInfo`` 时 ``obj.attr`` / ``obj.m()`` → ``PY2CPP_GETATTR`` / ``CALL``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.codegen.expand_py2cpp_template import expand_template
from src.translator import Translator


class CppAttrDispatchTests(unittest.TestCase):
  def test_unannotated_param_uses_py2cpp_getattr(self):
    src = """
from py2cpp import copyable, new

@copyable
class Node:
  @property
  def parent(self) -> int:
    return 1

def read_any(node) -> int:
  return node.parent

def write_any(node) -> None:
  node.parent = 2
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("PY2CPP_DECLARE_GETATTR(parent)", cpp)
      self.assertIn("PY2CPP_GETATTR", cpp)
      self.assertIn("PY2CPP_SETATTR", cpp)
      self.assertIn("#line", cpp)
      self.assertNotIn("PY2CPP_GETATTR_FAIL_MSG", cpp)
      self.assertNotIn("PY2CPP_SETATTR_FAIL_MSG", cpp)
      self.assertNotIn("PY2CPP_CALL_FAIL_MSG", cpp)
      read_any = cpp.split("read_any", 1)[1]
      self.assertIn("#line", read_any)
      self.assertNotIn("PY2CPP_GETATTR_FAIL_MSG", read_any)
      self.assertIn("PY2CPP_GETATTR", read_any)
      self.assertNotRegex(cpp.replace(" ", ""), r"node\.parent[^(]")

  def test_unannotated_param_method_uses_py2cpp_call(self):
    src = """
from py2cpp import copyable

@copyable
class Box:
  def bump(self) -> int:
    return 1

def call_any(box) -> int:
  return box.bump()
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("PY2CPP_DECLARE_CALL(bump)", cpp)
      self.assertIn("PY2CPP_CALL", cpp)
      self.assertNotIn("box.bump", cpp.replace(" ", ""))

  def test_template_param_only_not_plain_untyped_local(self):
    src = """
from py2cpp import copyable

@copyable
class Box:
  x: int = 0

def read_box(box: Box) -> int:
  return box.x

def f() -> int:
  box: Box = Box()
  return read_box(box)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("box.x", cpp.replace(" ", ""))
      self.assertNotIn("PY2CPP_GETATTR", cpp)

  def test_typed_param_still_uses_getter_call(self):
    src = """
from py2cpp import copyable, new

@copyable
class Node:
  @property
  def parent(self) -> int:
    return 1

def read_typed(node: Node) -> int:
  return node.parent
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8").replace(" ", "")
      self.assertIn("node.get_parent()", cpp)
      self.assertNotIn("PY2CPP_GETATTR", cpp)

  def test_member_access_header_static_assert_fallback(self):
    h = expand_template(
      "member_access.h",
      {"source_note": "test", "guard": "PY2CPP_MEMBER_ACCESS_TEST", "generated_at": "now"},
      apply_allman=False,
    )
    self.assertIn("access_dependent_false", h)
    self.assertIn("access_is_raw_pointer", h)
    self.assertIn("can_get_##attr", h)
    self.assertIn("__py2cpp_get_##attr##_no_match", h)
    self.assertIn("py2cpp_invoke_get_##attr", h)
    self.assertIn("can_set_##attr", h)
    self.assertIn("py2cpp_invoke_set_##attr", h)
    self.assertIn("can_call0_##method", h)
    self.assertIn("py2cpp_invoke_call_##method", h)
    self.assertNotIn("py2cpp_set_##attr##_fail", h)
    self.assertNotIn("py2cpp_call_##method##_fail", h)
    self.assertIn("py2cpp_get_##attr##_detect_int_val", h)
    self.assertIn("py2cpp_get_##attr##_detect_int_ptr", h)
    self.assertIn("pick_ptr", h)

  def test_unannotated_pointer_param_uses_py2cpp_getattr(self):
    src = """
from py2cpp import Pointer, copyable, new

@copyable
class Node:
  @property
  def parent(self) -> int:
    return 1

def read_ptr(node) -> int:
  return node.parent

def use(p: Pointer[Node]) -> int:
  return read_ptr(p)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("PY2CPP_GETATTR", cpp)
      self.assertIn("read_ptr", cpp)

  def test_chained_pointer_field_uses_arrow(self):
    src = """
from py2cpp import Pointer, Self, boxing

@boxing
class Link:
  next: Pointer[Self]
  prev: Pointer[Self]

def wire(cur: Pointer[Link], node: Pointer[Link]) -> None:
  cur.prev.next = node
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8").replace(" ", "")
      self.assertIn("cur->prev->next=", cpp)
      self.assertNotIn("cur->prev.next=", cpp)
