"""``@protocol`` 静态虚方法 traits 探测与 strict_style 规则。"""
import ast
import tempfile
import unittest
from pathlib import Path

from src.codegen.protocol_traits_gen import (
  _sfinae_protocol_static_method_probe,
  protocol_traits_lines,
)
from src.passes.protocol import is_protocol_static_virtual_method
from src.translation_error import TranslationError
from src.translator import Translator


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
      "IParsable",
      [],
      static_method_specs=[("parse", "Self", ("const PyStr&",), ())],
    )
    text = "\n".join(lines)
    self.assertIn("IParsable_check", text)
    self.assertIn("U::parse(std::declval<const PyStr&>())", text)


class ProtocolStaticVirtualStyleTests(unittest.TestCase):
  def _translate(self, body: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      Translator.translate_file(
        str(py),
        output_dir=str(out / "generated"),
        include_stdlib=True,
        strict=True,
      )

  def _expect_strict_fail(self, body: str, rule: str, *, substring: str = "") -> None:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(out / "generated"),
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
  @staticmethod
  @virtual
  def f() -> int:
    return 0
"""
    self._expect_strict_fail(
      src,
      "S39",
      substring="仅允许写在 ``@protocol``",
    )

  def test_allows_static_override_on_entity(self):
    src = """
class Widget:
  @staticmethod
  @override
  def parse(s: str) -> Self:
    return new("")

def main():
  pass
"""
    self._translate(src)

  def test_rejects_static_protocol_impl_without_override(self):
    src = """
@protocol
class IParsable:
  @staticmethod
  @abstract
  def parse(s: str) -> Self: ...

class Widget:
  @staticmethod
  def parse(s: str) -> Self:
    return new(0)

def try_parse[T: IParsable](s: str) -> T:
  return T.parse(s)

def main():
  w: Widget = try_parse[Widget]("1")
  return 0
"""
    self._expect_strict_fail(src, "S18", substring="协议静态虚成员")

  def test_is_protocol_static_virtual_method(self):
    node = ast.parse(
      """
class P:
  @staticmethod
  @abstract
  def parse(s: str) -> int: ...
""",
    ).body[0]
    assert isinstance(node, ast.ClassDef)
    method = node.body[0]
    assert isinstance(method, ast.FunctionDef)
    self.assertTrue(is_protocol_static_virtual_method(method))


if __name__ == "__main__":
  unittest.main()
