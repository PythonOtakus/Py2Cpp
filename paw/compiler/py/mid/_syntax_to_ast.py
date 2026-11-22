"""ExprSyntax / TypeSyntax → ``ast``（过渡：供仍走 ``Translator.visit`` 的 emit）。

不调用 ``ast.parse``；由结构化 IR 直构。
"""
from __future__ import annotations

import host.tree_nodes as ast
from compiler.py.frontend.syntax_nodes import (
  AttributeExpr,
  AttributeTypeSyntax,
  AttributedTypeSyntax,
  BinOpExpr,
  BoolOpExpr,
  CallExpr,
  CallableTypeSyntax,
  CompareExpr,
  DictExpr,
  ExprSyntax,
  GenericApplyTypeSyntax,
  IfExp,
  LambdaExpr,
  LazyTypeSyntax,
  ListExpr,
  LiteralExpr,
  MatMultExpr,
  NameExpr,
  NameTypeSyntax,
  NullableTypeSyntax,
  ParenthesizedTypeSyntax,
  ReferenceTypeSyntax,
  SliceExpr,
  StarredExpr,
  SubscriptExpr,
  TupleExpr,
  TupleTypeSyntax,
  TypeSyntax,
  UnaryOpExpr,
  UnionTypeSyntax,
)

_BINOP = {
  "+": ast.Add(),
  "-": ast.Sub(),
  "*": ast.Mult(),
  "/": ast.Div(),
  "//": ast.FloorDiv(),
  "%": ast.Mod(),
  "**": ast.Pow(),
  "<<": ast.LShift(),
  ">>": ast.RShift(),
  "|": ast.BitOr(),
  "^": ast.BitXor(),
  "&": ast.BitAnd(),
}
_UNARY = {"+": ast.UAdd(), "-": ast.USub(), "~": ast.Invert(), "not": ast.Not()}
_CMP = {
  "==": ast.Eq(),
  "!=": ast.NotEq(),
  "<": ast.Lt(),
  "<=": ast.LtE(),
  ">": ast.Gt(),
  ">=": ast.GtE(),
  "is": ast.Is(),
  "is not": ast.IsNot(),
  "in": ast.In(),
  "not in": ast.NotIn(),
}


