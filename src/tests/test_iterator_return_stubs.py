"""``iterator_return_stubs``：``__iter__`` / ``__reversed__`` 返回类型表驱动。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.ir import ClassInfo
from src.analysis.stubs.iterator_return_stubs import (
  iter_method_return_type,
  reversed_method_return_type,
)


def _info(name: str, *, type_params: list[str] | None = None) -> ClassInfo:
  node = ast.ClassDef(name=name, bases=[], keywords=[], body=[], decorator_list=[])
  info = ClassInfo(node)
  if type_params is not None:
    info.type_params = type_params
  return info


class IteratorReturnStubsTests(unittest.TestCase):
  def test_list_iter(self):
    rt, _ = iter_method_return_type(_info("list", type_params=["int"])) or ("", "")
    self.assertIn("PyListIterator", rt)
    self.assertIn("int", rt)

  def test_dict_iter(self):
    rt, _ = iter_method_return_type(_info("dict", type_params=["int", "str"])) or ("", "")
    self.assertIn("PyDictKeyIterator", rt)

  def test_str_reversed(self):
    rt, _ = reversed_method_return_type(_info("str")) or ("", "")
    self.assertIn("PyStrReverseIterator", rt)

  def test_dict_keys_view_reversed(self):
    rt, _ = reversed_method_return_type(
      _info("dict_keys_view", type_params=["int", "str"]),
    ) or ("", "")
    self.assertIn("PyDictKeyReverseIterator", rt)

  def test_seq_iterator_name(self):
    info = _info("stack_array", type_params=["byte"])
    info.seq_iterator_name = "stack_array_iterator"
    rt, _ = iter_method_return_type(info) or ("", "")
    self.assertIn("PyStackArrayIterator", rt)


if __name__ == "__main__":
  unittest.main()
