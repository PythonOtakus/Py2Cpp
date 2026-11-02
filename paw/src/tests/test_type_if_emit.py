"""``type_if`` pass：泛型 ``if T is …`` → C++ ``enable_if`` / 全特化分派 struct。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.analysis.analyzer import TypeParser
from src.passes.type_if import (
  branch_emit_patterns,
  find_type_if_chains,
  parse_type_if_chain_from_body,
  plan_type_if_chain,
)
from src.translator import Translator
import ast


class TypeIfParseTests(unittest.TestCase):
  def test_rejects_not_t_is_int(self):
    src = """
def f[T](x: T) -> int:
  if not T is int:
    return 1
  else:
    return 0
"""
    tree = ast.parse(src)
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    tr = Translator("mod", "mod.py")
    with self.assertRaises(ValueError):
      parse_type_if_chain_from_body(tr, func.body, tparams={"T"})

  def test_rejects_parallel_chains(self):
    src = """
def f[T](x: T) -> int:
  if T is int:
    return 1
  else:
    return 0
  if T is str:
    return 2
  return 3
"""
    tree = ast.parse(src)
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    with self.assertRaises(ValueError):
      plan_type_if_chain(tr, func)

  def test_rejects_nested_type_if_in_branch(self):
    src = """
def f[T](x: T) -> int:
  if T is int:
    if T is str:
      return 1
    return 2
  else:
    return 0
"""
    tree = ast.parse(src)
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    with self.assertRaises(ValueError):
      plan_type_if_chain(tr, func)

  def test_rejects_list_t_pattern(self):
    src = """
def f[T](x: T) -> int:
  if T is list[T]:
    return 1
  else:
    return 0
"""
    tree = ast.parse(src)
    func = tree.body[0]
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    with self.assertRaises(ValueError):
      plan_type_if_chain(tr, func)

  def test_parses_list_wildcard_pattern(self):
    src = """
def f[T](x: T) -> int:
  if T is list[...]:
    return 1
  else:
    return 0
"""
    tree = ast.parse(src)
    func = tree.body[0]
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    plan = plan_type_if_chain(tr, func)
    self.assertIsNotNone(plan)
    pat = plan.master_chain.branches[0].patterns[0]
    self.assertEqual(pat.cpp_type, "PyList<_Ty0>")
    self.assertEqual(pat.extra_template_params, ("_Ty0",))

  def test_rejects_list_underscore_wildcard(self):
    src = """
def f[T](x: T) -> int:
  if T is list[_]:
    return 1
  else:
    return 0
"""
    tree = ast.parse(src)
    func = tree.body[0]
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    with self.assertRaises(ValueError):
      plan_type_if_chain(tr, func)

  def test_finds_chain_inside_for(self):
    src = """
def tally[T]() -> int:
  n: int = 0
  for i in range(3):
    if T is int:
      n += 1
    elif T is str:
      n += 2
    else:
      pass
  return n
"""
    tree = ast.parse(src)
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    plan = plan_type_if_chain(tr, func)
    self.assertIsNotNone(plan)
    self.assertEqual(len(plan.chains), 1)
    self.assertEqual(plan.master_chain.branches[0].kind, "is")

  def test_parses_and_capture_branch(self):
    src = """
def f[T, _U = ...](x: T) -> int:
  if T is list[_U] and _U in [int, float]:
    return 1
  else:
    return 0
"""
    tree = ast.parse(src)
    func = tree.body[0]
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    plan = plan_type_if_chain(tr, func)
    self.assertIsNotNone(plan)
    br = plan.master_chain.branches[0]
    self.assertEqual(len(br.or_groups), 1)
    self.assertEqual(len(br.or_groups[0]), 2)
    pats = branch_emit_patterns(br, plan.master_chain.type_param)
    cpp_types = sorted(p.cpp_type for p in pats)
    self.assertEqual(sorted(cpp_types), ["PyList<PyFloat>", "PyList<PyInt>"])

  def test_parses_or_branch(self):
    src = """
def f[T]() -> int:
  if T is int or T is float:
    return 1
  else:
    return 0
