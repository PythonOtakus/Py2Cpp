"""函数体语句/表达式子集（P2+）：值下标与 MatMult 与类型节点分叉。"""
from __future__ import annotations

from .source import Span
from .syntax_nodes import (
  AnnAssignStmt,
  AssertStmt,
  AssignStmt,
  AttributeExpr,
  AugAssignStmt,
  BinOpExpr,
  BoolOpExpr,
  BreakStmt,
  CallExpr,
  CompareExpr,
  ContinueStmt,
  DictExpr,
  ExceptHandler,
  ExprStmt,
  ExprSyntax,
  ForStmt,
  GlobalStmt,
  IfExp,
  IfStmt,
  LambdaExpr,
  ListExpr,
  LiteralExpr,
  MatchCase,
  MatchStmt,
  MatMultExpr,
  NameExpr,
  NonlocalStmt,
  OpaqueStmtSyntax,
  PassStmt,
  RaiseStmt,
  ReturnStmt,
  SliceExpr,
  StarredExpr,
  StmtSyntax,
  SubscriptExpr,
  TryStmt,
  TupleExpr,
  UnaryOpExpr,
  WhileStmt,
  WithItem,
  WithStmt,
)
from .tokens import Token, TokenKind
from .type_parse import parse_type

_CMP = frozenset({"==", "!=", "<", "<=", ">", ">=", "is", "in", "not"})
_ADD = frozenset({"+", "-"})
_MUL = frozenset({"*", "/", "//", "%", "@"})
_AUG = frozenset(
  {
    "+=",
    "-=",
    "*=",
    "/=",
    "//=",
    "%=",
    "@=",
    "&=",
    "|=",
    "^=",
    "<<=",
    ">>=",
    "**=",
  }
)


def parse_suite(
  tokens: list[Token],
  i: int,
  end_i: int,
  *,
  source: str,
) -> tuple[list[StmtSyntax], int]:
  """解析当前缩进块内语句；遇到 ``DEDENT`` 结束（不吞掉外层语句）。"""
  stmts: list[StmtSyntax] = []
  while i < end_i:
    if tokens[i].kind is TokenKind.NEWLINE:
      i += 1
      continue
    if tokens[i].kind is TokenKind.INDENT:
      i += 1
      continue
    if tokens[i].kind is TokenKind.DEDENT:
      return stmts, i
    if tokens[i].kind is TokenKind.COMMENT:
      i += 1
      continue
    st, i = parse_stmt(tokens, i, end_i, source=source)
    if st is not None:
      stmts.append(st)
  return stmts, i