def expr_syntax_to_ast(expr: ExprSyntax) -> ast.expr:
  match expr:
    case NameExpr(name=name):
      return ast.Name(id=name, ctx=ast.Load())
    case LiteralExpr(kind=kind, text=text):
      if kind == "none":
        return ast.Constant(value=None)
      if kind == "bool":
        return ast.Constant(value=text in ("True", "true", "1"))
      if kind == "int":
        return ast.Constant(value=int(text, 0))
      if kind == "float":
        return ast.Constant(value=float(text))
      if kind in ("bytes", "byte", "bstr") or (
        kind == "str" and len(text) >= 2 and text[0] == "b" and text[1] in ("'", '"')
      ):
        # ``b""`` / ``b''``：lexer 可能标成 str 且 text 含前缀 b
        raw = text[1:] if text.startswith("b") and len(text) > 1 else text
        return ast.Constant(value=_unquote(raw).encode("utf-8"))
      if kind == "str":
        # 源文本整段 ``b"…"`` 误标为 str
        if len(text) >= 3 and text[0] == "b" and text[1] in ("'", '"'):
          return ast.Constant(value=_unquote(text[1:]).encode("utf-8"))
        return ast.Constant(value=_unquote(text))
      # 裸 ``b""`` 落入 default
      if len(text) >= 2 and text[0] == "b" and text[1] in ("'", '"'):
        return ast.Constant(value=_unquote(text[1:]).encode("utf-8"))
      return ast.Constant(value=text)
    case AttributeExpr(value=value, attr=attr):
      return ast.Attribute(
        value=expr_syntax_to_ast(value), attr=attr, ctx=ast.Load()
      )
    case CallExpr(func=func, args=args, keywords=kws):
      return ast.Call(
        func=expr_syntax_to_ast(func),
        args=[expr_syntax_to_ast(a) for a in args],
        keywords=[
          ast.keyword(arg=k, value=expr_syntax_to_ast(v)) for k, v in kws
        ],
      )
    case BinOpExpr(left=left, op=op, right=right):
      aop = _BINOP.get(op)
      if aop is None:
        raise ValueError(f"unsupported binop: {op}")
      return ast.BinOp(
        left=expr_syntax_to_ast(left), op=aop, right=expr_syntax_to_ast(right)
      )
    case UnaryOpExpr(op=op, operand=operand):
      uop = _UNARY.get(op)
      if uop is None:
        raise ValueError(f"unsupported unary: {op}")
      return ast.UnaryOp(op=uop, operand=expr_syntax_to_ast(operand))
    case CompareExpr(left=left, ops=ops, comparators=comps):
      return ast.Compare(
        left=expr_syntax_to_ast(left),
        ops=[_CMP[o] for o in ops],
        comparators=[expr_syntax_to_ast(c) for c in comps],
      )
    case BoolOpExpr(op=op, values=values):
      return ast.BoolOp(
        op=ast.And() if op == "and" else ast.Or(),
        values=[expr_syntax_to_ast(v) for v in values],
      )
    case SubscriptExpr(value=value, slice=sl):
      return ast.Subscript(
        value=expr_syntax_to_ast(value),
        slice=expr_syntax_to_ast(sl),
        ctx=ast.Load(),
      )
    case MatMultExpr(left=left, right=right):
      return ast.BinOp(
        left=expr_syntax_to_ast(left),
        op=ast.MatMult(),
        right=expr_syntax_to_ast(right),
      )
    case ListExpr(elts=elts):
      return ast.List(elts=[expr_syntax_to_ast(e) for e in elts], ctx=ast.Load())
    case TupleExpr(elts=elts):
      return ast.Tuple(
        elts=[expr_syntax_to_ast(e) for e in elts], ctx=ast.Load()
      )
    case DictExpr(keys=keys, values=values):
      return ast.Dict(
        keys=[None if k is None else expr_syntax_to_ast(k) for k in keys],
        values=[expr_syntax_to_ast(v) for v in values],
      )
    case SliceExpr(lower=lo, upper=hi, step=step):
      return ast.Slice(
        lower=None if lo is None else expr_syntax_to_ast(lo),
        upper=None if hi is None else expr_syntax_to_ast(hi),
        step=None if step is None else expr_syntax_to_ast(step),
      )
    case IfExp(body=body, test=test, orelse=orelse):
      return ast.IfExp(
        test=expr_syntax_to_ast(test),
        body=expr_syntax_to_ast(body),
        orelse=expr_syntax_to_ast(orelse),
      )
    case LambdaExpr(params_source=ps, body=body):
      # 过渡：参数原文再走一层 expression 不合适；保留 args 为空 + body
      return ast.Lambda(
        args=ast.arguments(
          posonlyargs=[],
          args=[],
          vararg=None,
          kwonlyargs=[],
          kw_defaults=[],
          kwarg=None,
          defaults=[],
        ),
        body=expr_syntax_to_ast(body),
      )
    case StarredExpr(value=value):
      return ast.Starred(value=expr_syntax_to_ast(value), ctx=ast.Load())
    case _:
      raise TypeError(f"unsupported ExprSyntax: {type(expr)!r}")


def _name_or_nttp_constant(name: str) -> ast.expr:
  """``NameTypeSyntax`` 可能承载 NTTP 字面量 ``0`` / ``1.5``（非标识符）。"""
  # 与 CPython ``ast.parse`` 对齐：``None``/``True``/``False`` → Constant。
  # 否则 ``T | None`` 变成 ``BinOp(..., Name("None"))``，analyzer 匹配不到 optional → ``void``。
  if name == "None":
    return ast.Constant(value=None)
  if name == "True":
    return ast.Constant(value=True)
  if name == "False":
    return ast.Constant(value=False)
  if name.isidentifier():
    return ast.Name(id=name, ctx=ast.Load())
  # ``Self._dim`` / ``Cls.N`` → Attribute 链
  if "." in name and all(p.isidentifier() for p in name.split(".")):
    parts = name.split(".")
    node: ast.expr = ast.Name(id=parts[0], ctx=ast.Load())
    for part in parts[1:]:
      node = ast.Attribute(value=node, attr=part, ctx=ast.Load())
    return node
  try:
    if name.startswith(("0x", "0X", "0o", "0O", "0b", "0B")) or (
      name.lstrip("+-").isdigit()
    ):
      return ast.Constant(value=int(name, 0))
  except ValueError:
    pass
  try:
    return ast.Constant(value=float(name))
  except ValueError:
    return ast.Name(id=name, ctx=ast.Load())


