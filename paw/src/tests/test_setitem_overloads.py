"""``__setitem__`` 自动生成 const/按值重载。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.analyzer import SignatureBuilder, TypeParser
from src.analysis.ir import ClassInfo
from src.emit.setitem_emit import (
  extra_setitem_decl_params,
  parse_setitem_value_param,
)


class SetitemOverloadTests(unittest.TestCase):
  def test_parse_mutable_lref(self):
    p = parse_setitem_value_param("Key key, Value& value")
    self.assertIsNotNone(p)
    assert p is not None
    self.assertEqual(p.ref, "mutable_lref")
    self.assertEqual(len(extra_setitem_decl_params(p)), 2)

  def test_parse_const_lref(self):
    p = parse_setitem_value_param("Key key, const Value& value")
    self.assertIsNotNone(p)
    assert p is not None
    self.assertEqual(p.ref, "const_lref")
    self.assertEqual(len(extra_setitem_decl_params(p)), 1)

  def test_parse_by_value(self):
    p = parse_setitem_value_param("PyInt index, T value")
    self.assertIsNotNone(p)
    assert p is not None
    self.assertEqual(p.ref, "value")
    self.assertEqual(extra_setitem_decl_params(p), [])

  def test_type_param_value_not_pass_by_ref(self):
    dict_src = """
class dict[Key, Value]:
  def __setitem__(self, key: Key, value: Value):
    pass
"""
    dict_node = ast.parse(dict_src).body[0]
    dinfo = ClassInfo(dict_node, "py2cpp/util/dict")
    method = dinfo.methods["__setitem__"]
    tp = TypeParser()
    tp.set_type_aliases(dinfo.type_aliases, use_as_cpp_name=True)
    sb = SignatureBuilder(tp)
    sb.set_classes({"dict": dinfo})
    sig = sb.build_method_sig(dinfo, method)
    self.assertIn("Value value", sig.params_decl)
    self.assertNotIn("const Value& value", sig.params_decl)

  def test_user_class_value_pass_by_ref(self):
    dict_src = """
class dict[Key, ValueType]:
  def __setitem__(self, key: Key, value: ValueType):
    pass
"""
    union_src = "class ValueType[T]: pass"
    dict_node = ast.parse(dict_src).body[0]
    union_node = ast.parse(union_src).body[0]
    dinfo = ClassInfo(dict_node, "py2cpp/util/dict")
    vinfo = ClassInfo(union_node, "test/lang/test_union")
    method = dinfo.methods["__setitem__"]
    tp = TypeParser()
    tp.set_type_aliases(dinfo.type_aliases, use_as_cpp_name=True)
    sb = SignatureBuilder(tp)
    sb.set_classes({"dict": dinfo, "ValueType": vinfo})
    sig = sb.build_method_sig(dinfo, method)
    self.assertIn("const ValueType& value", sig.params_decl)


if __name__ == "__main__":
  unittest.main()