def parse_stmt(
  tokens: list[Token],
  i: int,
  end_i: int,
  *,
  source: str,
) -> tuple[StmtSyntax | None, int]:
  n = end_i
  if i >= n:
    return None, i
  start = tokens[i].span

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "pass":
    i += 1
    return PassStmt(start), i

  # 存根体 ``...``（abstract / protocol / native 残留）
  if tokens[i].kind is TokenKind.ELLIPSIS:
    i += 1
    return PassStmt(start), i

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "break":
    i += 1
    return BreakStmt(start), i

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "continue":
    i += 1
    return ContinueStmt(start), i

  if tokens[i].kind is TokenKind.NAME and tokens[i].text in ("global", "nonlocal"):
    kind = tokens[i].text
    i += 1
    names: list[str] = []
    while i < n and tokens[i].kind is TokenKind.NAME:
      names.append(tokens[i].text)
      i += 1
      if i < n and tokens[i].kind is TokenKind.COMMA:
        i += 1
        continue
      break
    end = tokens[i - 1].span.end if names else start.end
    span = Span(start.file_id, start.start, end)
    if kind == "global":
      return GlobalStmt(names, span), i
    return NonlocalStmt(names, span), i

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "return":
    i += 1
    if i < n and tokens[i].kind not in (
      TokenKind.NEWLINE,
      TokenKind.DEDENT,
      TokenKind.END,
    ):
      val, i = _parse_expr_list(tokens, i, source=source)
      return ReturnStmt(val, Span(start.file_id, start.start, (val.span if val else start).end)), i
    return ReturnStmt(None, start), i

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "raise":
    i += 1
    if i < n and tokens[i].kind not in (
      TokenKind.NEWLINE,
      TokenKind.DEDENT,
      TokenKind.END,
    ):
      val, i = parse_expr(tokens, i, source=source)
      return RaiseStmt(val, Span(start.file_id, start.start, (val.span if val else start).end)), i
    return RaiseStmt(None, start), i

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "if":
    return _parse_if(tokens, i, end_i, source=source)

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "while":
    return _parse_while(tokens, i, end_i, source=source)

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "for":
    return _parse_for(tokens, i, end_i, source=source)

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "match":
    return _parse_match(tokens, i, end_i, source=source)

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "try":
    return _parse_try(tokens, i, end_i, source=source)

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "with":
    return _parse_with(tokens, i, end_i, source=source)

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "assert":
    return _parse_assert(tokens, i, end_i, source=source)

  # AnnAssign: target : type [= expr]（含 ``self.x: T = v``）
  ann_i = i
  ann_tgt, ann_j = _parse_postfix(tokens, i, source=source)
  if (
    ann_tgt is not None
    and ann_j < n
    and tokens[ann_j].kind is TokenKind.COLON
    and isinstance(ann_tgt, (NameExpr, AttributeExpr, SubscriptExpr))
  ):
    j = ann_j + 1
    ann, j = parse_type(tokens, j, source=source)
    val = None
    if j < n and tokens[j].kind is TokenKind.EQ:
      j += 1
      val, j = parse_expr(tokens, j, source=source)
    end = val.span if val else (ann.span if ann else ann_tgt.span)
    return (
      AnnAssignStmt(
        ann_tgt, ann, val, Span(ann_tgt.span.file_id, ann_tgt.span.start, end.end)
      ),
      j,
    )
  _ = ann_i

  # 赋值目标（支持 ``a, b = …``）；否则完整表达式语句
  expr_i = i
  tleft, tj = _parse_target(tokens, i, source=source)
  if tleft is not None and tj < n and (
    tokens[tj].kind is TokenKind.EQ
    or (tokens[tj].kind is TokenKind.OP and tokens[tj].text in _AUG)
  ):
    if tokens[tj].kind is TokenKind.EQ:
      tj += 1
      right, tj = _parse_expr_list(tokens, tj, source=source)
      if right is None:
        return OpaqueStmtSyntax(
          source[tokens[expr_i].span.start : tokens[min(tj, n - 1)].span.end],
          start,
        ), tj
      return AssignStmt(
        tleft, right, Span(tleft.span.file_id, tleft.span.start, right.span.end)
      ), tj
    op = tokens[tj].text
    tj += 1
    right, tj = parse_expr(tokens, tj, source=source)
    if right is None:
      return OpaqueStmtSyntax(
        source[tokens[expr_i].span.start : tokens[min(tj, n - 1)].span.end],
        start,
      ), tj
    return AugAssignStmt(
      tleft, op, right, Span(tleft.span.file_id, tleft.span.start, right.span.end)
    ), tj

  left, j = parse_expr(tokens, i, source=source)
  if left is None:
    vs = i
    while i < n and tokens[i].kind not in (TokenKind.NEWLINE, TokenKind.DEDENT):
      i += 1
    if i > vs:
      src = source[tokens[vs].span.start : tokens[i - 1].span.end]
      return OpaqueStmtSyntax(
        src,
        Span(tokens[vs].span.file_id, tokens[vs].span.start, tokens[i - 1].span.end),
      ), i
    return None, i + 1

  return ExprStmt(left, left.span), j


def parse_expr(
  tokens: list[Token], i: int, *, source: str
) -> tuple[ExprSyntax | None, int]:
  left, i = _parse_or(tokens, i, source=source)
  if left is None:
    return None, i
  # ternary: body if test else orelse
  if (
    i < len(tokens)
    and tokens[i].kind is TokenKind.NAME
    and tokens[i].text == "if"
  ):
    i += 1
    test, i = _parse_or(tokens, i, source=source)
    if (
      test is not None
      and i < len(tokens)
      and tokens[i].kind is TokenKind.NAME
      and tokens[i].text == "else"
    ):
      i += 1
      orelse, i = parse_expr(tokens, i, source=source)
      if orelse is not None:
        return (
          IfExp(
            left,
            test,
            orelse,
            Span(left.span.file_id, left.span.start, orelse.span.end),
          ),
          i,
        )
  return left, i


def _parse_expr_list(
  tokens: list[Token], i: int, *, source: str
) -> tuple[ExprSyntax | None, int]:
  """赋值右侧：``a`` 或 ``a, b, c``（无括号元组）。"""
  first, i = parse_expr(tokens, i, source=source)
  if first is None:
    return None, i
  if i >= len(tokens) or tokens[i].kind is not TokenKind.COMMA:
    return first, i
  elts = [first]
  while i < len(tokens) and tokens[i].kind is TokenKind.COMMA:
    i += 1
    if i < len(tokens) and tokens[i].kind in (
      TokenKind.NEWLINE,
      TokenKind.DEDENT,
      TokenKind.END,
      TokenKind.RPAR,
      TokenKind.RSQB,
      TokenKind.RBRACE,
    ):
      break
    el, i = parse_expr(tokens, i, source=source)
    if el is None:
      break
    elts.append(el)
  return (
    TupleExpr(elts, Span(first.span.file_id, first.span.start, elts[-1].span.end)),
    i,
  )


def _parse_or(tokens, i, *, source):
  left, i = _parse_and(tokens, i, source=source)
  if left is None:
    return None, i
  values = [left]
  while (
    i < len(tokens)
    and tokens[i].kind is TokenKind.NAME
    and tokens[i].text == "or"
  ):
    i += 1
    right, i = _parse_and(tokens, i, source=source)
    if right is None:
      break
    values.append(right)
  if len(values) == 1:
    return values[0], i
  return BoolOpExpr("or", values, Span(values[0].span.file_id, values[0].span.start, values[-1].span.end)), i


