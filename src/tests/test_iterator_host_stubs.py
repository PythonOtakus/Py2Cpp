"""``iterator_host_stubs``：迭代器宿主指针推导。"""
from __future__ import annotations

import unittest

from src.analysis.stubs.iterator_host_stubs import (
  dict_like_host_py_name,
  host_owner_field_name,
  host_owner_param_name,
  host_ptr_cpp_type,
  iterator_ctor_self_expr,
  iterator_owner_host_py_name,
  load_frozendict_host_bound_class_names,
)


class IteratorHostStubTests(unittest.TestCase):
  def test_iterator_owner_host_names(self):
    self.assertEqual(iterator_owner_host_py_name("ListIterator"), "list")
    self.assertEqual(iterator_owner_host_py_name("FrozenDictKeyIterator"), "frozendict")
    self.assertEqual(iterator_owner_host_py_name("ChunkDequeReverseIterator"), "ChunkDeque")
    self.assertEqual(iterator_owner_host_py_name("ECSComponentTableIterator"), "ECSComponentTable")

  def test_frozendict_host_bound_includes_views(self):
    names = load_frozendict_host_bound_class_names()
    self.assertIn("FrozenDictKeysView", names)
    self.assertIn("FrozenDictItemsIterator", names)
    self.assertNotIn("DictKeysView", names)

  def test_owner_field_and_param(self):
    self.assertEqual(host_owner_field_name("ListIterator"), "_owner")
    self.assertEqual(host_owner_param_name("ListIterator"), "owner")
    self.assertIsNone(host_owner_field_name("DictKeyIterator"))
    self.assertEqual(host_owner_field_name("FrozenDictKeyIterator"), "_dct")
    self.assertEqual(host_owner_param_name("DequeIterator"), "dq")
    self.assertEqual(host_owner_field_name("ChunkDequeIterator"), "_dq")

  def test_host_ptr_cpp_type(self):
    self.assertEqual(
      host_ptr_cpp_type("list", ["T"]),
      "const PyList<T>*",
    )
    self.assertEqual(
      host_ptr_cpp_type("dict", ["K", "V"]),
      "const PyDict<K, V>*",
    )
    self.assertEqual(
      host_ptr_cpp_type("deque", ["T"], const=False),
      "PyDeque<T>*",
    )

  def test_iterator_ctor_self_expr(self):
    self.assertEqual(iterator_ctor_self_expr("dict"), "*this")
    self.assertEqual(iterator_ctor_self_expr("list"), "this")
    self.assertEqual(iterator_ctor_self_expr("frozenset"), "*this")
    self.assertEqual(iterator_ctor_self_expr("ChunkDeque"), "this")

  def test_dict_like_host_py_name(self):
    self.assertEqual(dict_like_host_py_name("DictValuesIterator"), "dict")
    self.assertEqual(dict_like_host_py_name("FrozenDictKeysView"), "frozendict")


if __name__ == "__main__":
  unittest.main()
