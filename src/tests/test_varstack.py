"""``expand_varstack``：``VarStack`` + ``Self.iter_fields`` 译期展开。"""
from __future__ import annotations

import ast
import textwrap
import unittest

from src.analysis.ir import ClassInfo
from src.passes.varstack import expand_varstack


class ExpandVarStackTests(unittest.TestCase):
  def _host(self, src: str) -> ClassInfo:
    return ClassInfo(ast.parse(textwrap.dedent(src)).body[0])

  def _method(self, src: str) -> ast.FunctionDef:
    mod = ast.parse(textwrap.dedent(src))
    return mod.body[0].body[0]

  def test_vector2_zero(self):
    method = self._method(
      '''
      class M:
        @staticmethod
        def zero():
          vs: VarStack = new()
          for f in Self.iter_fields(public_only=True):
            vs.push(0.0)
          return new(*vs)
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("__py2cpp_vs_vs0", dump)
    self.assertIn("__py2cpp_vs_vs1", dump)
    self.assertNotIn("VarStack", dump)
    self.assertNotIn("push", dump)
    self.assertNotIn("iter_fields", dump)

  def test_vector3_scaled(self):
    method = self._method(
      '''
      class M:
        def scaled(self, other):
          vs: VarStack = new()
          for f in Self.iter_fields(public_only=True):
            vs.push(getattr(self, f) * getattr(other, f))
          return new(*vs)
      '''
    )
    host = self._host(
      '''
      class Vector3:
        x: float64 = 0.0
        y: float64 = 0.0
        z: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("__py2cpp_vs_vs0", dump)
    self.assertIn("__py2cpp_vs_vs1", dump)
    self.assertIn("__py2cpp_vs_vs2", dump)
    self.assertIn("attr='x'", dump)
    self.assertIn("attr='z'", dump)

  def test_two_stacks(self):
    method = self._method(
      '''
      class M:
        def pair(self, other):
          a: VarStack = new()
          b: VarStack = new()
          for f in Self.iter_fields(public_only=True):
            a.push(getattr(self, f))
            b.push(getattr(other, f))
          return new(*a), new(*b)
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("__py2cpp_vs_a0", dump)
    self.assertIn("__py2cpp_vs_a1", dump)
    self.assertIn("__py2cpp_vs_b0", dump)
    self.assertIn("__py2cpp_vs_b1", dump)

  def test_func_unpack(self):
    method = self._method(
      '''
      class M:
        def call_lerp(self, other, t):
          vs: VarStack = new()
          for f in Self.iter_fields(public_only=True):
            vs.push(lerp(getattr(self, f), getattr(other, f), t))
          return lerp(*vs)
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("__py2cpp_vs_vs0", dump)
    self.assertIn("__py2cpp_vs_vs1", dump)
    self.assertNotIn("Starred", dump)

  def test_pop_then_new(self):
    method = self._method(
      '''
      class M:
        def drop_tail(self):
          vs: VarStack = new()
          for f in Self.iter_fields(public_only=True):
            vs.push(getattr(self, f))
          vs.pop()
          return new(*vs)
      '''
    )
    host = self._host(
      '''
      class Vector3:
        x: float64 = 0.0
        y: float64 = 0.0
        z: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("__py2cpp_vs_vs0", dump)
    self.assertIn("__py2cpp_vs_vs1", dump)
    self.assertIn("__py2cpp_vs_vs2", dump)
    self.assertNotIn("pop", dump)
    self.assertNotIn("Starred", dump)
    self.assertRegex(
      dump,
      r"Call\(func=Name\(id='new'.*Name\(id='__py2cpp_vs_vs0'.*Name\(id='__py2cpp_vs_vs1'",
    )

  def test_pop_push_allocates_new_index(self):
    method = self._method(
      '''
      class M:
        def replace_tail(self, tail):
          vs: VarStack = new()
          vs.push(self.x)
          vs.push(self.y)
          vs.pop()
          vs.push(tail)
          return new(*vs)
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("__py2cpp_vs_vs0", dump)
    self.assertIn("__py2cpp_vs_vs1", dump)
    self.assertIn("__py2cpp_vs_vs2", dump)
    self.assertRegex(
      dump,
      r"Call\(func=Name\(id='new'.*Name\(id='__py2cpp_vs_vs0'.*Name\(id='__py2cpp_vs_vs2'",
    )

  def test_scope_if_use_rejected(self):
    method = self._method(
      '''
      class M:
        def bad(self, cond: bool):
          vs: VarStack = new()
          if cond:
            vs.push(self.x)
          return new(*vs)
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    with self.assertRaises(NotImplementedError) as ctx:
      expand_varstack(method, host)
    self.assertIn("不在同一作用域", str(ctx.exception))

  def test_scope_decl_in_if_rejected(self):
    method = self._method(
      '''
      class M:
        def bad(self, cond: bool):
          if cond:
            vs: VarStack = new()
            vs.push(self.x)
          return new(*vs)
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    with self.assertRaises(NotImplementedError) as ctx:
      expand_varstack(method, host)
    self.assertIn("不在同一作用域", str(ctx.exception))

  def test_top_inner_scope_ok(self):
    method = self._method(
      '''
      class M:
        def peek(self, cond: bool) -> float64:
          vs: VarStack = new()
          vs.push(self.x)
          vs.push(self.y)
          top: float64 = 0.0
          if cond:
            top = vs.top()
          return top
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("__py2cpp_vs_vs1", dump)
    self.assertNotIn("attr='top'", dump)

  def test_top_expansion(self):
    method = self._method(
      '''
      class M:
        def last(self) -> float64:
          vs: VarStack = new()
          vs.push(self.x)
          vs.push(self.y)
          return vs.top()
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertRegex(
      dump,
      r"Return\(value=Name\(id='__py2cpp_vs_vs1'",
    )

  def test_iter_fields_field_eq_inlined(self):
    method = self._method(
      '''
      class M:
        def conjugate(self):
          vs: VarStack = new()
          for f in Self.iter_fields(public_only=True):
            vs.push(getattr(self, f) if f == 'w' else -getattr(self, f))
          return new(*vs)
      '''
    )
    host = self._host(
      '''
      class Rotator:
        w: float64 = 1.0
        z: float64 = 0.0
      '''
    )
    expanded = expand_varstack(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("attr='w'", dump)
    self.assertIn("attr='z'", dump)
    self.assertNotIn("Compare", dump)
    self.assertNotIn("IfExp", dump)

  def test_rejects_bare_varstack_decl(self):
    method = self._method(
      '''
      class M:
        def bad(self):
          vs: VarStack
          vs.push(0.0)
      '''
    )
    host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    with self.assertRaises(NotImplementedError) as ctx:
      expand_varstack(method, host)
    self.assertIn("= new()", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