def _parse_and(tokens, i, *, source):
  left, i = _parse_not(tokens, i, source=source)
  if left is None:
    return None, i
  values = [left]
  while (
    i < len(tokens)
    and tokens[i].kind is TokenKind.NAME
    and tokens[i].text == "and"
  ):
    i += 1
    right, i = _parse_not(tokens, i, source=source)
    if right is None:
      break
    values.append(right)
  if len(values) == 1:
    return values[0], i
  return BoolOpExpr("and", values, Span(values[0].span.file_id, values[0].span.start, values[-1].span.end)), i


def _parse_not(tokens, i, *, source):
  if i < len(tokens) and tokens[i].kind is TokenKind.NAME and tokens[i].text == "not":
    sp = tokens[i].span
    i += 1
    operand, i = _parse_not(tokens, i, source=source)
    if operand is None:
      return None, i
    return UnaryOpExpr("not", operand, Span(sp.file_id, sp.start, operand.span.end)), i
  return _parse_compare(tokens, i, source=source)


def _parse_compare(tokens, i, *, source):
  left, i = _parse_bitor(tokens, i, source=source)
  if left is None:
    return None, i
  ops: list[str] = []
  comps: list[ExprSyntax] = []
  while i < len(tokens):
    op = None
    if tokens[i].kind is TokenKind.OP and tokens[i].text in _CMP:
      op = tokens[i].text
      i += 1
    elif tokens[i].kind is TokenKind.NAME and tokens[i].text in ("is", "in", "not"):
      if tokens[i].text == "is":
        i += 1
        if (
          i < len(tokens)
          and tokens[i].kind is TokenKind.NAME
          and tokens[i].text == "not"
        ):
          op = "is not"
          i += 1
        else:
          op = "is"
      elif tokens[i].text == "not":
        if (
          i + 1 < len(tokens)
          and tokens[i + 1].kind is TokenKind.NAME
          and tokens[i + 1].text == "in"
        ):
          op = "not in"
          i += 2
        else:
          break
      else:
        op = "in"
        i += 1
    else:
      break
    right, i = _parse_bitor(tokens, i, source=source)
    if right is None:
      break
    ops.append(op)
    comps.append(right)
  if not ops:
    return left, i
  return CompareExpr(
    left, ops, comps, Span(left.span.file_id, left.span.start, comps[-1].span.end)
  ), i


def _parse_bitor(tokens, i, *, source):
  left, i = _parse_bitxor(tokens, i, source=source)
  if left is None:
    return None, i
  while i < len(tokens) and tokens[i].kind is TokenKind.OP and tokens[i].text == "|":
    i += 1
    right, i = _parse_bitxor(tokens, i, source=source)
    if right is None:
      break
    left = BinOpExpr(left, "|", right, Span(left.span.file_id, left.span.start, right.span.end))
  return left, i


def _parse_bitxor(tokens, i, *, source):
  left, i = _parse_bitand(tokens, i, source=source)
  if left is None:
    return None, i
  while i < len(tokens) and tokens[i].kind is TokenKind.OP and tokens[i].text == "^":
    i += 1
    right, i = _parse_bitand(tokens, i, source=source)
    if right is None:
      break
    left = BinOpExpr(left, "^", right, Span(left.span.file_id, left.span.start, right.span.end))
  return left, i


def _parse_bitand(tokens, i, *, source):
  left, i = _parse_shift(tokens, i, source=source)
  if left is None:
    return None, i
  while i < len(tokens) and tokens[i].kind is TokenKind.OP and tokens[i].text == "&":
    i += 1
    right, i = _parse_shift(tokens, i, source=source)
    if right is None:
      break
    left = BinOpExpr(left, "&", right, Span(left.span.file_id, left.span.start, right.span.end))
  return left, i


def _parse_shift(tokens, i, *, source):
  left, i = _parse_add(tokens, i, source=source)
  if left is None:
    return None, i
  while (
    i < len(tokens)
    and tokens[i].kind is TokenKind.OP
    and tokens[i].text in ("<<", ">>")
  ):
    op = tokens[i].text
    i += 1
    right, i = _parse_add(tokens, i, source=source)
    if right is None:
      break
    left = BinOpExpr(left, op, right, Span(left.span.file_id, left.span.start, right.span.end))
  return left, i


def _parse_add(tokens, i, *, source):
  left, i = _parse_mul(tokens, i, source=source)
  if left is None:
    return None, i
  while i < len(tokens) and tokens[i].kind is TokenKind.OP and tokens[i].text in _ADD:
    op = tokens[i].text
    i += 1
    right, i = _parse_mul(tokens, i, source=source)
    if right is None:
      break
    left = BinOpExpr(left, op, right, Span(left.span.file_id, left.span.start, right.span.end))
  return left, i


