"""``protocol_erase_gen`` 模板展开 smoke。"""
import unittest

from src.analysis.stubs.protocol_erase_stubs import protocol_erase_specs_for_header
from src.codegen.protocol_erase_gen import _render_spec, protocol_erase_header_lines


class ProtocolEraseGenTests(unittest.TestCase):
  def test_render_spec_no_unexpanded_macros(self):
    specs = protocol_erase_specs_for_header(late=False)
    self.assertTrue(specs)
    for spec in specs:
      text = _render_spec(spec)
      self.assertNotIn("PY2CPP_ECHO", text)
      self.assertNotIn("PY2CPP_INLINE_ECHO", text)
      self.assertNotIn("PY2CPP_DYNAMIC_TYPE", text)
      self.assertNotIn("PY2CPP_BEGIN", text)
      self.assertNotIn("PY2CPP_EVAL", text)

  def test_iterator_iter_returns_this(self):
    specs = {s.name: s for s in protocol_erase_specs_for_header(late=False)}
    text = _render_spec(specs["Iterator"])
    self.assertIn("PyIterator<T>& __iter__()", text)
    self.assertIn("return *this;", text)
    self.assertNotIn("_fn___iter__", text)

  def test_iterable_iter_uses_make_iterator(self):
    specs = {s.name: s for s in protocol_erase_specs_for_header(late=False)}
    text = _render_spec(specs["Iterable"])
    self.assertIn("return makeIterator<T>(self->impl->__iter__());", text)

  def test_header_includes_preamble_and_guard(self):
    lines = protocol_erase_header_lines(generated_at="2099-01-01 00:00:00")
    text = "\n".join(lines)
    self.assertIn("#ifndef PY2CPP_PROTOCOL_ERASE_H", text)
    self.assertIn("py2cpp_protocol_erase_detail::model_hdr", text)
    self.assertIn("makeContextManager", text)


if __name__ == "__main__":
  unittest.main()
