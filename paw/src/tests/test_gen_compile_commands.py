"""``scripts/gen_compile_commands.py`` 收集 ``templates/``。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class GenCompileCommandsTests(unittest.TestCase):
  def test_collect_includes_templates_inl(self):
    from scripts.gen_compile_commands import _collect_sources

    paths = {_collect_sources_path(p) for p in _collect_sources()}
    self.assertIn("templates/util/+memory.inl", paths)
    self.assertIn("templates/text/+bytes.inl", paths)
    self.assertIn("templates/text/+str.h", paths)
    self.assertIn("templates/operators.inl", paths)
    self.assertIn("templates/operators.h", paths)
    self.assertIn("templates/~test/~syntax_showcase.inl", paths)

  def test_template_compile_command_includes_generated_runtime(self):
    from scripts.gen_compile_commands import _compile_command, write_macro_headers

    write_macro_headers()
    cmd = _compile_command(ROOT / "templates" / "text" / "+bytes.inl")
    norm = cmd.replace("\\", "/")
    self.assertIn("generated/runtime", norm)
    self.assertNotIn("~macros.h", norm)
    self.assertIn("~macro/text/+bytes.inl.h", norm)
    self.assertIn("PY2CPP_IGNORE", (ROOT / "templates" / "~macro" / "text" / "+bytes.inl.h").read_text(encoding="utf-8"))
    sqlite_hdr = (ROOT / "templates" / "~macro" / "sql" / "+sqlite.inl.h").read_text(encoding="utf-8")
    self.assertIn("#define PY2CPP_NAMESPACE py2cpp::sql::sqlite", sqlite_hdr)
    self.assertIn("#define PY2CPP_EVAL(...) __VA_ARGS__", sqlite_hdr)
    self.assertIn("#define PY2CPP_TYPE_PyStr", sqlite_hdr)
    self.assertIn("#define PY2CPP_TYPE(Type) PY2CPP_TYPE_##Type", sqlite_hdr)
    self.assertIn("#define PY2CPP_ECHO(...) __VA_ARGS__", sqlite_hdr)

  def test_str_header_macro_and_compile_command(self):
    from scripts.gen_compile_commands import _compile_command, write_macro_headers

    write_macro_headers()
    macro_path = ROOT / "templates" / "~macro" / "text" / "+str.h.h"
    self.assertTrue(macro_path.is_file(), macro_path)
    macro_text = macro_path.read_text(encoding="utf-8")
    self.assertIn("#define PY2CPP_INJECT_CLASS(...)", macro_text)
    self.assertIn("#define PY2CPP_NAMESPACE py2cpp::text::str", macro_text)
    cmd = _compile_command(ROOT / "templates" / "text" / "+str.h")
    self.assertIn("~macro/text/+str.h.h", cmd.replace("\\", "/"))

  def test_exception_group_impl_macro_header(self):
    from scripts.gen_compile_commands import write_macro_headers

    write_macro_headers()
    macro_path = ROOT / "templates" / "~macro" / "core" / "~exception_group_dynamic_impl.inl.h"
    self.assertTrue(macro_path.is_file(), macro_path)
    macro_text = macro_path.read_text(encoding="utf-8")
    self.assertIn("#define PY2CPP_BEGIN_SCOPE namespace py2cpp", macro_text)
    self.assertIn("core::exceptions", macro_text)

  def test_generated_json_lists_templates(self):
    from scripts.gen_compile_commands import main

    if not (ROOT / "generated" / "runtime").is_dir():
      self.skipTest("generated/runtime 不存在")
    if main() != 0:
      self.skipTest("gen_compile_commands 失败")
    data = json.loads((ROOT / "compile_commands.json").read_text(encoding="utf-8"))
    files = [e["file"].replace("\\", "/") for e in data]
    self.assertTrue(any(f.endswith("templates/util/+memory.inl") for f in files))


def _collect_sources_path(path: Path) -> str:
  return path.relative_to(ROOT).as_posix()


if __name__ == "__main__":
  unittest.main()