def _parse_mul(tokens, i, *, source):
  left, i = _parse_unary(tokens, i, source=source)
  if left is None:
    return None, i
  n = len(tokens)
  while i < n:
    # ``@`` 词法为 TokenKind.AT；其余乘除为 OP
    if tokens[i].kind is TokenKind.AT:
      op = "@"
    elif tokens[i].kind is TokenKind.OP and tokens[i].text in _MUL:
      op = tokens[i].text
    else:
      break
    save = i
    i += 1
    right, i = _parse_unary(tokens, i, source=source)
    if right is None:
      return left, save
    if op == "@":
      left = MatMultExpr(left, right, Span(left.span.file_id, left.span.start, right.span.end))
    else:
      left = BinOpExpr(left, op, right, Span(left.span.file_id, left.span.start, right.span.end))
  return left, i


def _parse_unary(tokens, i, *, source):
  if i < len(tokens) and tokens[i].kind is TokenKind.OP and tokens[i].text in ("+", "-", "~"):
    sp = tokens[i].span
    op = tokens[i].text
    i += 1
    operand, i = _parse_unary(tokens, i, source=source)
    if operand is None:
      return None, i
    return UnaryOpExpr(op, operand, Span(sp.file_id, sp.start, operand.span.end)), i
  return _parse_power(tokens, i, source=source)


def _parse_power(tokens, i, *, source):
  left, i = _parse_postfix(tokens, i, source=source)
  if left is None:
    return None, i
  if i < len(tokens) and tokens[i].kind is TokenKind.OP and tokens[i].text == "**":
    i += 1
    right, i = _parse_unary(tokens, i, source=source)
    if right is None:
      return left, i
    return BinOpExpr(
      left, "**", right, Span(left.span.file_id, left.span.start, right.span.end)
    ), i
  return left, i


def _parse_postfix(tokens, i, *, source):
  left, i = _parse_atom(tokens, i, source=source)
  if left is None:
    return None, i
  n = len(tokens)
  while i < n:
    if tokens[i].kind is TokenKind.DOT and i + 1 < n and tokens[i + 1].kind is TokenKind.NAME:
      attr = tokens[i + 1].text
      end = tokens[i + 1].span
      i += 2
      left = AttributeExpr(left, attr, Span(left.span.file_id, left.span.start, end.end))
      continue
    if tokens[i].kind is TokenKind.LSQB:
      i += 1
      parts: list[ExprSyntax] = []
      while True:
        # 维切片 ``:`` / ``:u`` / ``l:`` / ``l:u`` / ``l:u:s``
        if i < n and tokens[i].kind is TokenKind.COLON:
          colon_sp = tokens[i].span
          lower = None
          i += 1
          upper = None
          if i < n and tokens[i].kind not in (
            TokenKind.COLON,
            TokenKind.RSQB,
            TokenKind.COMMA,
          ):
            upper, i = parse_expr(tokens, i, source=source)
          step = None
          if i < n and tokens[i].kind is TokenKind.COLON:
            i += 1
            if i < n and tokens[i].kind not in (TokenKind.RSQB, TokenKind.COMMA):
              step, i = parse_expr(tokens, i, source=source)
          end_sp = (
            step.span if step is not None
            else upper.span if upper is not None
            else colon_sp
          )
          parts.append(
            SliceExpr(lower, upper, step, Span(colon_sp.file_id, colon_sp.start, end_sp.end))
          )
        else:
          first, i = parse_expr(tokens, i, source=source)
          if first is None:
            return left, i
          if i < n and tokens[i].kind is TokenKind.COLON:
            i += 1
            upper = None
            if i < n and tokens[i].kind not in (
              TokenKind.COLON,
              TokenKind.RSQB,
              TokenKind.COMMA,
            ):
              upper, i = parse_expr(tokens, i, source=source)
            step = None
            if i < n and tokens[i].kind is TokenKind.COLON:
              i += 1
              if i < n and tokens[i].kind not in (TokenKind.RSQB, TokenKind.COMMA):
                step, i = parse_expr(tokens, i, source=source)
            sl = SliceExpr(
              first,
              upper,
              step,
              Span(first.span.file_id, first.span.start, tokens[i - 1].span.end),
            )
            parts.append(sl)
          else:
            parts.append(first)
        if i < n and tokens[i].kind is TokenKind.COMMA:
          i += 1
          continue
        break
      if i >= n or tokens[i].kind is not TokenKind.RSQB or not parts:
        return left, i
      end = tokens[i].span
      i += 1
      if len(parts) == 1:
        index: ExprSyntax = parts[0]
      else:
        index = TupleExpr(
          parts, Span(parts[0].span.file_id, parts[0].span.start, parts[-1].span.end)
        )
      left = SubscriptExpr(left, index, Span(left.span.file_id, left.span.start, end.end))
      continue
    if tokens[i].kind is TokenKind.LPAR:
      i += 1
      args: list[ExprSyntax] = []
      kws: list[tuple[str, ExprSyntax]] = []
      while i < n and tokens[i].kind is not TokenKind.RPAR:
        if tokens[i].kind is TokenKind.COMMA:
          i += 1
          continue
        if (
          tokens[i].kind is TokenKind.NAME
          and i + 1 < n
          and tokens[i + 1].kind is TokenKind.EQ
        ):
          kn = tokens[i].text
          i += 2
          kv, i = parse_expr(tokens, i, source=source)
          if kv is not None:
            kws.append((kn, kv))
          continue
        arg, i = parse_expr(tokens, i, source=source)
        if arg is None:
          break
        args.append(arg)
      if i < n and tokens[i].kind is TokenKind.RPAR:
        end = tokens[i].span
        i += 1
        left = CallExpr(left, args, kws, Span(left.span.file_id, left.span.start, end.end))
      continue
    break
  return left, i


