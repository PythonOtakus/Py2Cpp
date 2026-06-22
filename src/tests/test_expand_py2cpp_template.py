"""``expand_py2cpp_template`` 七宏展开单测。"""
from __future__ import annotations

import unittest

from src.codegen.expand_py2cpp_template import expand_template
from src.codegen.inject_template_emit import expanded_inject_template
from src.codegen.stdlib_mirror_codegen import expand_whole_file_template

_SHOWCASE_REL = "~test/~syntax_showcase.inl"
_SHOWCASE_CTX: dict[str, object] = {
  "module_rel": "util/memory",
  "typ": 1,
  "n": "count",
  "items": ("a", "b"),
  "parts": ["line_a;", "line_b;"],
  "tags": ("alpha", "beta"),
  "type_names": ["ValueError", "KeyError"],
  "a": "foo",
  "b": "bar",
  "ctx_Block": "block_a;\nblock_b;",
  "ctx_Suffix": ", y(1)",
  "ctx_Base": "PySized",
  "ctx_Name": "ValueError",
}


def _expand_showcase(**ctx_overrides: object) -> str:
  ctx = dict(_SHOWCASE_CTX)
  ctx.update(ctx_overrides)
  return expand_template(_SHOWCASE_REL, ctx, apply_allman=False)


class ExpandPy2CppTemplateTests(unittest.TestCase):
  def test_memory_inject_template(self):
    impl = expanded_inject_template("util/+memory.inl")
    self.assertIn("copy_buf(PyChar* dst", impl)
    self.assertIn("load_u64_le_bytes(PyByte* p", impl)
    self.assertIn("namespace py2cpp", impl)

  def test_bytes_inject_template(self):
    impl = expanded_inject_template("text/+bytes.inl")
    self.assertIn("bytes_from_literal", impl)
    self.assertIn("PyArray<PyByte> buf(n)", impl)
    self.assertNotIn("#include \"py2cpp/text/bytes.h\"", impl)

  def test_ignore_region_stripped_before_expand(self):
    impl = expanded_inject_template("text/+bytes.inl")
    self.assertNotIn("PY2CPP_IGNORE", impl)
    self.assertNotIn("PY2CPP_END", impl)

  def test_scope_from_template_path(self):
    impl = expanded_inject_template("text/+bytes.inl")
    self.assertIn("namespace py2cpp", impl)
    self.assertIn("namespace text", impl)
    self.assertIn("namespace bytes", impl)
    self.assertIn("} // namespace bytes", impl)
    self.assertNotIn("PY2CPP_BEGIN_SCOPE", impl)
    self.assertNotIn("PY2CPP_END_SCOPE", impl)

  def test_scope_explicit_override(self):
    out = expand_template(
      "text/+bytes.inl",
      {"module_rel": "util/memory"},
      apply_allman=False,
    )
    self.assertIn("namespace util", out)
    self.assertIn("namespace memory", out)
    self.assertNotIn("namespace text", out)

  def test_paste_short_form_sqlite(self):
    impl = expanded_inject_template("sql/+sqlite.inl")
    self.assertIn("PySqliteConnection connect(const PyStr& path)", impl)
    self.assertIn("PySqliteCursor::~PySqliteCursor()", impl)
    self.assertNotIn("PY2CPP_NAMESPACE", impl)
    self.assertNotIn("py2cpp::sql::sqlite::connect", impl)

  def test_paste_short_form_paste_before(self):
    out = expand_template("system/-time.inl", apply_allman=False)
    self.assertIn("PyFloat64 py_time()", out)
    self.assertNotIn("PY2CPP_NAMESPACE", out)

  def test_paste_short_form_class_paste(self):
    out = expand_template("text/+str.inl", apply_allman=False)
    self.assertIn("PyStr PyStr::from_buf", out)
    self.assertIn("PyStr::PyStr(PyArray<PyChar>&& data)", out)
    self.assertIn("_str_unescape_braces", out)
    self.assertNotIn("PY2CPP_NAMESPACE", out)

  def test_operators_codegen_inject_template(self):
    h = expand_whole_file_template(
      "operators.h",
      "2026-01-01",
      {"source_note": "test", "guard": "TEST_OPERATORS_H"},
      apply_allman=False,
    )
    self.assertIn("__truediv__(PyInt a, PyInt b)", h)
    self.assertIn("py2cpp::text::str::PyStr", h)
    self.assertIn("__mod__(PyInt64 a, PyInt64 b)", h)
    self.assertIn("chr(PyInt i)", h)
    self.assertIn("#ifndef TEST_OPERATORS_H", h)
    self.assertIn("#endif // TEST_OPERATORS_H", h)
    self.assertNotIn("PY2CPP_NAMESPACE", h)
    out = expand_whole_file_template(
      "operators.inl",
      "2026-01-01",
      {"guard": "PY2CPP_OPERATORS_INL"},
      apply_allman=False,
    )
    self.assertIn("_py_int_mod", out)
    self.assertIn("str_format_printf_spec", out)
    self.assertIn("percent_format", out)
    self.assertIn("_py_i64_mod", out)
    self.assertIn("chr(PyInt i)", out)
    self.assertIn("#ifndef PY2CPP_OPERATORS_INL", out)
    self.assertIn("#endif // PY2CPP_OPERATORS_INL", out)
    self.assertNotIn("PY2CPP_NAMESPACE", out)

  def test_codegen_file_wrap_preamble(self):
    out = expand_whole_file_template(
      "operators.inl",
      "2026-06-14",
      {"guard": "PY2CPP_OPERATORS_INL"},
      apply_allman=False,
    )
    self.assertIn("// 由 py2cpp 生成", out)
    self.assertIn("// 2026-06-14", out)
    self.assertIn("#ifndef PY2CPP_OPERATORS_INL", out)
    self.assertIn("#endif // PY2CPP_OPERATORS_INL", out)

  def test_syntax_showcase_ignore_and_include(self):
    out = _expand_showcase()
    self.assertNotIn("PY2CPP_IGNORE", out)
    self.assertNotIn("#include \"py2cpp/text/str.h\"", out)
    self.assertIn("snippet_marker = 42;", out)

  def test_syntax_showcase_scope(self):
    out = _expand_showcase()
    self.assertIn("namespace util", out)
    self.assertIn("namespace memory", out)
    self.assertNotIn("PY2CPP_BEGIN_SCOPE", out)

  def test_for_static_expand(self):
    out = _expand_showcase()
    self.assertIn("buf[0] = 1;", out)
    self.assertIn("buf[1] = 2;", out)
    self.assertIn("buf[2] = 3;", out)

  def test_if_static_chain_keeps_one_branch(self):
    out = _expand_showcase()
    self.assertIn("sqlite3_bind_int(stmt, 1, 2);", out)
    self.assertNotIn("sqlite3_bind_null(stmt, 3);", out)

  def test_if_elif_branch(self):
    out = _expand_showcase(typ=2)
    self.assertIn("sqlite3_bind_null(stmt, 3);", out)
    self.assertNotIn("sqlite3_bind_int(stmt, 1, 2);", out)

  def test_for_runtime_fallback(self):
    out = _expand_showcase()
    self.assertIn("while ((j < count))", out)
    self.assertIn("j = (j + 1);", out)

  def test_type_index_error_throw(self):
    out = _expand_showcase()
    self.assertIn("throw py2cpp::core::exceptions::IndexError();", out)

  def test_echo_inserts_lines(self):
    out = _expand_showcase()
    self.assertIn("block_a;", out)
    self.assertIn("block_b;", out)
    self.assertNotIn("PY2CPP_ECHO(", out)

  def test_echo_arbitrary_expr(self):
    out = _expand_showcase()
    self.assertIn("joined foobar;", out.replace("\n", " "))
    self.assertIn("first line_a;", out.replace("\n", " "))
    self.assertNotIn("PY2CPP_ECHO(", out)

  def test_echo_inline_suffix(self):
    out = _expand_showcase()
    self.assertIn("void fn() : x(0), y(1)", out.replace("\n", " ").replace("  ", " "))
    self.assertNotIn("PY2CPP_ECHO(", out)

  def test_echo_registry_and_for_names(self):
    out = _expand_showcase()
    self.assertIn("class PySized {};", out)
    self.assertIn(
      "void catch_(const py2cpp::core::exceptions::ValueError& e);",
      out,
    )
    self.assertIn(
      "void handle(const py2cpp::core::exceptions::ValueError& e);",
      out,
    )
    self.assertIn(
      "void handle(const py2cpp::core::exceptions::KeyError& e);",
      out,
    )

  def test_exec_def_inlines_template_helper(self):
    out = _expand_showcase()
    self.assertIn("line a;", out)
    self.assertIn("line b;", out)
    self.assertIn("line alpha;", out)
    self.assertIn("line beta;", out)
    self.assertNotIn("PY2CPP_EXEC", out)
    self.assertNotIn("fn_EmitLines", out)

  def test_exec_in_for_emits_comment(self):
    out = _expand_showcase()
    self.assertIn("// first", out)
    self.assertIn("mark[0] = 0;", out)

  def test_eval_string_constant_becomes_cpp_literal(self):
    out = _expand_showcase()
    self.assertIn('PyStr("hello")', out.replace(" ", ""))
    self.assertIn("marker=42;", out.replace(" ", ""))

  def test_eval_python_literal_types(self):
    out = _expand_showcase()
    compact = out.replace(" ", "")
    self.assertIn('PyStr("ab")', compact)
    self.assertIn("PyIntnum=42;", compact)
    self.assertIn("PyBoolflag=true;", compact)
    self.assertIn("1.5f", compact)

  def test_pure_cpp_preserved(self):
    out = _expand_showcase()
    self.assertIn("int pure_cpp_only = 0;", out)

  def test_tuple_codegen_template(self):
    out = expand_template("util/tuple.inl", apply_allman=False)
    self.assertIn("PyTuple<Args...>::__getitem__(int index)", out)
    self.assertIn("throw py2cpp::core::exceptions::IndexError();", out)

  def test_class_header_inject_templates(self):
    from src.codegen.expand_py2cpp_template import (
      expand_template,
      extract_py2cpp_inject_class_blocks,
    )

    expanded = expand_template("text/+str.h", apply_allman=False)
    blocks = extract_py2cpp_inject_class_blocks(expanded)
    self.assertIn("PyStr", blocks)
    self.assertEqual(len(blocks["PyStr"]), 2)
    joined = "\n".join(blocks["PyStr"])
    self.assertIn("format(c_str fmt", joined)
    self.assertIn("py2cpp::text::str::PyStr", joined)
    self.assertIn("__mod__(const PyTuple", joined)
    self.assertIn("PyArray<PyChar>&& data", joined)
    self.assertNotIn("PY2CPP_INJECT_CLASS", joined)

  def test_exceptions_inject_header_and_inl(self):
    from src.codegen.expand_py2cpp_template import (
      expand_template,
      extract_py2cpp_inject_class_blocks,
    )

    h = expand_template("core/+exceptions.h", apply_allman=False)
    blocks = extract_py2cpp_inject_class_blocks(h)
    self.assertIn("Exception", blocks)
    joined_h = "\n".join(blocks["Exception"])
    self.assertIn("__cause__", joined_h)
    self.assertIn("explicit Exception() : __cause__(nullptr) {}", joined_h)
    self.assertIn("explicit Exception(const py2cpp::core::exceptions::AssertionError& o)", joined_h)
    self.assertNotIn("PY2CPP_INLINE_ECHO", joined_h)
    self.assertNotIn("PY2CPP_DYNAMIC_TYPE", joined_h)
    inl = expand_template("core/+exceptions.inl", apply_allman=False)
    self.assertIn("Exception::Exception(const py2cpp::core::exceptions::KeyError& o)", inl)
    self.assertNotIn("PY2CPP_INLINE_ECHO", inl)
    self.assertNotIn("PY2CPP_DYNAMIC_TYPE", inl)

  def test_forbidden_type_eval_pattern_absent_in_templates(self):
    from src.codegen.expand_py2cpp_template import collect_forbidden_type_eval_violations

    self.assertEqual(collect_forbidden_type_eval_violations(), [])

  def test_forbidden_stl_container_pattern_absent_in_templates(self):
    from src.codegen.expand_py2cpp_template import collect_forbidden_stl_container_violations

    self.assertEqual(collect_forbidden_stl_container_violations(), [])

  def test_forbidden_stl_container_raises_on_expand(self):
    from src.codegen.expand_py2cpp_template import expand_template, template_root

    bad_rel = "~test/~forbidden_stl_smoke.inl"
    bad_path = template_root() / bad_rel
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    try:
      bad_path.write_text("#include <vector>\n", encoding="utf-8")
      with self.assertRaises(ValueError) as ctx:
        expand_template(bad_rel, apply_allman=False)
      msg = str(ctx.exception)
      self.assertIn("STL 容器", msg)
      self.assertIn("~test/~forbidden_stl_smoke.inl:1", msg)
      self.assertIn("#include <vector>", msg)
    finally:
      if bad_path.is_file():
        bad_path.unlink()
      try:
        bad_path.parent.rmdir()
      except OSError:
        pass


  def test_minimal_codegen_file_wrap(self):
    from src.codegen.umbrella_gen import build_py2cpp_umbrella_header

    header = build_py2cpp_umbrella_header(
      "PY2CPP_MINIMAL_H",
      "2026-06-15 00:00:00",
      "py2cpp",
      ["util/list"],
    )
    self.assertIn("#ifndef PY2CPP_MINIMAL_H", header)
    self.assertIn("#define PY2CPP_MINIMAL_H", header)
    self.assertIn("#endif // PY2CPP_MINIMAL_H", header)
    self.assertIn("templates/minimal.h（运行时万能头，聚合 py2cpp/*.h）", header)
    self.assertIn("// 2026-06-15 00:00:00", header)
    self.assertNotIn("PY2CPP_EVAL(guard)", header)
    self.assertNotIn("PY2CPP_ECHO(guard)", header)

  def test_forbidden_type_eval_raises_on_expand(self):
    from src.codegen.expand_py2cpp_template import expand_template, template_root

    bad_rel = "~test/~forbidden_type_eval_smoke.inl"
    bad_path = template_root() / bad_rel
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    try:
      bad_path.write_text(
        "void fn(const PY2CPP_TYPE(PY2CPP_EVAL(name))& o);\n",
        encoding="utf-8",
      )
      with self.assertRaises(ValueError) as ctx:
        expand_template(bad_rel, apply_allman=False)
      self.assertIn("PY2CPP_TYPE(PY2CPP_EVAL", str(ctx.exception))
    finally:
      if bad_path.is_file():
        bad_path.unlink()
      try:
        bad_path.parent.rmdir()
      except OSError:
        pass


  def test_forbidden_dynamic_type_pattern_absent_in_templates(self):
    from src.codegen.expand_py2cpp_template import collect_forbidden_dynamic_type_violations

    self.assertEqual(collect_forbidden_dynamic_type_violations(), [])

  def test_forbidden_dynamic_type_raises_on_expand(self):
    from src.codegen.expand_py2cpp_template import expand_template, template_root

    bad_rel = "~test/~forbidden_dynamic_type_smoke.inl"
    bad_path = template_root() / bad_rel
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    try:
      bad_path.write_text(
        "class PY2CPP_DYNAMIC_TYPE(Foo, bar) {};\n",
        encoding="utf-8",
      )
      with self.assertRaises(ValueError) as ctx:
        expand_template(bad_rel, apply_allman=False)
      self.assertIn("PY2CPP_DYNAMIC_TYPE 已删除", str(ctx.exception))
    finally:
      if bad_path.is_file():
        bad_path.unlink()
      try:
        bad_path.parent.rmdir()
      except OSError:
        pass


if __name__ == "__main__":
  unittest.main()
