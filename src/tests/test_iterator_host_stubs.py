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
    self.assertEqual(iterator_owner_host_py_name("list_iterator"), "list")
    self.assertEqual(iterator_owner_host_py_name("frozendict_key_iterator"), "frozendict")
    self.assertEqual(iterator_owner_host_py_name("ChunkDequeReverseIterator"), "ChunkDeque")
    self.assertEqual(iterator_owner_host_py_name("ECSComponentTableIterator"), "ECSComponentTable")

  def test_frozendict_host_bound_includes_views(self):
    names = load_frozendict_host_bound_class_names()
    self.assertIn("frozendict_keys_view", names)
    self.assertIn("frozendict_items_iterator", names)
    self.assertNotIn("dict_keys_view", names)

  def test_owner_field_and_param(self):
    self.assertEqual(host_owner_field_name("list_iterator"), "_owner")
    self.assertEqual(host_owner_param_name("list_iterator"), "owner")
    self.assertIsNone(host_owner_field_name("dict_key_iterator"))
    self.assertEqual(host_owner_field_name("frozendict_key_iterator"), "_dct")
    self.assertEqual(host_owner_param_name("deque_iterator"), "dq")
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
    self.assertEqual(dict_like_host_py_name("dict_values_iterator"), "dict")
    self.assertEqual(dict_like_host_py_name("frozendict_keys_view"), "frozendict")


if __name__ == "__main__":
  unittest.main()