def _parse_atom(tokens, i, *, source):
  n = len(tokens)
  if i >= n:
    return None, i
  t = tokens[i]
  if t.kind is TokenKind.NAME:
    if t.text in ("True", "False", "None"):
      kind = "bool" if t.text != "None" else "none"
      return LiteralExpr(kind, t.text, t.span), i + 1
    if t.text == "lambda":
      return _parse_lambda(tokens, i, source=source)
    return NameExpr(t.text, t.span), i + 1
  # 表达式位置 ``*args`` / ``**kwargs``
  if t.kind is TokenKind.OP and t.text in ("*", "**") and i + 1 < n:
    inner, j = _parse_atom(tokens, i + 1, source=source)
    if inner is not None:
      # ``**`` 暂与 ``*`` 同用 StarredExpr（emit 可再分）
      return StarredExpr(inner, Span(t.span.file_id, t.span.start, inner.span.end)), j
  if t.kind is TokenKind.NUMBER:
    kind = "float" if "." in t.text or "e" in t.text.lower() else "int"
    return LiteralExpr(kind, t.text, t.span), i + 1
  if t.kind is TokenKind.ELLIPSIS:
    return LiteralExpr("ellipsis", "...", t.span), i + 1
  if t.kind is TokenKind.STRING:
    # 隐式拼接 ``"a" "b"`` / 相邻 f-string
    text = t.text
    end_sp = t.span
    i += 1
    while i < n and tokens[i].kind is TokenKind.STRING:
      text += tokens[i].text
      end_sp = tokens[i].span
      i += 1
    return LiteralExpr("str", text, Span(t.span.file_id, t.span.start, end_sp.end)), i
  if t.kind is TokenKind.LSQB:
    return _parse_list(tokens, i, source=source)
  if t.kind is TokenKind.LBRACE:
    return _parse_brace(tokens, i, source=source)
  if t.kind is TokenKind.LPAR:
    start = t.span
    i += 1
    if i < n and tokens[i].kind is TokenKind.RPAR:
      end = tokens[i].span
      return TupleExpr([], Span(start.file_id, start.start, end.end)), i + 1
    first, i = parse_expr(tokens, i, source=source)
    if first is None:
      return None, i
    if i < n and tokens[i].kind is TokenKind.COMMA:
      elts = [first]
      while i < n and tokens[i].kind is TokenKind.COMMA:
        i += 1
        if i < n and tokens[i].kind is TokenKind.RPAR:
          break
        el, i = parse_expr(tokens, i, source=source)
        if el is None:
          break
        elts.append(el)
      if i < n and tokens[i].kind is TokenKind.RPAR:
        end = tokens[i].span
        i += 1
        return TupleExpr(elts, Span(start.file_id, start.start, end.end)), i
      return TupleExpr(elts, Span(start.file_id, start.start, elts[-1].span.end)), i
    if i < n and tokens[i].kind is TokenKind.RPAR:
      i += 1
    return first, i
  return None, i


def _parse_list(tokens, i, *, source):
  start = tokens[i].span
  i += 1
  elts: list[ExprSyntax] = []
  n = len(tokens)
  while i < n and tokens[i].kind is not TokenKind.RSQB:
    if tokens[i].kind is TokenKind.COMMA:
      i += 1
      continue
    if tokens[i].kind in (TokenKind.NEWLINE, TokenKind.INDENT, TokenKind.DEDENT):
      i += 1
      continue
    el, i = parse_expr(tokens, i, source=source)
    if el is None:
      break
    elts.append(el)
  if i < n and tokens[i].kind is TokenKind.RSQB:
    end = tokens[i].span
    i += 1
    return ListExpr(elts, Span(start.file_id, start.start, end.end)), i
  return ListExpr(elts, Span(start.file_id, start.start, elts[-1].span.end if elts else start.end)), i