def type_syntax_to_ast(ty: TypeSyntax) -> ast.expr:
  match ty:
    case NameTypeSyntax(name=name):
      return _name_or_nttp_constant(name)
    case GenericApplyTypeSyntax(head=head, arguments=args):
      head_ast = type_syntax_to_ast(head)

      def _colon_name_to_slice(name: str) -> ast.Slice | None:
        if name == ":" or name.startswith(":"):
          upper_src = name[1:]
          upper = _name_or_nttp_constant(upper_src) if upper_src else None
          return ast.Slice(lower=None, upper=upper, step=None)
        return None

      # ``T[:N]`` / ``T[:]`` / ``T[:N, :M]``：type_parse 暂把切片收成 Name(':N')
      if args and all(
        isinstance(a, NameTypeSyntax) and (a.name == ":" or a.name.startswith(":"))
        for a in args
      ):
        slices = [_colon_name_to_slice(a.name) for a in args]  # type: ignore[union-attr]
        assert all(s is not None for s in slices)
        sl_expr: ast.expr = (
          slices[0]  # type: ignore[assignment]
          if len(slices) == 1
          else ast.Tuple(elts=list(slices), ctx=ast.Load())  # type: ignore[arg-type]
        )
        return ast.Subscript(value=head_ast, slice=sl_expr, ctx=ast.Load())
      arg_asts = [type_syntax_to_ast(a) for a in args]
      sl: ast.expr = (
        arg_asts[0] if len(arg_asts) == 1 else ast.Tuple(elts=arg_asts, ctx=ast.Load())
      )
      return ast.Subscript(value=head_ast, slice=sl, ctx=ast.Load())
    case ReferenceTypeSyntax(inner=inner) | LazyTypeSyntax(inner=inner):
      # 过渡：ref/lazy 以 Name 包装不完整；用 Attribute 式标记少见，落到 unparse 源
      from compiler.py.frontend.type_parse import type_syntax_to_source

      src = type_syntax_to_source(ty)
      # 仅标识符
      if src.isidentifier():
        return ast.Name(id=src, ctx=ast.Load())
      # list[T] 等已由 Generic 覆盖；其余用 Name 片段
      return ast.Name(id=src.replace(" ", "_"), ctx=ast.Load())
    case NullableTypeSyntax(inner=inner):
      return type_syntax_to_ast(inner)
    case ParenthesizedTypeSyntax(inner=inner):
      return type_syntax_to_ast(inner)
    case TupleTypeSyntax(items=items):
      return ast.Tuple(
        elts=[type_syntax_to_ast(x) for x in items], ctx=ast.Load()
      )
    case UnionTypeSyntax(options=opts):
      node = type_syntax_to_ast(opts[0])
      for opt in opts[1:]:
        node = ast.BinOp(left=node, op=ast.BitOr(), right=type_syntax_to_ast(opt))
      return node
    case CallableTypeSyntax() | AttributeTypeSyntax() | AttributedTypeSyntax():
      from compiler.py.frontend.type_parse import type_syntax_to_source

      src = type_syntax_to_source(ty)
      if src.isidentifier():
        return ast.Name(id=src, ctx=ast.Load())
      raise ValueError(f"type_syntax_to_ast: complex type {src!r}")
    case _:
      raise TypeError(f"unsupported TypeSyntax: {type(ty)!r}")


def _unquote(text: str) -> str:
  if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
    return text[1:-1]
  return text
