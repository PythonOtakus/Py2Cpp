"""``protocol`` 静态虚方法 traits 探测与 strict_style 规则（Paw 表面）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import host.tree_nodes as ast

from host.codegen.protocol_traits_gen import (
  _sfinae_protocol_static_method_probe,
  protocol_traits_lines,
)
from host.frontend.api import parse_module
from host.passes.protocol import is_protocol_static_virtual_method
from host.translation_error import TranslationError
from host.translator import Translator
from compiler.py.mid.nodes import MidClass
from host.analysis.ir import ClassInfo


class ProtocolStaticVirtualProbeTests(unittest.TestCase):
  def test_static_parse_probe_uses_type_scope(self):
    line = _sfinae_protocol_static_method_probe(
      "parse",
      "Self",
      ("const PyStr&",),
    )
    self.assertIn("U::parse(std::declval<const PyStr&>())", line)
    self.assertIn("std::is_same<decltype", line)

  def test_static_template_method_probe_uses_template_keyword(self):
    line = _sfinae_protocol_static_method_probe(
      "alloc_array",
      "T*",
      ("PyInt",),
      method_type_params=("T",),
    )
    self.assertIn("U::template alloc_array<T>(std::declval<PyInt>())", line)

  def test_traits_lines_include_static_probe(self):
    lines = protocol_traits_lines(
      "IParsableType",
      [],
      static_method_specs=[("parse", "Self", ("const PyStr&",), ())],
    )
    text = "\n".join(lines)
    self.assertIn("IParsableType_check", text)
    self.assertIn("U::parse(std::declval<const PyStr&>())", text)


class ProtocolStaticVirtualStyleTests(unittest.TestCase):
  def _translate(self, body: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      paw = out / "mod.paw"
      paw.write_text(f"from paw import *\n\n{body}", encoding="utf-8")
      Translator.translate_file(
        str(paw),
        output_dir=str(out / "out"),
        include_stdlib=True,
        strict=True,
      )

  def _expect_strict_fail(self, body: str, rule: str, *, substring: str = "") -> None:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      paw = out / "mod.paw"
      paw.write_text(f"from paw import *\n\n{body}", encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(paw),
          output_dir=str(out / "out"),
          include_stdlib=True,
          strict=True,
        )
      msg = str(ctx.exception)
      self.assertIn(f"[{rule}]", msg)
      if substring:
        self.assertIn(substring, msg)

  def test_rejects_static_virtual_on_entity_class(self):
    src = """
class Bad:
  static virtual def f() -> int:
    return 0
"""
    self._expect_strict_fail(
      src,
      "S1003",
      substring="仅允许写在 ``@protocol``",
    )

  def test_allows_static_override_on_entity(self):
    src = """
class Widget:
  static override def parse(s: str) -> Self:
    return new("")

def main():
  pass
"""
    self._translate(src)

  def test_rejects_static_protocol_impl_without_override(self):
    src = """
protocol IParsableType:
  static abstract def parse(s: str) -> Self: ...

class Widget:
  static def parse(s: str) -> Self:
    return new(0)

def try_parse[T: IParsableType](s: str) -> T:
  return T.parse(s)

def main():
  w: Widget = try_parse[Widget]("1")
  return 0
"""
    self._expect_strict_fail(src, "S1002", substring="协议静态虚成员")

  def test_is_protocol_static_virtual_method(self):
    src = """
protocol P:
  static abstract def parse(s: str) -> int: ...
"""
    pm = parse_module(src, path="<test_static_virtual>.paw", use_cache=False)
    cls = next(
      i for i in pm.mid.items if isinstance(i, MidClass) and i.name == "P"
    )
    info = ClassInfo.from_mid_class(cls, "<test>")
    info.ensure_methods_bridged_from_mid()
    method = info.methods["parse"]
    self.assertIsInstance(method, ast.FunctionDef)
    self.assertTrue(is_protocol_static_virtual_method(method))


if __name__ == "__main__":
  unittest.main()
