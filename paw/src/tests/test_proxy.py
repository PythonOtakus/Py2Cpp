"""``expand_proxy`` / ``__base__`` / ``Super`` 译器单测。"""
import ast
import unittest

from src.analysis.ir import ClassInfo
from src.analysis.proxy import (
  cpp_proxy_inner_type,
  is_super_call_form,
  is_super_dunder_call,
  is_super_method_call,
  is_s0101_init_forward_call,
  unwrap_super_receiver,
)
from src.passes.class_type_base import _entity_base_ast, expand_class_type_base
from src.passes.proxy import expand_proxy
from src.tests.test_class_type_base import _TrStub, _parse_class


def _proxy_info() -> ClassInfo:
  node = ast.parse(
    """
@copyable
@native
class Proxy[T]:
  _target: T
  def __init__(self, target: T):
    self._target = target
"""
  ).body[0]
  info = ClassInfo(node, "py2cpp/core/proxy")
  info.is_native = True
  info.is_copyable = True
  return info


class TestProxyPass(unittest.TestCase):
  def test_unwrap_super_receiver(self):
    sup = ast.Name(id="super", ctx=ast.Load())
    self.assertTrue(unwrap_super_receiver(sup))
    self.assertTrue(unwrap_super_receiver(ast.Call(func=sup, args=[], keywords=[])))
    call_attr = ast.Call(
      func=ast.Attribute(value=sup, attr="__call__", ctx=ast.Load()),
      args=[],
      keywords=[],
    )
    self.assertTrue(unwrap_super_receiver(call_attr))
    self.assertTrue(is_super_call_form(ast.Call(func=sup, args=[], keywords=[])))
    self.assertTrue(is_super_call_form(call_attr))
    self.assertFalse(is_super_call_form(sup))
    inc = ast.Call(
      func=ast.Attribute(
        value=ast.Call(func=sup, args=[], keywords=[]),
        attr="inc",
        ctx=ast.Load(),
      ),
      args=[],
      keywords=[],
    )
    self.assertTrue(is_super_method_call(inc))
    init_call = ast.Call(
      func=ast.Attribute(value=sup, attr="__init__", ctx=ast.Load()),
      args=[],
      keywords=[],
    )
    self.assertTrue(is_super_dunder_call(init_call))
    bad_init = ast.Call(
      func=ast.Attribute(
        value=ast.Call(func=sup, args=[], keywords=[]),
        attr="__init__",
        ctx=ast.Load(),
      ),
      args=[],
      keywords=[],
    )
    self.assertFalse(is_super_dunder_call(bad_init))
    fwd = ast.Call(
      func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr="__init__", ctx=ast.Load()),
      args=[ast.Constant(value=1)],
      keywords=[],
    )
    self.assertTrue(is_s0101_init_forward_call(fwd, in_class_init=True))
    self.assertFalse(is_s0101_init_forward_call(fwd, in_class_init=False))

  def test_cpp_proxy_inner_type(self):
    self.assertEqual(cpp_proxy_inner_type("PyProxy<Widget>"), "Widget")
    self.assertEqual(
      cpp_proxy_inner_type("PyProxy<test_proxy::Widget>"),
      "test_proxy::Widget",
    )

  def test_counting_proxy_entity_base_is_inner_t(self):
    proxy = _proxy_info()
    host_node = ast.parse("class CountingProxy[T](Proxy[T]): pass").body[0]
    host = ClassInfo(host_node, "m")
    host.bases = ["Proxy"]
    tr = _TrStub({"Proxy": proxy, "CountingProxy": host})
    expand_proxy(tr)  # type: ignore[arg-type]
    expand_class_type_base(tr)  # type: ignore[arg-type]
    ast_obj = _entity_base_ast(host, tr)
    self.assertIsInstance(ast_obj, ast.Name)
    self.assertEqual(ast_obj.id, "T")
    self.assertEqual(host.type_aliases["__base__"].value.id, "T")

  def test_concrete_proxy_inner_widget(self):
    proxy = _proxy_info()
    widget = ClassInfo(_parse_class("class Widget: pass"), "m")
    host_node = ast.parse("class LoggingProxy(Proxy[Widget]): pass").body[0]
    host = ClassInfo(host_node, "m")
    host.bases = ["Proxy"]
    tr = _TrStub({"Proxy": proxy, "Widget": widget, "LoggingProxy": host})
    expand_proxy(tr)  # type: ignore[arg-type]
    expand_class_type_base(tr)  # type: ignore[arg-type]
    ast_obj = _entity_base_ast(host, tr)
    self.assertIsInstance(ast_obj, ast.Name)
    self.assertEqual(ast_obj.id, "Widget")


if __name__ == "__main__":
  unittest.main()