def _parse_brace(tokens, i, *, source):
  """``{k: v, ...}`` / ``{**d, k: v}`` 字典或 ``{a, b, ...}`` 集合（集合降为 ListExpr）。

  字典推导 ``{k: v for …}``：键值解析后若遇 ``for``，其余吞到 ``}`` 仍出 DictExpr
  （推导细节留 body_source / Mid emit 竖切）。
  """
  start = tokens[i].span
  i += 1
  n = len(tokens)
  while i < n and tokens[i].kind in (
    TokenKind.NEWLINE,
    TokenKind.INDENT,
    TokenKind.DEDENT,
  ):
    i += 1
  if i < n and tokens[i].kind is TokenKind.RBRACE:
    end = tokens[i].span
    return DictExpr([], [], Span(start.file_id, start.start, end.end)), i + 1

  # ``{**x…}`` / 首元素后冒号 → dict；否则 set
  is_dict = (
    i < n
    and tokens[i].kind is TokenKind.OP
    and tokens[i].text == "**"
  )
  if not is_dict:
    save = i
    first, j = parse_expr(tokens, i, source=source)
    if first is None:
      return None, i
    is_dict = j < n and tokens[j].kind is TokenKind.COLON
    i = save

  if is_dict:
    keys: list[ExprSyntax | None] = []
    values: list[ExprSyntax] = []
    while i < n and tokens[i].kind is not TokenKind.RBRACE:
      if tokens[i].kind is TokenKind.COMMA:
        i += 1
        continue
      if tokens[i].kind in (TokenKind.NEWLINE, TokenKind.INDENT, TokenKind.DEDENT):
        i += 1
        continue
      # ``**expr`` 展开
      if (
        tokens[i].kind is TokenKind.OP
        and tokens[i].text == "**"
      ):
        star, i = parse_expr(tokens, i, source=source)
        if star is None:
          break
        keys.append(None)
        values.append(star)
        continue
      k, i = parse_expr(tokens, i, source=source)
      if k is None:
        break
      if i >= n or tokens[i].kind is not TokenKind.COLON:
        break
      i += 1
      v, i = parse_expr(tokens, i, source=source)
      if v is None:
        break
      keys.append(k)
      values.append(v)
      # 字典推导：``{k: v for …}`` — 吞到闭合 ``}``
      if (
        i < n
        and tokens[i].kind is TokenKind.NAME
        and tokens[i].text == "for"
      ):
        while i < n and tokens[i].kind is not TokenKind.RBRACE:
          if tokens[i].kind in (TokenKind.NEWLINE, TokenKind.DEDENT, TokenKind.END):
            break
          i += 1
        break
    if i < n and tokens[i].kind is TokenKind.RBRACE:
      end = tokens[i].span
      i += 1
      return DictExpr(keys, values, Span(start.file_id, start.start, end.end)), i
    end_pos = values[-1].span.end if values else start.end
    return DictExpr(keys, values, Span(start.file_id, start.start, end_pos)), i

  # set → ListExpr（竖切；emit 仍可用）
  elts: list[ExprSyntax] = []
  while i < n and tokens[i].kind is not TokenKind.RBRACE:
    if tokens[i].kind is TokenKind.COMMA:
      i += 1
      continue
    if tokens[i].kind in (TokenKind.NEWLINE, TokenKind.INDENT, TokenKind.DEDENT):
      i += 1
      continue
    el, i = parse_expr(tokens, i, source=source)
    if el is None:
      break
    elts.append(el)
  if i < n and tokens[i].kind is TokenKind.RBRACE:
    end = tokens[i].span
    i += 1
    return ListExpr(elts, Span(start.file_id, start.start, end.end)), i
  end_pos = elts[-1].span.end if elts else start.end
  return ListExpr(elts, Span(start.file_id, start.start, end_pos)), i


def _parse_block_body(tokens, i, end_i, *, source):
  body: list[StmtSyntax] = []
  while i < end_i and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  if i < end_i and tokens[i].kind is TokenKind.INDENT:
    i += 1
    body, i = parse_suite(tokens, i, end_i, source=source)
    if i < end_i and tokens[i].kind is TokenKind.DEDENT:
      i += 1
  return body, i


def _parse_if(tokens, i, end_i, *, source):
  start = tokens[i].span
  i += 1  # if
  test, i = parse_expr(tokens, i, source=source)
  if test is None or i >= end_i or tokens[i].kind is not TokenKind.COLON:
    return OpaqueStmtSyntax("if …", start), i
  i += 1
  body, i = _parse_block_body(tokens, i, end_i, source=source)
  orelse: list[StmtSyntax] = []
  if i < end_i and tokens[i].kind is TokenKind.NAME and tokens[i].text == "elif":
    # elif → else: if …
    nested, i = _parse_if(tokens, i, end_i, source=source)
    orelse = [nested]
  elif i < end_i and tokens[i].kind is TokenKind.NAME and tokens[i].text == "else":
    i += 1
    if i < end_i and tokens[i].kind is TokenKind.COLON:
      i += 1
    orelse, i = _parse_block_body(tokens, i, end_i, source=source)
  end = orelse[-1].span if orelse else (body[-1].span if body else test.span)
  return IfStmt(test, body, orelse, Span(start.file_id, start.start, end.end)), i


