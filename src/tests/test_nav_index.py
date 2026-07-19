"""``generated/.cache/nav`` 符号索引。"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from src.codegen.nav_index import (
  NAV_INDEX_VERSION,
  NAV_MANIFEST,
  _class_decl_line,
  _impl_definition_line,
  module_shard_name,
  module_shard_rel,
  nav_cache_dir,
  write_nav_index,
)
from src.translator import Translator


def _translate_snippet(src: str, *, name: str = "nav_snip.py") -> tuple[Path, dict, dict]:
  tmp = tempfile.TemporaryDirectory()
  out = Path(tmp.name)
  py = out / name
  py.write_text(src, encoding="utf-8")
  Translator.translate_file(str(py), output_dir=str(out), include_stdlib=False)
  manifest_path = nav_cache_dir(out) / NAV_MANIFEST
  manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
  module = name.replace(".py", "")
  shard_rel = manifest["modules"][module]["shard"]
  shard = json.loads((nav_cache_dir(out) / shard_rel).read_text(encoding="utf-8"))
  # 挂上 tmp 以免被 GC
  shard["_tmp"] = tmp
  return out, manifest, shard


class NavIndexTests(unittest.TestCase):
  def test_module_shard_path_matches_module(self):
    self.assertEqual(module_shard_name("py2cpp/util/list"), "py2cpp/util/list.json")
    self.assertEqual(
      module_shard_rel("test/misc/test_chr_ord"),
      "modules/test/misc/test_chr_ord.json",
    )

  def test_index_version_is_3(self):
    self.assertEqual(NAV_INDEX_VERSION, 3)

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
      self.assertEqual(manifest["version"], NAV_INDEX_VERSION)
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

  def test_property_setter_uses_dunder_set(self):
    src = """
from py2cpp import *

@copyable
class Box:
  _n: int = 0

  @property
  def capacity(self) -> int:
    return self._n

  @property.setter
  def capacity(self, v: int) -> None:
    self._n = v
"""
    _out, _manifest, shard = _translate_snippet(src, name="nav_prop.py")
    props = [s for s in shard["symbols"] if s["kind"] == "property" and s["name"] == "capacity"]
    roles = {s.get("role") for s in props}
    self.assertIn("getter", roles)
    self.assertIn("setter", roles)
    setter = next(s for s in props if s.get("role") == "setter")
    self.assertEqual(setter["cppName"], "capacity__set")
    self.assertNotIn("set_capacity", setter["cppName"])
    self.assertIn("decl", setter["cpp"])
    shard["_tmp"].cleanup()

  def test_staticproperty_indexed(self):
    src = """
from py2cpp import *

@copyable
class Matrix3:
  @staticproperty
  def zero() -> Self:
    return new()
"""
    _out, _manifest, shard = _translate_snippet(src, name="nav_sp.py")
    zeros = [
      s for s in shard["symbols"]
      if s["kind"] == "property" and s["name"] == "zero"
    ]
    self.assertTrue(zeros, shard["symbols"])
    self.assertEqual(zeros[0]["cppName"], "zero__get")
    shard["_tmp"].cleanup()

  def test_type_alias_indexed(self):
    src = """
from py2cpp import *

@copyable
class Holder:
  type Item = int

  def get(self) -> Item:
    return 0
"""
    _out, _manifest, shard = _translate_snippet(src, name="nav_alias.py")
    aliases = [s for s in shard["symbols"] if s["kind"] == "type_alias" and s["name"] == "Item"]
    self.assertTrue(aliases, [s["kind"] for s in shard["symbols"]])
    self.assertEqual(aliases[0]["owner"], "Holder")
    self.assertIn("decl", aliases[0]["cpp"])
    shard["_tmp"].cleanup()

  def test_enum_members_indexed(self):
    src = """
from py2cpp import *

@enum
class AggMode:
  Min = 0
  Max = 1
  Sum = 2
