"""协议运行时擦除表与 ``makeGenerator`` 命名。"""
import ast
import unittest

from src.analysis.ir import cpp_make_generator_expr
from src.analysis.stubs.protocol_erase_stubs import (
  PROTOCOL_ERASE_ALWAYS,
  annotation_uses_self,
  erased_protocol_make_fn,
  load_protocol_runtime_erase,
)


class ProtocolEraseStubTests(unittest.TestCase):
  def test_self_detection(self):
    ann = ast.parse("list[Self]").body[0].value
    self.assertTrue(annotation_uses_self(ann))
    self.assertFalse(annotation_uses_self(ast.parse("Iterator[T]").body[0].value))

  def test_runtime_erase_includes_generator_not_comparable(self):
    rt = load_protocol_runtime_erase()
    self.assertIn("Generator", rt)
    self.assertIn("AsyncGenerator", rt)
    self.assertIn("ContextManager", rt)
    self.assertIn("Sized", rt)
    self.assertNotIn("Comparable", rt)
    self.assertNotIn("Equatable", rt)

  def test_make_generator_rename(self):
    self.assertEqual(erased_protocol_make_fn("Generator"), "makeGenerator")
    expr = cpp_make_generator_expr(
      "PyGenerator<PyInt, PyNone, PyNone>",
      "gen_pair_generator()",
    )
    self.assertEqual(
      expr,
      "makeGenerator<PyInt, PyNone, PyNone>(gen_pair_generator())",
    )

  def test_always_handwritten(self):
    self.assertEqual(
      PROTOCOL_ERASE_ALWAYS,
      frozenset({"Generator", "Coroutine", "AsyncGenerator"}),
    )

  def test_element_alias_maps_to_type_param(self):
    from src.analysis.stubs.protocol_erase_stubs import (
      _protocol_ann_to_cpp,
      load_protocol_runtime_erase_candidates,
    )

    import ast

    candidates = load_protocol_runtime_erase_candidates()
    aliases = {"Element": ast.Constant(value=Ellipsis)}
    cpp = _protocol_ann_to_cpp(
      ast.Name(id="Element"), ("T",), aliases, runtime_erase=candidates,
    )
    self.assertEqual(cpp, "T")

  def test_varint_maps_to_fqn(self):
    from src.analysis.stubs.protocol_erase_stubs import (
      _protocol_ann_to_cpp,
      load_protocol_runtime_erase_candidates,
    )

    candidates = load_protocol_runtime_erase_candidates()
    ann = ast.parse("varint").body[0].value
    cpp = _protocol_ann_to_cpp(ann, (), {}, runtime_erase=candidates)
    self.assertEqual(cpp, "py2cpp::numeric::varint::PyVarInt")
    ann2 = ast.parse("list[varint]").body[0].value
    cpp2 = _protocol_ann_to_cpp(ann2, (), {}, runtime_erase=candidates)
    self.assertEqual(
      cpp2,
      "PyList<py2cpp::numeric::varint::PyVarInt>",
    )

  def test_domain_protocol_erase_specs(self):
    from src.analysis.stubs.protocol_erase_stubs import load_protocol_erase_specs

    names = {s.name for s in load_protocol_erase_specs()}
    self.assertIn("Encoder", names)
    self.assertIn("Connection", names)
    self.assertIn("Navigatable", names)
    self.assertIn("Container", names)
    self.assertNotIn("TextIO", names)


if __name__ == "__main__":
  unittest.main()
