"""P0：类型表面与值下标 / MatMult 表达式分叉。"""
from __future__ import annotations

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.source import FileId
from compiler.py.frontend.syntax_nodes import (
  AttributedTypeSyntax,
  CallableTypeSyntax,
  GenericApplyTypeSyntax,
  LazyTypeSyntax,
  NameTypeSyntax,
  NullableTypeSyntax,
  ReferenceTypeSyntax,
)
from compiler.py.frontend.type_parse import (
  parse_type,
  type_syntax_to_legacy_annotation,
  type_syntax_to_source,
)


def _parse(s: str):
  toks = Lexer(s, FileId(0)).tokenize()
  ty, i = parse_type(toks, 0, source=s)
  return ty, i, toks


def test_generic_apply_not_subscript_expr():
  ty, _, _ = _parse("list[int]")
  assert isinstance(ty, GenericApplyTypeSyntax)
  assert isinstance(ty.head, NameTypeSyntax) and ty.head.name == "list"
  assert len(ty.arguments) == 1
  assert isinstance(ty.arguments[0], NameTypeSyntax)
  assert type_syntax_to_source(ty) == "list[int]"


def test_ref_and_lazy_ref():
  ty, _, _ = _parse("ref StreamReader")
  assert isinstance(ty, ReferenceTypeSyntax)
  assert type_syntax_to_legacy_annotation(ty) == "StreamReader @ref"

  ty2, _, _ = _parse("lazy ref int")
  assert isinstance(ty2, LazyTypeSyntax)
  assert isinstance(ty2.inner, ReferenceTypeSyntax)
  assert type_syntax_to_legacy_annotation(ty2) == "int @ref @lazy"


def test_nullable_and_attr_not_matmult_expr():
  ty, _, _ = _parse("Node?")
  assert isinstance(ty, NullableTypeSyntax)

  ty2, _, _ = _parse("int @thread_local")
  assert isinstance(ty2, AttributedTypeSyntax)
  assert ty2.attributes[0].name == "thread_local"
  assert type_syntax_to_source(ty2) == "int @thread_local"


def test_function_arrow_type():
  """裸箭头 ≡ C 函数指针（旧 Function[[…],R]）。"""
  ty, _, _ = _parse("(int, float) -> str")
  assert isinstance(ty, CallableTypeSyntax)
  assert not ty.is_py_callable
  assert len(ty.parameter_types) == 2
  assert type_syntax_to_source(ty) == "(int, float) -> str"
  assert type_syntax_to_legacy_annotation(ty) == "Function[[int, float], str]"

  ty1, _, _ = _parse("int -> str")
  assert isinstance(ty1, CallableTypeSyntax) and not ty1.is_py_callable
  assert type_syntax_to_source(ty1) == "int -> str"
  assert type_syntax_to_legacy_annotation(ty1) == "Function[[int], str]"


def test_py_callable_arrow_type():
  """``Callable[arrow]`` ≡ PyCallable 槽（旧 Callable[[…],R]）。"""
  ty, _, _ = _parse("Callable[int -> str]")
  assert isinstance(ty, CallableTypeSyntax)
  assert ty.is_py_callable
  assert type_syntax_to_source(ty) == "Callable[int -> str]"
  assert type_syntax_to_legacy_annotation(ty) == "Callable[[int], str]"


def test_reject_legacy_function_callable_subscript():
  ty, _, _ = _parse("Function[[int], str]")
  assert ty is None
  ty2, _, _ = _parse("Callable[[int], str]")
  assert ty2 is None


def test_slice_type_char():
  ty, _, _ = _parse("char[:]")
  assert isinstance(ty, GenericApplyTypeSyntax)
  assert type_syntax_to_source(ty) == "char[:]"


