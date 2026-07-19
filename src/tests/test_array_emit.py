"""``util.array`` / ``array[Element, StackLength]`` codegen。"""
from __future__ import annotations

import unittest
from pathlib import Path


class ArrayEmitTests(unittest.TestCase):
  def test_array_inlines_storage(self):
    h = Path("generated/runtime/py2cpp/util/array.h").read_text(encoding="utf-8")
    self.assertIn("_ptr", h)
    self.assertIn("_stack", h)
    self.assertIn("_heap", h)
    self.assertNotIn("Allocator", h)
    self.assertNotIn("_alloc", h)
    self.assertNotIn("buf__get", h)
    inl = Path("generated/runtime/py2cpp/util/array.inl").read_text(encoding="utf-8")
    self.assertIn("this->allocate(", inl)
    self.assertIn("this->release(", inl)
    self.assertIn("this->adopt_heap(", inl)
    self.assertNotIn("freeArray(this->_buf", inl)
    self.assertFalse(Path("generated/runtime/py2cpp/util/allocator.h").exists())

  def test_array2d_uses_data_array(self):
    h = Path("generated/runtime/py2cpp/util/array.h").read_text(encoding="utf-8")
    self.assertIn("_data", h)
    idx = h.find("class PyArray2D")
    self.assertGreater(idx, 0)
    chunk = h[idx : idx + 800]
    self.assertIn("PyArray", chunk)

  def test_stack_array_forward_decl_two_param_pyarray(self):
    h = Path("generated/runtime/py2cpp/util/stack_array.h").read_text(encoding="utf-8")
    self.assertIn("template<typename U, PyInt _StackLength>", h)
    self.assertIn("class PyArray;", h)


if __name__ == "__main__":
  unittest.main()
