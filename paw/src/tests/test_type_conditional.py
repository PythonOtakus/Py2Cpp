"""条件类型别名编译期求值单测。"""
import ast
import unittest

from src.analysis.analyzer import TypeParser
from src.analysis.ir import TypeAliasInfo, cpp_ident
from src.analysis.type_extract import NEVER_CPP, evaluate_conditional_alias, try_match_pattern
from src.passes.type_conditional import plan_conditional_alias
from src.passes.type_if import TypePattern
from src.translator import Translator


def _ifexp(test: ast.expr, body: ast.expr, orelse: ast.expr) -> ast.IfExp:
  return ast.IfExp(test=test, body=body, orelse=orelse)


def _is_test(name: str, pattern: ast.expr) -> ast.Compare:
  return ast.Compare(
    left=ast.Name(id=name, ctx=ast.Load()),
    ops=[ast.Is()],
    comparators=[pattern],
  )


def _list_elem_of_alias(*, else_name: str = "T") -> TypeAliasInfo:
  cap = "_V"
  return TypeAliasInfo(
    name="ListElemOf",
    value=_ifexp(
      _is_test("T", ast.Subscript(
        value=ast.Name(id="list", ctx=ast.Load()),
        slice=ast.Name(id=cap, ctx=ast.Load()),
        ctx=ast.Load(),
      )),
      ast.Name(id=cap, ctx=ast.Load()),
      ast.Name(id=else_name, ctx=ast.Load()),
    ),
    type_params=("T", cap),
    capture_params=(cap,),
    is_conditional=True,
  )


def _val_of_alias(*, else_name: str = "T") -> TypeAliasInfo:
  cap_v = "_V"
  cap_w = "_W"
  return TypeAliasInfo(
    name="ValOf",
    value=_ifexp(
      _is_test("T", ast.Subscript(
        value=ast.Name(id="list", ctx=ast.Load()),
        slice=ast.Name(id=cap_v, ctx=ast.Load()),
        ctx=ast.Load(),
      )),
      ast.Name(id=cap_v, ctx=ast.Load()),
      _ifexp(
        _is_test("T", ast.Subscript(
          value=ast.Name(id="dict", ctx=ast.Load()),
          slice=ast.Tuple(
            elts=[
              ast.Name(id="str", ctx=ast.Load()),
              ast.Name(id=cap_w, ctx=ast.Load()),
            ],
            ctx=ast.Load(),
          ),
          ctx=ast.Load(),
        )),
        ast.Name(id=cap_w, ctx=ast.Load()),
        ast.Name(id=else_name, ctx=ast.Load()),
      ),
    ),
    type_params=("T", cap_v, cap_w),
    capture_params=(cap_v, cap_w),
    is_conditional=True,
  )


class TestTypeExtract(unittest.TestCase):
  def test_structural_match_binds_capture(self):
    pat = TypePattern("PyList<_V>", ("_V",))
    binds = try_match_pattern("PyList<PyInt>", pat)
    self.assertEqual(binds, {"_V": "PyInt"})

  def test_exact_match(self):
    pat = TypePattern("PyInt", ())
    self.assertEqual(try_match_pattern("PyInt", pat), {})
    self.assertIsNone(try_match_pattern("PyStr", pat))


class TestConditionalAliasPlan(unittest.TestCase):
  def _parser_with_alias(self, alias: TypeAliasInfo) -> tuple[TypeParser, Translator]:
    tr = Translator("mod", "mod.py")
    tr.module_order = ["m"]
    tr.module_asts = {"m": ast.Module(body=[], type_ignores=[])}
    tp = TypeParser()
    tp.set_translator(tr)
    tp.set_type_aliases({alias.name: alias})
    tr.type_parser = tp
    return tp, tr

  def test_list_elem_of_list_int(self):
    alias = _list_elem_of_alias()
    _, tr = self._parser_with_alias(alias)
    plan = plan_conditional_alias(tr, alias)
    cpp = evaluate_conditional_alias(
      tr, alias, plan, {"T": "PyList<PyInt>"}, set(),
    )
    self.assertEqual(cpp, "PyInt")

  def test_list_elem_of_str_fallback(self):
    alias = _list_elem_of_alias()
    _, tr = self._parser_with_alias(alias)
    plan = plan_conditional_alias(tr, alias)
    cpp = evaluate_conditional_alias(
      tr, alias, plan, {"T": "PyStr"}, set(),
    )
    self.assertEqual(cpp, "PyStr")

  def test_never_else(self):
    alias = _list_elem_of_alias(else_name="Never")
    _, tr = self._parser_with_alias(alias)
    plan = plan_conditional_alias(tr, alias)
    cpp = evaluate_conditional_alias(
      tr, alias, plan, {"T": "PyStr"}, set(),
    )
    self.assertEqual(cpp, NEVER_CPP)

  def test_val_of_dict_str_int(self):
    alias = _val_of_alias()
    _, tr = self._parser_with_alias(alias)
    plan = plan_conditional_alias(tr, alias)
    cpp = evaluate_conditional_alias(
      tr, alias, plan, {"T": "PyDict<PyStr, PyInt>"}, set(),
    )
    self.assertEqual(cpp, "PyInt")

  def test_rejects_capture_without_underscore(self):
    alias = TypeAliasInfo(
      name="Bad",
      value=_ifexp(
        _is_test("T", ast.Name(id="int", ctx=ast.Load())),
        ast.Name(id="U", ctx=ast.Load()),
        ast.Name(id="T", ctx=ast.Load()),
      ),
      type_params=("T", "U"),
      capture_params=("U",),
      is_conditional=True,
    )
    _, tr = self._parser_with_alias(alias)
    with self.assertRaises(ValueError) as ctx:
      plan_conditional_alias(tr, alias)
    self.assertIn("_X", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
