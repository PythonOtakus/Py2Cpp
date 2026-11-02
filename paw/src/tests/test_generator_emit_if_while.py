"""生成器 ``__resume``：``if`` 与 ``while`` 分态（勿在 ``if`` 块内截断 ``switch case``）。"""
from __future__ import annotations

import ast
import unittest

from src.passes.generator_emit import GeneratorSwitchEmitter
from src.passes.generators import _transform_function
from src.translator import Translator


def _resume_body_from_source(src: str) -> list[ast.stmt]:
  tree = ast.parse(src)
  fn = tree.body[0]
  assert isinstance(fn, ast.FunctionDef)
  _, gen_cls = _transform_function(fn, "g_generator", Translator("mod", "mod.py"))
  for node in gen_cls.body:
    if isinstance(node, ast.FunctionDef) and node.name == "__resume":
      return node.body
  raise AssertionError("__resume not found")


def _resume_has_self_annassign(body: list[ast.stmt]) -> bool:
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if not isinstance(node, ast.AnnAssign):
      continue
    t = node.target
    if (
      isinstance(t, ast.Attribute)
      and isinstance(t.value, ast.Name)
      and t.value.id == "self"
    ):
      return True
  return False


class TranslatorStub:
  """最小 ``Translator`` 桩，仅用于拼 ``__resume`` 片段。"""

  indent_level = 0
  class_info = None

  def write_line(self, s: str = "") -> None:
    self._lines.append(s)

  def __init__(self) -> None:
    self._lines: list[str] = []
    self._loop_stack: list = []

  def _use_block(self, header: str = ""):
    from contextlib import contextmanager

    @contextmanager
    def _cm():
      if header:
        self.write_line(header)
        self.write_line("{")
        self.indent_level += 1
      try:
        yield
      finally:
        if header:
          self.indent_level -= 1
          self.write_line("}")

    return _cm()

  def visit(self, node: ast.AST) -> str:
    if isinstance(node, ast.Name):
      return node.id
    if isinstance(node, ast.Compare):
      left = self.visit(node.left)
      ops: list[str] = []
      for op, comp in zip(node.ops, node.comparators):
        if isinstance(op, ast.Lt):
          ops.append(f"{left} < {self.visit(comp)}")
        elif isinstance(op, ast.GtE):
          ops.append(f"{left} >= {self.visit(comp)}")
        else:
          ops.append(f"{left} ? {self.visit(comp)}")
        left = self.visit(comp)
      return ops[0] if len(ops) == 1 else " && ".join(ops)
    return "expr"

  def _iter_result_return_expr(self) -> str:
    return "PY2CPP_RETURN"

  def _result_value_expr(self, val: str) -> str:
    return f"PY2CPP_YIELD({val})"

  def _result_return_done_expr(self, val: str) -> str:
    return f"PY2CPP_DONE({val})"

  def _next_result_cpp_type(self) -> str:
    return "PyIterResult<int, PyNone>"

  def _member_access(self, expr: str) -> str:
    return "."

  def _emit_active_finally(self) -> None:
    pass

  def _emit_with_exits(self) -> None:
    pass


def _emit_resume(body: list[ast.stmt]) -> str:
  tr = TranslatorStub()
  GeneratorSwitchEmitter(tr).emit(body)
  return "\n".join(tr._lines)


class GeneratorEmitIfWhileTests(unittest.TestCase):
  def test_resume_hoisted_fields_use_assign_not_annassign(self):
    body = _resume_body_from_source(
      """
def g() -> GeneratorType[int, None, None]:
  j: int = 0
  while j < 3:
    yield j
    j += 1
  return
""",
    )
    self.assertFalse(_resume_has_self_annassign(body))

  def test_leading_docstring_not_in_resume(self):
    body = _resume_body_from_source(
      """
def g() -> GeneratorType[int, None, None]:
  \"\"\"doc only\"\"\"
  yield 1
""",
    )
    out = _emit_resume(body)
    self.assertNotIn("doc only", out)

  def test_wrapper_keeps_leading_docstring(self):
    src = """
def g() -> GeneratorType[int, None, None]:
  \"\"\"doc on wrapper\"\"\"
  yield 1
"""
    tree = ast.parse(src)
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    wrapper, _ = _transform_function(fn, "g_generator", Translator("mod", "mod.py"))
    self.assertEqual(ast.get_docstring(wrapper), "doc on wrapper")

  def test_if_then_while_separate_cases(self):
    body = _resume_body_from_source(
      """
def g() -> GeneratorType[int, None, None]:
  flag: bool = True
  if flag:
    i: int = 0
    while i < 3:
      yield i
      i += 1
  return
""",
    )
    out = _emit_resume(body)
    self.assertIn("if (!(", out)
    self.assertIn("PY2CPP_YIELD", out)
    self.assertNotRegex(out, r"case 0:\s*\{[^}]*case 0:")

  def test_if_else_both_yield(self):
    body = _resume_body_from_source(
      """
def g() -> GeneratorType[int, None, None]:
  i: int = 0
  if i % 2 == 0:
    yield 0
  else:
    yield 101
  return
""",
    )
    out = _emit_resume(body)
    self.assertEqual(out.count("PY2CPP_YIELD"), 2)
    # 每个 ``yield`` 之后须有续推 ``case`` 桥接到 ``join``（勿与 ``if (!test)`` 分支配态混淆）
    import re

    for chunk in out.split("PY2CPP_YIELD")[1:3]:
      self.assertRegex(
        chunk,
        re.compile(r"case \d+:\s*\{[^}]*this->_state = \d+;\s*continue;"),
      )

  def test_if_yield_then_join_bridge(self):
    body = _resume_body_from_source(
      """
def g() -> GeneratorType[int, None, None]:
  i: int = 0
  while i < 3:
    if i < 2:
      yield i
    i += 1
  return
""",
    )
    out = _emit_resume(body)
    self.assertIn("case 4:", out)
    self.assertRegex(
      out,
      r"case 4:\s*\{[^}]*this->_state = 3;\s*continue;",
    )

  def test_while_exit_falls_through(self):
    body = _resume_body_from_source(
      """
def g() -> GeneratorType[int, None, None]:
  i: int = 0
  while i < 1:
    yield i
    i += 1
  return
""",
    )
    out = _emit_resume(body)
    head, _tail = out.split("PY2CPP_YIELD", 1)
    self.assertIn("if (!(", head)
    self.assertNotIn("PY2CPP_RETURN", head)

  def test_sync_yield_from_yields_child_value(self):
    body = _resume_body_from_source(
      """
def g(xs: list[int]) -> GeneratorType[int, None, None]:
  yield from xs
""",
    )
    out = _emit_resume(body)
    self.assertIn("return (PyIterResult<int, PyNone>::Yield)", out)
    self.assertNotRegex(out, r"if \(!__yf\d+\.done__get\(\)\)\s*\{\s*continue;")


if __name__ == "__main__":
  unittest.main()
