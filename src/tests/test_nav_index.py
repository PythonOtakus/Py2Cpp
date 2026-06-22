"""``generated/.cache/nav`` 符号索引。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.codegen.nav_index import (
  NAV_MANIFEST,
  _class_decl_line,
  _impl_definition_line,
  module_shard_name,
  module_shard_rel,
  nav_cache_dir,
  write_nav_index,
)
from src.translator import Translator


class NavIndexTests(unittest.TestCase):
  def test_module_shard_path_matches_module(self):
    self.assertEqual(module_shard_name("py2cpp/util/list"), "py2cpp/util/list.json")
    self.assertEqual(
      module_shard_rel("test/misc/test_chr_ord"),
      "modules/test/misc/test_chr_ord.json",
    )

  def test_user_module_shard_has_class_and_method(self):
    src = """
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

@copyable
class ChrOrdTests(TestCaseMixin):
  @override
  def test(self) -> None:
    x: int = 1
    self.assertEqual(x, 1)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "test_chr_ord.py"
      py.write_text(src, encoding="utf-8")
      Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      manifest_path = nav_cache_dir(out) / NAV_MANIFEST
      self.assertTrue(manifest_path.is_file(), manifest_path)
      manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
      self.assertIn("test_chr_ord", manifest["modules"])
      shard_rel = manifest["modules"]["test_chr_ord"]["shard"]
      self.assertEqual(shard_rel, "modules/test_chr_ord.json")
      shard = json.loads((nav_cache_dir(out) / shard_rel).read_text(encoding="utf-8"))
      kinds = {s["kind"] for s in shard["symbols"]}
      self.assertIn("class", kinds)
      self.assertIn("method", kinds)
      cls = next(s for s in shard["symbols"] if s["kind"] == "class")
      self.assertEqual(cls["name"], "ChrOrdTests")
      self.assertIn("decl", cls["cpp"])
      method = next(s for s in shard["symbols"] if s["kind"] == "method" and s["name"] == "test")
      self.assertIn("impl", method["cpp"])

  def test_class_decl_skips_forward_declaration(self):
    import ast

    from src.analysis.ir import ClassInfo

    header = """
namespace py2cpp { namespace util { namespace list { template<typename T> class PyList; } } }
namespace py2cpp
{
  namespace util
  {
    namespace list
    {
      template<typename T>
      class PyList;
      template<typename T>
      class PyList
      {
      public:
        void append();
      };
    }
  }
}
"""
    lines = header.splitlines()
    node = ast.parse("class list: pass").body[0]
    info = ClassInfo(node, "py2cpp/util/list")
    info.cpp_rename = "PyList"
    self.assertEqual(_class_decl_line(lines, info), 12)

  def test_impl_line_skips_this_call_site(self):
    inl = """
void py2cpp::util::list::PyList<T>::sort()
{
  PyInt minrun = this->_tim_compute_minrun(n);
}

template<typename T>
PyInt py2cpp::util::list::PyList<T>::_tim_compute_minrun(PyInt n) const
{
  return n;
}
"""
    lines = inl.splitlines()
    patterns = [
      __import__("re").compile(r"\bpy2cpp::util::list::PyList\s*::\s*_tim_compute_minrun\s*\("),
      __import__("re").compile(r"\bPyList\s*::\s*_tim_compute_minrun\s*\("),
      __import__("re").compile(r"\b_tim_compute_minrun\s*\("),
    ]
    self.assertEqual(_impl_definition_line(lines, patterns, "_tim_compute_minrun"), 8)


if __name__ == "__main__":
  unittest.main()