def test_multi_dim_slice_and_nttp():
  ty, _, _ = _parse("int[:,:]")
  assert isinstance(ty, GenericApplyTypeSyntax)
  assert type_syntax_to_source(ty) == "int[:, :]"
  ty2, _, _ = _parse("list[str, 0]")
  assert type_syntax_to_source(ty2) == "list[str, 0]"
  ty3, _, _ = _parse("Scalar[:Self._dim]")
  assert type_syntax_to_source(ty3) == "Scalar[:Self._dim]"


def test_union_type_pipe():
  ty, _, _ = _parse("list[int] | None")
  assert type_syntax_to_source(ty) == "list[int] | None"


def test_delegate_and_native_bodyless():
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.syntax_nodes import FunctionDecl

  src = (
    "delegate FuncDelegate[T](x: T) -> T\n"
    "native def foo(cb: int -> None) -> int\n"
  )
  mod = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  fns = [x for x in mod.items if isinstance(x, FunctionDecl)]
  assert len(fns) == 2
  assert fns[0].is_delegate and fns[0].type_params_source == "[T]"
  assert fns[1].is_native and fns[1].body_source == "..."


def test_annassign_attribute_self():
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.syntax_nodes import (
    AnnAssignStmt,
    AttributeExpr,
    ClassDecl,
    FunctionDecl,
    OpaqueStmtSyntax,
  )

  src = "class C:\n  def __init__(self):\n    self._n: int = 0\n    ...\n"
  mod = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  cls = [x for x in mod.items if isinstance(x, ClassDecl)][0]
  fn = [m for m in cls.members if isinstance(m, FunctionDecl)][0]
  assert not any(isinstance(s, OpaqueStmtSyntax) for s in fn.body)
  ann = [s for s in fn.body if isinstance(s, AnnAssignStmt)][0]
  assert isinstance(ann.target, AttributeExpr) and ann.target.attr == "_n"


def test_tuple_assign_and_bitwise():
  from compiler.py.frontend.parser import _try_parse_function
  from compiler.py.frontend.syntax_nodes import AssignStmt, BinOpExpr, OpaqueStmtSyntax, TupleExpr

  src = "def f():\n  ra, rb = rb, ra\n  x = a | b\n"
  fn, _ = _try_parse_function(Lexer(src, FileId(0)).tokenize(), src, 0, [])
  assert fn is not None
  assert not any(isinstance(s, OpaqueStmtSyntax) for s in fn.body)
  a0, a1 = fn.body[0], fn.body[1]
  assert isinstance(a0, AssignStmt) and isinstance(a0.target, TupleExpr)
  assert isinstance(a0.value, TupleExpr)
  assert isinstance(a1, AssignStmt) and isinstance(a1.value, BinOpExpr)


def test_property_block_expand():
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.syntax_nodes import ClassDecl, FunctionDecl

  src = (
    "class C:\n"
    "  property pos:\n"
    "    def __get__(self) -> int:\n"
    "      return 1\n"
    "    def __set__(self, value: int):\n"
    "      pass\n"
  )
  mod = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  cls = [x for x in mod.items if isinstance(x, ClassDecl)][0]
  fns = [m for m in cls.members if isinstance(m, FunctionDecl)]
  assert len(fns) == 2
  assert fns[0].name == "pos" and fns[0].is_property
  assert fns[1].name == "pos" and "setter" in fns[1].decorators_source


def test_reject_ref_lazy_order():
  ty, _, _ = _parse("ref lazy int")
  assert ty is None


def test_function_return_wired():
  from compiler.py.frontend.parser import parse_tokens

  src = "def f(x: list[int]) -> ref str:\n  return x\n"
  toks = Lexer(src, FileId(0)).tokenize()
  mod = parse_tokens(toks, src)
  from compiler.py.frontend.syntax_nodes import FunctionDecl

  fns = [x for x in mod.items if isinstance(x, FunctionDecl)]
  assert len(fns) == 1
  assert isinstance(fns[0].return_type, ReferenceTypeSyntax)
  assert fns[0].return_source == "ref str"
