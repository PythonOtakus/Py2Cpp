"""``expand_mirror_to_generated`` 镜像写盘（含 ``*.h``）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.codegen.expand_py2cpp_template import expand_mirror_to_generated


class ExpandMirrorCodegenTests(unittest.TestCase):
  def test_mirror_writes_tuple_h_and_inl(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      written = expand_mirror_to_generated(
        root,
        generated_at="生成时间: test",
        apply_allman=False,
      )
      rels = {p.relative_to(root).as_posix() for p in written}
      self.assertIn("util/tuple.h", rels)
      self.assertIn("util/tuple.inl", rels)
      htext = (root / "util/tuple.h").read_text(encoding="utf-8")
      self.assertIn("#ifndef PY2CPP_UTIL_TUPLE_H", htext)
      self.assertIn("#include \"py2cpp/util/tuple.inl\"", htext)
      self.assertIn("class PyTuple", htext)
      itext = (root / "util/tuple.inl").read_text(encoding="utf-8")
      self.assertIn("模板实现", itext)
      self.assertIn("throw py2cpp::core::exceptions::IndexError();", itext)

  def test_mirror_writes_p0_stdlib_codegen(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      written = expand_mirror_to_generated(
        root,
        generated_at="生成时间: test",
        apply_allman=False,
      )
      rels = {p.relative_to(root).as_posix() for p in written}
      for rel in (
        "util/stack_array.h",
        "util/stack_array.inl",
        "core/refcount.h",
        "core/delegate.h",
        "weak/ref.h",
      ):
        self.assertIn(rel, rels)
      stack_h = (root / "util/stack_array.h").read_text(encoding="utf-8")
      self.assertIn("class PyStackArray", stack_h)
      self.assertIn("#include \"py2cpp/util/stack_array.inl\"", stack_h)
      refcount_h = (root / "core/refcount.h").read_text(encoding="utf-8")
      self.assertIn("class PyRefCount", refcount_h)
      self.assertIn("class PyWeakRef", refcount_h)
      self.assertNotIn("#include \"py2cpp/core/refcount.inl\"", refcount_h)
      weak_h = (root / "weak/ref.h").read_text(encoding="utf-8")
      self.assertIn("#include \"py2cpp/core/refcount.h\"", weak_h)
      delegate_h = (root / "core/delegate.h").read_text(encoding="utf-8")
      self.assertIn("class PyDelegate", delegate_h)
      self.assertIn("py2cpp::util::list::PyList", delegate_h)


if __name__ == "__main__":
  unittest.main()
