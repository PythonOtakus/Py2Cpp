"""``check_template_conventions`` / ``collect_template_violations`` 单测。"""
from __future__ import annotations

import unittest

from src.codegen.template_conventions import (
  ViolationSeverity,
  check_template_conventions,
  clear_template_violations_cache,
  collect_template_violations,
)
from src.codegen.expand_py2cpp_template import (
  collect_forbidden_dynamic_type_violations,
  collect_forbidden_stl_container_violations,
  collect_forbidden_type_eval_violations,
  expand_template,
  template_root,
)
from src.constant.template_module_bindings import validate_template_module_bindings


class TemplateConventionsTests(unittest.TestCase):
  def test_current_templates_pass(self):
    clear_template_violations_cache()
    errors = [
      v for v in collect_template_violations()
      if v.severity == ViolationSeverity.ERROR
    ]
    self.assertEqual(errors, [])

  def test_validate_module_bindings(self):
    validate_template_module_bindings()

  def test_forbidden_helpers_empty(self):
    clear_template_violations_cache()
    self.assertEqual(collect_forbidden_type_eval_violations(), [])
    self.assertEqual(collect_forbidden_stl_container_violations(), [])
    self.assertEqual(collect_forbidden_dynamic_type_violations(), [])

  def test_inject_include_outside_ignore_detected(self):
    from src.codegen.template_scan import scan_inject_ignore_violations

    lines = ['#include "py2cpp/util/memory.h"\n']
    hits = scan_inject_ignore_violations(
      lines,
      check_py2cpp_include=True,
      check_ctx_define=True,
    )
    self.assertEqual(len(hits), 1)
    self.assertIn("PY2CPP_IGNORE", hits[0][1])

  def test_paste_inject_rel_matches_plus_inl(self):
    from src.codegen.template_conventions import _is_paste_inject_rel

    self.assertTrue(_is_paste_inject_rel("text/+str.inl"))
    self.assertTrue(_is_paste_inject_rel("io/-file.inl"))
    self.assertFalse(_is_paste_inject_rel("~test/~snippet.inl"))

  def test_no_strict_skips_check(self):
    check_template_conventions(strict=False)

  def test_t23_rejects_pragma_once(self):
    from src.codegen.template_scan import scan_include_guard_violations

    hits = scan_include_guard_violations(["#pragma once\n"])
    self.assertEqual(len(hits), 1)
    self.assertIn("pragma once", hits[0][1].lower())

  def test_t24_rejects_qualified_cut_type(self):
    from src.codegen.template_scan import partition_ignore_regions, scan_qualified_cut_type_violations

    lines = ["py2cpp::core::iter_result::PyIterResult<A,B> fn();\n"]
    hits = scan_qualified_cut_type_violations(
      lines,
      ignore_regions=partition_ignore_regions(lines),
    )
    self.assertEqual(len(hits), 1)
    self.assertIn("PY2CPP_TYPE", hits[0][1])

  def test_t25_rejects_bad_ctx_key_naming(self):
    from src.codegen.template_scan import scan_ctx_key_naming_violations

    lines = ["PY2CPP_ECHO(ctx_make_fn)();\n"]
    hits = scan_ctx_key_naming_violations(lines)
    self.assertEqual(len(hits), 1)
    self.assertIn("PascalCase", hits[0][1])

  def test_t25_rejects_echo_without_ignore_define(self):
    from src.codegen.template_scan import partition_ignore_regions, scan_ctx_ignore_echo_set_violations

    lines = ["PY2CPP_ECHO(ctx_Foo)();\n"]
    hits = scan_ctx_ignore_echo_set_violations(
      lines,
      ignore_regions=partition_ignore_regions(lines),
    )
    self.assertEqual(len(hits), 1)
    self.assertIn("#define ctx_Foo", hits[0][1])

  def test_t25_rejects_orphan_ignore_define(self):
    from src.codegen.template_scan import partition_ignore_regions, scan_ctx_ignore_echo_set_violations

    lines = [
      "PY2CPP_IGNORE\n",
      "#define ctx_Unused Bar\n",
      "PY2CPP_END\n",
    ]
    hits = scan_ctx_ignore_echo_set_violations(
      lines,
      ignore_regions=partition_ignore_regions(lines),
    )
    self.assertEqual(len(hits), 1)
    self.assertIn("ctx_Unused", hits[0][1])
    self.assertIn("PY2CPP_ECHO", hits[0][1])

  def test_t25_accepts_ignore_define_and_echo(self):
    from src.codegen.template_scan import partition_ignore_regions, scan_ctx_ignore_echo_set_violations

    lines = [
      "PY2CPP_IGNORE\n",
      "#define ctx_Foo Bar\n",
      "PY2CPP_END\n",
      "PY2CPP_ECHO(ctx_Foo)();\n",
    ]
    hits = scan_ctx_ignore_echo_set_violations(
      lines,
      ignore_regions=partition_ignore_regions(lines),
    )
    self.assertEqual(hits, [])

  def test_t26_rejects_ab_system_include(self):
    from src.codegen.template_conventions import _scan_file_content

    text = '#include <stdio.h>\n#include <cstdint>\n#include <cmath>\n#include "ffi/crt/stdio.h"\n'
    hits = [
      v for v in _scan_file_content("probe.inl", text, template_root())
      if v.rule == "T26"
    ]
    self.assertEqual(len(hits), 1)
    self.assertIn("stdio.h", hits[0].message)

  def test_t26_rejects_c_stdint_not_cstdint(self):
    from src.codegen.template_conventions import _scan_file_content

    text = "#include <stdint.h>\n"
    hits = [
      v for v in _scan_file_content("probe.inl", text, template_root())
      if v.rule == "T26"
    ]
    self.assertEqual(len(hits), 1)
    self.assertIn("stdint.h", hits[0].message)

  def test_orphan_tilde_is_warning_not_error(self):
    clear_template_violations_cache()
    warnings = [
      v for v in collect_template_violations()
      if v.severity == ViolationSeverity.WARNING
    ]
    if not warnings:
      self.skipTest("当前 templates 树无孤立 ~ 警告")
    rules = {v.rule for v in warnings}
    self.assertIn("T6", rules)

  def test_t22_rejects_inject_without_class_shell(self):
    from src.codegen.template_scan import scan_inject_class_shell_violations

    lines = [
      "PY2CPP_IGNORE\n",
      '#include "py2cpp/io/file.h"\n',
      "namespace py2cpp { namespace io { namespace file {\n",
      "PY2CPP_END\n",
      "\n",
      "PY2CPP_INJECT_CLASS(PyScandirIterator)\n",
      "  void foo();\n",
      "PY2CPP_END\n",
    ]
    hits = scan_inject_class_shell_violations(lines)
    self.assertTrue(any("class PyScandirIterator" in msg for _, msg in hits))

  def test_t22_rejects_class_name_mismatch(self):
    from src.codegen.template_scan import scan_inject_class_shell_violations

    lines = [
      "PY2CPP_IGNORE\n",
      '#include "py2cpp/io/file.h"\n',
      "namespace py2cpp { namespace io { namespace file {\n",
      "class Foo {\n",
      "PY2CPP_END\n",
      "\n",
      "PY2CPP_INJECT_CLASS(ScandirIterator)\n",
      "  void foo();\n",
      "PY2CPP_END\n",
      "\n",
      "PY2CPP_IGNORE\n",
      "};\n",
      "PY2CPP_END\n",
    ]
    hits = scan_inject_class_shell_violations(lines)
    self.assertTrue(any("不一致" in msg for _, msg in hits))

  def test_t22_accepts_valid_shell(self):
    from src.codegen.template_scan import scan_inject_class_shell_violations

    lines = [
      "PY2CPP_IGNORE\n",
      '#include "py2cpp/io/file.h"\n',
      "namespace py2cpp { namespace io { namespace file {\n",
      "class ScandirIterator {\n",
      "PY2CPP_END\n",
      "\n",
      "PY2CPP_INJECT_CLASS(ScandirIterator)\n",
      "  void foo();\n",
      "PY2CPP_END\n",
      "\n",
      "PY2CPP_IGNORE\n",
      "};\n",
      "PY2CPP_END\n",
    ]
    hits = scan_inject_class_shell_violations(lines)
    self.assertEqual(hits, [])

  def test_t22_accepts_multiple_inject_same_shell(self):
    from src.codegen.template_scan import scan_inject_class_shell_violations

    lines = [
      "PY2CPP_IGNORE\n",
      '#include "py2cpp/text/str.h"\n',
      "namespace py2cpp { namespace text { namespace str {\n",
      "class PyStr {\n",
      "PY2CPP_END\n",
      "\n",
      "PY2CPP_INJECT_CLASS(PyStr)\n",
      "  PyStr(int x);\n",
      "PY2CPP_END\n",
      "\n",
      "PY2CPP_INJECT_CLASS(PyStr)\n",
      "  void bar();\n",
      "PY2CPP_END\n",
      "\n",
      "PY2CPP_IGNORE\n",
      "};\n",
      "PY2CPP_END\n",
    ]
    hits = scan_inject_class_shell_violations(lines)
    self.assertEqual(hits, [])

  def test_expand_still_checks_forbidden_stl(self):
    bad_rel = "~test/~forbidden_stl_smoke.inl"
    bad_path = template_root() / bad_rel
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    try:
      bad_path.write_text("#include <vector>\n", encoding="utf-8")
      with self.assertRaises(ValueError) as ctx:
        expand_template(bad_rel, apply_allman=False)
      self.assertIn("STL 容器", str(ctx.exception))
    finally:
      if bad_path.is_file():
        bad_path.unlink()


if __name__ == "__main__":
  unittest.main()