def _parse_while(tokens, i, end_i, *, source):
  start = tokens[i].span
  i += 1
  test, i = parse_expr(tokens, i, source=source)
  if test is None or i >= end_i or tokens[i].kind is not TokenKind.COLON:
    return OpaqueStmtSyntax("while …", start), i
  i += 1
  body, i = _parse_block_body(tokens, i, end_i, source=source)
  end = body[-1].span if body else test.span
  return WhileStmt(test, body, Span(start.file_id, start.start, end.end)), i


def _parse_lambda(tokens, i, *, source):
  """``lambda [params]: expr``。"""
  start = tokens[i].span
  i += 1
  n = len(tokens)
  params_start = i
  while i < n and tokens[i].kind is not TokenKind.COLON:
    if tokens[i].kind in (TokenKind.NEWLINE, TokenKind.DEDENT, TokenKind.END):
      return None, params_start
    i += 1
  params_src = ""
  if i > params_start and source is not None:
    params_src = source[tokens[params_start].span.start : tokens[i - 1].span.end].strip()
  if i >= n or tokens[i].kind is not TokenKind.COLON:
    return None, params_start
  i += 1
  body, i = parse_expr(tokens, i, source=source)
  if body is None:
    return None, i
  return LambdaExpr(params_src, body, Span(start.file_id, start.start, body.span.end)), i


def _parse_one_target(tokens, i, *, source):
  """单个赋值目标：``x`` / ``a.b`` / ``*x``。"""
  n = len(tokens)
  if i < n and tokens[i].kind is TokenKind.OP and tokens[i].text == "*":
    star_sp = tokens[i].span
    i += 1
    inner, i = _parse_postfix(tokens, i, source=source)
    if inner is None:
      return None, i
    return StarredExpr(inner, Span(star_sp.file_id, star_sp.start, inner.span.end)), i
  return _parse_postfix(tokens, i, source=source)


def _parse_target(tokens, i, *, source):
  """赋值 / for 目标：不含比较（避免 ``i in xs`` 被吃进 target）。"""
  first, i = _parse_one_target(tokens, i, source=source)
  if first is None:
    return None, i
  if i < len(tokens) and tokens[i].kind is TokenKind.COMMA:
    elts = [first]
    while i < len(tokens) and tokens[i].kind is TokenKind.COMMA:
      i += 1
      if i < len(tokens) and (
        (tokens[i].kind is TokenKind.NAME and tokens[i].text == "in")
        or tokens[i].kind is TokenKind.EQ
        or tokens[i].kind is TokenKind.COLON
      ):
        break
      el, i = _parse_one_target(tokens, i, source=source)
      if el is None:
        break
      elts.append(el)
    return TupleExpr(
      elts, Span(first.span.file_id, first.span.start, elts[-1].span.end)
    ), i
  return first, i


def _parse_for(tokens, i, end_i, *, source):
  start = tokens[i].span
  i += 1
  target, i = _parse_target(tokens, i, source=source)
  if target is None or i >= end_i or not (
    tokens[i].kind is TokenKind.NAME and tokens[i].text == "in"
  ):
    return OpaqueStmtSyntax("for …", start), i
  i += 1
  it, i = parse_expr(tokens, i, source=source)
  if it is None or i >= end_i or tokens[i].kind is not TokenKind.COLON:
    return OpaqueStmtSyntax("for …", start), i
  i += 1
  body, i = _parse_block_body(tokens, i, end_i, source=source)
  end = body[-1].span if body else it.span
  return ForStmt(target, it, body, Span(start.file_id, start.start, end.end)), i


def _parse_match(tokens, i, end_i, *, source):
  start = tokens[i].span
  i += 1
  subject, i = parse_expr(tokens, i, source=source)
  if subject is None or i >= end_i or tokens[i].kind is not TokenKind.COLON:
    return OpaqueStmtSyntax("match …", start), i
  i += 1
  while i < end_i and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  cases: list[MatchCase] = []
  if i < end_i and tokens[i].kind is TokenKind.INDENT:
    i += 1
    while i < end_i and tokens[i].kind is not TokenKind.DEDENT:
      if tokens[i].kind is TokenKind.NEWLINE:
        i += 1
        continue
      if tokens[i].kind is TokenKind.COMMENT:
        i += 1
        continue
      if not (tokens[i].kind is TokenKind.NAME and tokens[i].text == "case"):
        break
      cstart = tokens[i].span
      i += 1
      # 模式：吃到顶层冒号（含 ``|`` or-pattern；跳过 ``{"k": v}`` 内冒号）
      ps = i
      depth_par = depth_sq = depth_br = 0
      while i < end_i:
        kind = tokens[i].kind
        if kind in (TokenKind.NEWLINE, TokenKind.DEDENT, TokenKind.END):
          break
        if kind is TokenKind.LPAR:
          depth_par += 1
        elif kind is TokenKind.RPAR:
          depth_par = max(0, depth_par - 1)
        elif kind is TokenKind.LSQB:
          depth_sq += 1
        elif kind is TokenKind.RSQB:
          depth_sq = max(0, depth_sq - 1)
        elif kind is TokenKind.LBRACE:
          depth_br += 1
        elif kind is TokenKind.RBRACE:
          depth_br = max(0, depth_br - 1)
        elif (
          kind is TokenKind.COLON
          and depth_par == 0
          and depth_sq == 0
          and depth_br == 0
        ):
          break
        i += 1
      if i >= end_i or tokens[i].kind is not TokenKind.COLON:
        return OpaqueStmtSyntax("case …", cstart), i
      pat = source[tokens[ps].span.start : tokens[i - 1].span.end] if i > ps else "_"
      i += 1  # :
      cbody, i = _parse_block_body(tokens, i, end_i, source=source)
      cend = cbody[-1].span if cbody else cstart
      cases.append(
        MatchCase(pat.strip(), cbody, Span(cstart.file_id, cstart.start, cend.end))
      )
    if i < end_i and tokens[i].kind is TokenKind.DEDENT:
      i += 1
  end = cases[-1].span if cases else subject.span
  return MatchStmt(subject, cases, Span(start.file_id, start.start, end.end)), i


