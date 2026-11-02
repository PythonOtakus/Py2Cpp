"""``is_stub_function_body`` / ``@native`` 桩体校验。"""
import ast
import unittest

from src.analysis.ir import is_native_function_body, is_overload_stub, is_stub_function_body


class StubFunctionBodyTests(unittest.TestCase):
  def test_ellipsis_only(self):
    body = ast.parse("def f():\n  ...").body[0].body  # type: ignore[attr-defined]
    self.assertTrue(is_stub_function_body(body))

  def test_docstring_then_ellipsis(self):
    body = ast.parse('def f():\n  """d"""\n  ...').body[0].body  # type: ignore[attr-defined]
    self.assertTrue(is_stub_function_body(body))

  def test_pass_only(self):
    body = ast.parse("def f():\n  pass").body[0].body  # type: ignore[attr-defined]
    self.assertTrue(is_stub_function_body(body))

  def test_return_not_stub(self):
    body = ast.parse("def f():\n  return 0").body[0].body  # type: ignore[attr-defined]
    self.assertFalse(is_stub_function_body(body))


class NativeFunctionBodyTests(unittest.TestCase):
  def test_ellipsis_only(self):
    body = ast.parse("def f():\n  ...").body[0].body  # type: ignore[attr-defined]
    self.assertTrue(is_native_function_body(body))

  def test_docstring_then_ellipsis(self):
    body = ast.parse('def f():\n  """d"""\n  ...').body[0].body  # type: ignore[attr-defined]
    self.assertTrue(is_native_function_body(body))

  def test_pass_rejected(self):
    body = ast.parse("def f():\n  pass").body[0].body  # type: ignore[attr-defined]
    self.assertFalse(is_native_function_body(body))


class OverloadStubTests(unittest.TestCase):
  def test_native_overload_not_pass_stub(self):
    node = ast.parse(
      "@overload\n@native\ndef __init__(self, value: int):\n  ...",
    ).body[0]
    assert isinstance(node, ast.FunctionDef)
    self.assertFalse(is_overload_stub(node))

  def test_pass_overload_is_stub(self):
    node = ast.parse("@overload\ndef f(x: int):\n  pass").body[0]
    assert isinstance(node, ast.FunctionDef)
    self.assertTrue(is_overload_stub(node))


if __name__ == "__main__":
  unittest.main()
