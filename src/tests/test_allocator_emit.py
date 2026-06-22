"""``util.allocator`` / ``array[T, StackLength]`` codegen。"""
from __future__ import annotations

import unittest
from pathlib import Path


class AllocatorArrayEmitTests(unittest.TestCase):
  def test_array_uses_allocator(self):
    h = Path("generated/runtime/py2cpp/util/array.h").read_text(encoding="utf-8")
    self.assertIn("Allocator", h)
    self.assertIn("_alloc", h)
    inl = Path("generated/runtime/py2cpp/util/array.inl").read_text(encoding="utf-8")
    self.assertIn(".allocate(", inl)
    self.assertIn(".release(", inl)

  def test_stack_array_forward_decl_two_param_pyarray(self):
    h = Path("generated/runtime/py2cpp/util/stack_array.h").read_text(encoding="utf-8")
    self.assertIn("template<typename U, PyInt _StackLength>", h)
    self.assertIn("class PyArray;", h)


if __name__ == "__main__":
  unittest.main()