"""
    _out, _manifest, shard = _translate_snippet(src, name="nav_enum.py")
    cls = next(s for s in shard["symbols"] if s["kind"] == "class" and s["name"] == "AggMode")
    self.assertEqual(cls.get("role"), "enum")
    self.assertIn("decl", cls["cpp"])
    members = {
      s["name"]: s
      for s in shard["symbols"]
      if s["kind"] == "enum_member"
    }
    self.assertEqual(set(members), {"Min", "Max", "Sum"})
    self.assertIn("decl", members["Min"]["cpp"])
    self.assertEqual(members["Min"]["cppQual"], "AggMode::Min")
    shard["_tmp"].cleanup()

  def test_union_variant_prefers_factory(self):
    src = """
from py2cpp import *

@union
class Result[OkValue, ErrValue]:
  @variant
  class Ok:
    value: OkValue

  @variant
  class Err:
    error: ErrValue
"""
    _out, _manifest, shard = _translate_snippet(src, name="nav_union.py")
    variants = {
      s["name"]: s
      for s in shard["symbols"]
      if s["kind"] == "variant"
    }
    self.assertEqual(set(variants), {"Ok", "Err"})
    ok = variants["Ok"]
    self.assertIn("decl", ok["cpp"])
    # 工厂行应含 Ok(
    h_rel = shard["artifacts"]["h"]
    self.assertIsNotNone(h_rel)
    h_path = Path(shard["_tmp"].name) / h_rel if not Path(h_rel).is_file() else Path(h_rel)
    # artifacts 为相对仓库/输出根
    candidates = [
      Path(shard["_tmp"].name) / h_rel.replace("\\", "/").split("/")[-1],
      Path(shard["_tmp"].name) / Path(h_rel).name,
    ]
    # 从 shard 旁找 .h
    for p in Path(shard["_tmp"].name).rglob("*.h"):
      candidates.append(p)
    h_text = None
    for p in candidates:
      if p.is_file():
        h_text = p.read_text(encoding="utf-8")
        break
    self.assertIsNotNone(h_text)
    decl_line = ok["cpp"]["decl"]["line"]
    line = h_text.splitlines()[decl_line - 1]
    self.assertIn("Ok", line)
    self.assertTrue("static" in line or "Ok(" in line, line)
    shard["_tmp"].cleanup()

  def test_protocol_py_only(self):
    src = """
from py2cpp import *

@protocol
class Readable:
  type Element = int

  def read(self) -> Element: ...
"""
    _out, _manifest, shard = _translate_snippet(src, name="nav_proto.py")
    proto = next(s for s in shard["symbols"] if s["kind"] == "protocol")
    self.assertEqual(proto["name"], "Readable")
    self.assertEqual(proto.get("cpp"), {})
    methods = [s for s in shard["symbols"] if s["kind"] == "method" and s["name"] == "read"]
    self.assertTrue(methods)
    self.assertEqual(methods[0].get("cpp"), {})
    shard["_tmp"].cleanup()

  def test_delegate_indexed(self):
    src = """
from py2cpp import *

@delegate
def UIEvent() -> None: ...
"""
    _out, _manifest, shard = _translate_snippet(src, name="nav_del.py")
    dels = [s for s in shard["symbols"] if s["kind"] == "delegate" and s["name"] == "UIEvent"]
    self.assertTrue(dels, [s["kind"] for s in shard["symbols"]])
    self.assertIn("decl", dels[0]["cpp"])
    shard["_tmp"].cleanup()

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

  def test_enum_class_decl_line(self):
    import ast

    from src.analysis.ir import ClassInfo

    header = """
namespace py2cpp
{
  enum class AggMode : PyInt
  {
    Min = 0,
  };
}
"""
    lines = header.splitlines()
    node = ast.parse("class AggMode: pass").body[0]
    info = ClassInfo(node, "py2cpp/alg/agg_mode")
    self.assertEqual(_class_decl_line(lines, info), 4)

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
      re.compile(r"\bpy2cpp::util::list::PyList\s*::\s*_tim_compute_minrun\s*\("),
      re.compile(r"\bPyList\s*::\s*_tim_compute_minrun\s*\("),
      re.compile(r"\b_tim_compute_minrun\s*\("),
    ]
    self.assertEqual(_impl_definition_line(lines, patterns, "_tim_compute_minrun"), 8)


if __name__ == "__main__":
  unittest.main()
