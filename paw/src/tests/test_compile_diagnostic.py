"""编译期诊断文案与翻译期 ``翻译失败:`` 对称。"""
from __future__ import annotations

import unittest

from src.emit.compile_diagnostic_emit import (
  COMPILE_DIAG_PREFIX,
  compile_diag_descriptor_protocol,
  compile_diag_protocol_unsatisfied,
  compile_diag_type_param_protocol,
)
from src.codegen.expand_py2cpp_template import expand_template


class CompileDiagnosticTests(unittest.TestCase):
  def test_prefix_matches_translation_style(self):
    self.assertEqual(COMPILE_DIAG_PREFIX, "编译期")

  def test_type_param_protocol_message(self):
    msg = compile_diag_type_param_protocol("K", "DictKeyType")
    self.assertTrue(msg.startswith("编译期:"))
    self.assertIn("类型参数 K", msg)
    self.assertIn("@protocol DictKeyType", msg)

  def test_protocol_verify_message(self):
    msg = compile_diag_protocol_unsatisfied("ComparableType")
    self.assertIn("类型 T 不满足", msg)
    self.assertIn("@protocol ComparableType", msg)

  def test_descriptor_protocol_message(self):
    msg = compile_diag_descriptor_protocol("PyInt", "ComparableType")
    self.assertIn("描述符值类型 PyInt", msg)
    self.assertIn("@protocol ComparableType", msg)

  def test_type_param_protocol_message_with_location(self):
    from src.emit.compile_diagnostic_emit import compile_diag_location_prefix

    loc = compile_diag_location_prefix("test/foo.py", 12)
    msg = compile_diag_type_param_protocol("K", "DictKeyType", loc_prefix=loc)
    self.assertTrue(msg.startswith("test/foo.py:12:"))
    self.assertIn("编译期:", msg)

  def test_member_access_header_no_fail_msg_macros(self):
    h = expand_template(
      "member_access.h",
      {"source_note": "t", "guard": "GUARD", "generated_at": "now"},
      apply_allman=False,
    )
    self.assertNotIn("PY2CPP_GETATTR_FAIL_MSG", h)
    self.assertNotIn("PY2CPP_SETATTR_FAIL_MSG", h)
    self.assertNotIn("PY2CPP_CALL_FAIL_MSG", h)
    self.assertNotIn("__PY2CPP_GETATTR_DIAG_SUFFIX", h)
    self.assertNotIn("__PY2CPP_SETATTR_DIAG_SUFFIX", h)
    self.assertNotIn("__PY2CPP_CALL_DIAG_SUFFIX", h)
    self.assertIn("can_get_##attr", h)
    self.assertIn("py2cpp_invoke_get_##attr", h)
    self.assertNotIn("py2cpp_get_##attr##_fail", h)
    self.assertNotIn("py2cpp_set_##attr##_fail", h)
    self.assertNotIn("py2cpp_call_##method##_fail", h)
    self.assertIn("PY2CPP_GETATTR", h)
    self.assertIn("PY2CPP_SETATTR", h)
    self.assertIn("PY2CPP_CALL", h)
    self.assertNotIn("not found", h)
    self.assertNotIn("/->", h)

  def test_py2cpp_getattr_message_includes_location(self):
    from src.emit.compile_diagnostic_emit import compile_diag_py2cpp_getattr

    msg = compile_diag_py2cpp_getattr("missing", loc_prefix="test/fail/x.py:12: ")
    self.assertTrue(msg.startswith("test/fail/x.py:12:"))
    self.assertIn("PY2CPP_GETATTR", msg)
    self.assertIn("missing", msg)

  def test_utf8_literal_roundtrip(self):
    from src.emit.compile_diagnostic_emit import (
      compile_diag_c_utf8_literal,
      compile_diag_py2cpp_getattr,
    )

    msg = compile_diag_py2cpp_getattr("missing", loc_prefix="test/x.py:12: ")
    import re

    lit = compile_diag_c_utf8_literal(msg)
    decoded = bytes(
      int(h, 16) for h in re.findall(r"\\x([0-9a-f]{2})", lit)
    ).decode("utf-8")
    self.assertEqual(decoded, msg)
    self.assertIn("编译期", decoded)
    self.assertIn("missing", decoded)

  def test_getattr_fail_hint_text(self):
    from src.emit.compile_diagnostic_emit import compile_diag_py2cpp_getattr_fail_hint

    hint = compile_diag_py2cpp_getattr_fail_hint()
    self.assertIn("get_<成员>()", hint)
    self.assertNotIn("/->", hint)


if __name__ == "__main__":
  unittest.main()