"""
    tree = ast.parse(src)
    func = tree.body[0]
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    plan = plan_type_if_chain(tr, func)
    self.assertIsNotNone(plan)
    br = plan.master_chain.branches[0]
    self.assertEqual(len(br.or_groups), 2)
    pats = branch_emit_patterns(br, plan.master_chain.type_param)
    self.assertEqual(len(pats), 2)

  def test_rejects_unused_capture(self):
    src = """
def f[T, _U = ...](x: T) -> int:
  if T is int:
    return 1
  else:
    return 0
"""
    tree = ast.parse(src)
    func = tree.body[0]
    tr = Translator("mod", "mod.py")
    tr.type_parser = TypeParser()
    with self.assertRaises(ValueError):
      plan_type_if_chain(tr, func)


class TypeIfEmitTests(unittest.TestCase):
  def test_module_function_emits_pick_struct(self):
    src = """
from py2cpp import *

def pick[T](x: T) -> int:
  if T is int:
    return 1
  elif T is str:
    return 2
  else:
    return 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("__py2cpp_type_if_pick_", cpp)
      self.assertIn("struct __py2cpp_type_if_pick_", cpp)
      self.assertIn("_pick<PyInt,void>", cpp.replace(" ", ""))
      self.assertIn("return __py2cpp_type_if_pick_", cpp)
      self.assertIn("::__call__(", cpp)
      self.assertNotIn("::go(", cpp)
      self.assertNotIn("if (std::is_same", cpp)

  def test_is_not_branch_uses_enable_if(self):
    src = """
from py2cpp import *

def neg[T](x: T) -> int:
  if T is not int:
    return 0
  else:
    return 1
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      compact = cpp.replace(" ", "")
      self.assertIn("enable_if<!std::is_same<T,PyInt>::value", compact)

  def test_missing_else_emits_static_assert(self):
    src = """
from py2cpp import *

def only[T](x: T) -> int:
  if T is int:
    return 1
  elif T is str:
    return 2
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("static_assert(sizeof(T) == 0", cpp)

  def test_for_body_spliced_into_call(self):
    src = """
from py2cpp import *

def tally[T]() -> int:
  n: int = 0
  for i in range(3):
    if T is int:
      n += 1
    else:
      pass
  return n
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("for (int i = 0;", cpp)
      self.assertNotIn("if (std::is_same", cpp)

  def test_list_wildcard_emits_partial_specialization(self):
    src = """
from py2cpp import *

def pick_list[T](x: T) -> int:
  if T is list[int]:
    return 1
  elif T is list[...]:
    return 2
  else:
    return 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      compact = cpp.replace(" ", "")
      self.assertIn("template<>", cpp)
      self.assertIn("pick<PyList<PyInt>,void>", compact)
      self.assertIn("template<typename_Ty0>", compact.replace("\n", ""))
      self.assertIn("pick<PyList<_Ty0>,void>", compact)

  def test_list_wildcard_branch_uses_element_type_param(self):
    src = """
from py2cpp import *

class Box[U]:
  val: int = 0

def pick[T](slot: int) -> int:
  if T is list[...]:
    gs: Box[T.Element] = cast(slot)
    return gs.val
  else:
    return 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      compact = cpp.replace(" ", "")
      self.assertIn("template<typename_Ty0>", compact.replace("\n", ""))
      self.assertIn("pick<PyList<_Ty0>,void>", compact)
      self.assertIn("Box<_Ty0>", compact)
      self.assertNotIn("typenameT::Element", compact)
      self.assertNotIn("Box<typenameT::Element>", compact.replace(" ", ""))

  def test_type_if_prologue_before_dispatch(self):
    src = """
from py2cpp import *

def pick[T](slot: int) -> int:
  if slot == 0:
    return -1
  if T is int:
    return 1
  else:
    return 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("if ((slot == 0))", cpp)
      self.assertIn("return __py2cpp_type_if_pick_", cpp)

  def test_t_in_set_returns_bool_not_concrete_type(self):
    src = """
from py2cpp import *

def uses_arena[T]() -> bool:
  if T in { int, str }:
    return False
  else:
    return True
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      compact = cpp.replace(" ", "")
      self.assertIn("staticPyBool__call__()", compact)
      self.assertIn("returnfalse;", compact)
      self.assertIn("returntrue;", compact)
      self.assertNotIn("staticPyInt__call__()", compact)


if __name__ == "__main__":
  unittest.main()