def _parse_try(tokens, i, end_i, *, source):
  start = tokens[i].span
  i += 1
  if i >= end_i or tokens[i].kind is not TokenKind.COLON:
    return OpaqueStmtSyntax("try …", start), i
  i += 1
  body, i = _parse_block_body(tokens, i, end_i, source=source)
  handlers: list[ExceptHandler] = []
  while i < end_i and tokens[i].kind is TokenKind.NAME and tokens[i].text == "except":
    hstart = tokens[i].span
    i += 1
    typ: ExprSyntax | None = None
    name: str | None = None
    if i < end_i and tokens[i].kind is not TokenKind.COLON:
      typ, i = parse_expr(tokens, i, source=source)
      if (
        i < end_i
        and tokens[i].kind is TokenKind.NAME
        and tokens[i].text == "as"
        and i + 1 < end_i
        and tokens[i + 1].kind is TokenKind.NAME
      ):
        name = tokens[i + 1].text
        i += 2
    if i >= end_i or tokens[i].kind is not TokenKind.COLON:
      return OpaqueStmtSyntax("except …", hstart), i
    i += 1
    hbody, i = _parse_block_body(tokens, i, end_i, source=source)
    hend = hbody[-1].span if hbody else hstart
    handlers.append(
      ExceptHandler(typ, name, hbody, Span(hstart.file_id, hstart.start, hend.end))
    )
  orelse: list[StmtSyntax] = []
  if i < end_i and tokens[i].kind is TokenKind.NAME and tokens[i].text == "else":
    i += 1
    if i < end_i and tokens[i].kind is TokenKind.COLON:
      i += 1
    orelse, i = _parse_block_body(tokens, i, end_i, source=source)
  finalbody: list[StmtSyntax] = []
  if i < end_i and tokens[i].kind is TokenKind.NAME and tokens[i].text == "finally":
    i += 1
    if i < end_i and tokens[i].kind is TokenKind.COLON:
      i += 1
    finalbody, i = _parse_block_body(tokens, i, end_i, source=source)
  end = (
    finalbody[-1].span
    if finalbody
    else orelse[-1].span
    if orelse
    else handlers[-1].span
    if handlers
    else body[-1].span
    if body
    else start
  )
  return TryStmt(
    body, handlers, orelse, finalbody, Span(start.file_id, start.start, end.end)
  ), i


def _parse_with(tokens, i, end_i, *, source):
  start = tokens[i].span
  i += 1
  items: list[WithItem] = []
  while True:
    ctx, i = parse_expr(tokens, i, source=source)
    if ctx is None:
      return OpaqueStmtSyntax("with …", start), i
    opt: ExprSyntax | None = None
    if i < end_i and tokens[i].kind is TokenKind.NAME and tokens[i].text == "as":
      i += 1
      opt, i = _parse_one_target(tokens, i, source=source)
    items.append(
      WithItem(
        ctx,
        opt,
        Span(ctx.span.file_id, ctx.span.start, (opt.span if opt else ctx.span).end),
      )
    )
    if i < end_i and tokens[i].kind is TokenKind.COMMA:
      i += 1
      continue
    break
  if i >= end_i or tokens[i].kind is not TokenKind.COLON:
    return OpaqueStmtSyntax("with …", start), i
  i += 1
  body, i = _parse_block_body(tokens, i, end_i, source=source)
  end = body[-1].span if body else items[-1].span
  return WithStmt(items, body, Span(start.file_id, start.start, end.end)), i


def _parse_assert(tokens, i, end_i, *, source):
  start = tokens[i].span
  i += 1
  test, i = parse_expr(tokens, i, source=source)
  if test is None:
    return OpaqueStmtSyntax("assert …", start), i
  msg: ExprSyntax | None = None
  if i < end_i and tokens[i].kind is TokenKind.COMMA:
    i += 1
    msg, i = parse_expr(tokens, i, source=source)
  end = msg.span if msg is not None else test.span
  return AssertStmt(test, msg, Span(start.file_id, start.start, end.end)), i
