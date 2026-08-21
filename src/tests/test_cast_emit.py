"""``cast[T](obj)`` / ``cast(obj)`` → ``static_cast`` emit。"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from src.analysis.ir import ClassInfo
from src.emit.call_emit import _emit_cast_call
from src.translator import Scope, Translator


class CastEmitTests(unittest.TestCase):
  def test_cast_ref_downcast(self):
    cls_src = """
@refcount
class Base:
  pass
"""
    tr = Translator("test/mod", "test/mod.py")
    from src.analysis.analyzer import TypeParser

    tr.type_parser = TypeParser()
    base_cls = ast.parse(cls_src).body[0]
    assert isinstance(base_cls, ast.ClassDef)
    info = ClassInfo(base_cls, "test/mod")
    tr.classes["Base"] = info
    tr.classes["Derived"] = info  # same cpp for smoke; only checks & form

    node = ast.parse("cast[Derived](b)", mode="eval").body
    assert isinstance(node, ast.Call)
    target = tr._parse_type(ast.Name(id="Derived"), set())
    tr.scope = Scope(ast.parse("pass").body[0])
    tr.scope.param_types = {"b": "Base&"}
    out = _emit_cast_call(tr, target, node)
    self.assertEqual(out, "static_cast<PyDerived>(b)")

  def test_cast_int64_to_pointer(self):
    tr = Translator("test/mod", "test/mod.py")
    from src.analysis.analyzer import TypeParser

    tr.type_parser = TypeParser()
    node = ast.parse("cast[Pointer[byte]](handle)", mode="eval").body
    assert isinstance(node, ast.Call)
    target = tr._parse_type(ast.Subscript(value=ast.Name(id="Pointer"), slice=ast.Name(id="byte")), set())
    tr.scope = Scope(ast.parse("pass").body[0])
    tr.scope.param_types = {"handle": "PyInt64"}
    out = _emit_cast_call(tr, target, node)
    self.assertEqual(out, "reinterpret_cast<PyByte*>(handle)")

  def test_overload_match_strips_const_list_reference(self):
    tr = Translator("test/mod", "test/mod.py")
    score = tr._overload_param_match_score(
      "const PyList<PyStr>&", "PyList<PyStr>",
    )
    self.assertEqual(score, 100)

  def test_cast_cstr_to_uintptr(self):
    tr = Translator("test/mod", "test/mod.py")
    from src.analysis.analyzer import TypeParser

    tr.type_parser = TypeParser()
    node = ast.parse("cast[uintptr](text)", mode="eval").body
    assert isinstance(node, ast.Call)
    target = tr._parse_type(ast.Name(id="uintptr"), set())
    tr.scope = Scope(ast.parse("pass").body[0])
    tr._infer_expr_cpp_type = lambda _node: "PyUtf8Ptr"
    out = _emit_cast_call(tr, target, node)
    self.assertEqual(out, "reinterpret_cast<PyUIntPtr>(text)")

  def test_cast_uint16_pointer_to_cwstr(self):
    tr = Translator("test/mod", "test/mod.py")
    from src.analysis.analyzer import TypeParser

    tr.type_parser = TypeParser()
    node = ast.parse("cast[utf16ptr](text)", mode="eval").body
    assert isinstance(node, ast.Call)
    target = tr._parse_type(ast.Name(id="utf16ptr"), set())
    tr.scope = Scope(ast.parse("pass").body[0])
    tr._infer_expr_cpp_type = lambda _node: "PyUInt16*"
    out = _emit_cast_call(tr, target, node)
    self.assertEqual(out, "reinterpret_cast<PyUtf16Ptr>(text)")
  def test_cast_deduced_from_ann_assign(self):
    src = """
from py2cpp import *

@refcount
class Base:
  pass

@refcount
class Derived(Base):
  pass

def narrow(slot: Base) -> None:
  d: Derived @ref = cast(slot)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("static_cast<PyDerived&>(*slot)", cpp)


if __name__ == "__main__":
  unittest.main()
