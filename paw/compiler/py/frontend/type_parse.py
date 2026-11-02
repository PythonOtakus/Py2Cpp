"""类型表面递归下降：与表达式下标 / ``a @ b`` 分叉。

产出 ``TypeSyntax``（含 ``GenericApplyTypeSyntax``、``ReferenceTypeSyntax``、
``AttributedTypeSyntax`` 等）。停止于 ``stop`` 集合中的 token（不含已消费部分）。
"""
from __future__ import annotations

from .source import Span
from .syntax_nodes import (
  AttributeTypeSyntax,
  AttributedTypeSyntax,
  CallableTypeSyntax,
  GenericApplyTypeSyntax,
  LazyTypeSyntax,
  NameTypeSyntax,
  NullableTypeSyntax,
  ParenthesizedTypeSyntax,
  ReferenceTypeSyntax,
  TupleTypeSyntax,
  TypeAttrSyntax,
  TypeSyntax,
  UnionTypeSyntax,
)
from .tokens import Token, TokenKind

_STOP_DEFAULT = frozenset(
  {
    TokenKind.NEWLINE,
    TokenKind.DEDENT,
    TokenKind.INDENT,
    TokenKind.END,
    TokenKind.COLON,
    TokenKind.EQ,
    TokenKind.COMMA,
    TokenKind.RPAR,
    TokenKind.RSQB,
    TokenKind.RBRACE,
  }
)


def parse_type(
  tokens: list[Token],
  i: int,
  *,
  source: str | None = None,
  stop: frozenset[TokenKind] | None = None,
) -> tuple[TypeSyntax | None, int]:
  """从 ``tokens[i]`` 解析一个类型；失败返回 ``(None, i)``。"""
  n = len(tokens)
  if i >= n:
    return None, i
  stop_set = stop if stop is not None else _STOP_DEFAULT
  if tokens[i].kind in stop_set:
    return None, i
  return _parse_type_expr(tokens, i, stop_set, source)


def type_syntax_to_source(ty: TypeSyntax) -> str:
  """结构化类型 → 兼容后端的注解源码（``ref``/``lazy`` 前缀；属性仍 ``T @Meta``）。"""
  match ty:
    case NameTypeSyntax(name=name):
      return name
    case GenericApplyTypeSyntax(head=head, arguments=args):
      inner = ", ".join(type_syntax_to_source(a) for a in args)
      return f"{type_syntax_to_source(head)}[{inner}]"
    case ReferenceTypeSyntax(inner=inner):
      return f"ref {type_syntax_to_source(inner)}"
    case LazyTypeSyntax(inner=inner):
      return f"lazy {type_syntax_to_source(inner)}"
    case NullableTypeSyntax(inner=inner):
      return f"{type_syntax_to_source(inner)}?"
    case ParenthesizedTypeSyntax(inner=inner):
      return f"({type_syntax_to_source(inner)})"
    case TupleTypeSyntax(items=items, trailing_comma=trail):
      parts = [type_syntax_to_source(x) for x in items]
      body = ", ".join(parts)
      if trail or len(items) == 1:
        body = body + ","
      return f"({body})"
    case CallableTypeSyntax(parameter_types=ps, return_type=ret, is_py_callable=py_c):
      arrow = _arrow_source(ps, ret, to_src=type_syntax_to_source)
      return f"Callable[{arrow}]" if py_c else arrow
    case UnionTypeSyntax(options=opts):
      return " | ".join(type_syntax_to_source(o) for o in opts)
    case AttributeTypeSyntax(inner=inner, attr=attr):
      return f"{type_syntax_to_source(inner)}.{attr}"
    case AttributedTypeSyntax(inner=inner, attributes=attrs):
      s = type_syntax_to_source(inner)
      for a in attrs:
        if a.args_source:
          s += f" @{a.name}({a.args_source})"
        else:
          s += f" @{a.name}"
      return s
    case _:
      return ""


def type_syntax_to_legacy_annotation(ty: TypeSyntax) -> str:
  """物化用：前缀 ``ref``/``lazy`` 改为 MatMult 标记 ``T @ref`` / ``T @lazy``。"""
  match ty:
    case ReferenceTypeSyntax(inner=inner):
      return f"{type_syntax_to_legacy_annotation(inner)} @ref"
    case LazyTypeSyntax(inner=ReferenceTypeSyntax() as ref):
      # lazy ref T → T @ref @lazy
      return f"{type_syntax_to_legacy_annotation(ref.inner)} @ref @lazy"
    case LazyTypeSyntax(inner=inner):
      return f"{type_syntax_to_legacy_annotation(inner)} @lazy"
    case NullableTypeSyntax(inner=inner):
      # 后端暂仍多写 Optional/|；物化保留 ? 需 rewrite — 先展开为 inner | None 过重
      # C0：保留 ? 交给 surface_rewrite/opaque；此处拼回 ?
      return f"{type_syntax_to_legacy_annotation(inner)}?"
    case GenericApplyTypeSyntax(head=head, arguments=args):
      inner = ", ".join(type_syntax_to_legacy_annotation(a) for a in args)
      return f"{type_syntax_to_legacy_annotation(head)}[{inner}]"
    case ParenthesizedTypeSyntax(inner=inner):
      return f"({type_syntax_to_legacy_annotation(inner)})"
    case TupleTypeSyntax(items=items, trailing_comma=trail):
      parts = [type_syntax_to_legacy_annotation(x) for x in items]
      body = ", ".join(parts)
      if trail or len(items) == 1:
        body = body + ","
      return f"({body})"
    case CallableTypeSyntax(parameter_types=ps, return_type=ret, is_py_callable=py_c):
      # 物化桥：仍写旧 Subscript，供 type_parse_ast 识别 Function/Callable
      args = ", ".join(type_syntax_to_legacy_annotation(p) for p in ps)
      r = type_syntax_to_legacy_annotation(ret)
      head = "Callable" if py_c else "Function"
      return f"{head}[[{args}], {r}]"
    case UnionTypeSyntax(options=opts):
      return " | ".join(type_syntax_to_legacy_annotation(o) for o in opts)
    case AttributedTypeSyntax(inner=inner, attributes=attrs):
      s = type_syntax_to_legacy_annotation(inner)
      for a in attrs:
        if a.args_source:
          s += f" @{a.name}({a.args_source})"
        else:
          s += f" @{a.name}"
      return s
    case NameTypeSyntax(name=name):
      return name
    case _:
      return type_syntax_to_source(ty)


def _arrow_source(
  ps: list[TypeSyntax],
  ret: TypeSyntax,
  *,
  to_src,
) -> str:
  """单参优先 ``T -> R``；零参 ``() -> R``；多参 ``(A, B) -> R``。"""
  r = to_src(ret)
  if len(ps) == 0:
    return f"() -> {r}"
  if len(ps) == 1:
    p = to_src(ps[0])
    # 已有括号的复杂实参保持原样
    if p.startswith("(") or "->" in p or "[" in p:
      return f"({p}) -> {r}"
    return f"{p} -> {r}"
  params = ", ".join(to_src(p) for p in ps)
  return f"({params}) -> {r}"


def _span_join(a: Span, b: Span) -> Span:
  return Span(a.file_id, a.start, b.end)


def _parse_type_expr(
  tokens: list[Token],
  i: int,
  stop: frozenset[TokenKind],
  source: str | None,
) -> tuple[TypeSyntax | None, int]:
  n = len(tokens)
  if i >= n or tokens[i].kind in stop:
    return None, i

  left, i = _parse_type_expr_no_union(tokens, i, stop, source)
  if left is None:
    return None, i
  # ``A | B | C``（类型并；``|`` 为 OP）
  opts = [left]
  while (
    i < n
    and tokens[i].kind is TokenKind.OP
    and tokens[i].text == "|"
    and TokenKind.OP not in stop  # stop 一般不含 OP
  ):
    i += 1
    right, i = _parse_type_expr_no_union(tokens, i, stop, source)
    if right is None:
      break
    opts.append(right)
  if len(opts) == 1:
    return opts[0], i
  return UnionTypeSyntax(opts, _span_join(opts[0].span, opts[-1].span)), i


def _parse_type_expr_no_union(
  tokens: list[Token],
  i: int,
  stop: frozenset[TokenKind],
  source: str | None,
) -> tuple[TypeSyntax | None, int]:
  n = len(tokens)
  if i >= n or tokens[i].kind in stop:
    return None, i

  # lazy / ref 前缀（软关键字）
  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "lazy":
    start = tokens[i].span
    i += 1
    if (
      i < n
      and tokens[i].kind is TokenKind.NAME
      and tokens[i].text == "ref"
    ):
      i += 1
      inner, i = _parse_type_primary(tokens, i, stop, source)
      if inner is None:
        return None, i
      ref = ReferenceTypeSyntax(inner, _span_join(start, inner.span))
      return LazyTypeSyntax(ref, _span_join(start, ref.span)), i
    if i < n and tokens[i].kind is TokenKind.NAME and tokens[i].text == "lazy":
      return None, i
    inner, i = _parse_type_primary(tokens, i, stop, source)
    if inner is None:
      return None, i
    return LazyTypeSyntax(inner, _span_join(start, inner.span)), i

  if tokens[i].kind is TokenKind.NAME and tokens[i].text == "ref":
    start = tokens[i].span
    i += 1
    if i < n and tokens[i].kind is TokenKind.NAME and tokens[i].text == "lazy":
      return None, i
    if i < n and tokens[i].kind is TokenKind.NAME and tokens[i].text == "class":
      return None, i - 1
    inner, i = _parse_type_primary(tokens, i, stop, source)
    if inner is None:
      return None, i
    return ReferenceTypeSyntax(inner, _span_join(start, inner.span)), i

  return _parse_type_primary(tokens, i, stop, source)


def _parse_type_primary(
  tokens: list[Token],
  i: int,
  stop: frozenset[TokenKind],
  source: str | None,
) -> tuple[TypeSyntax | None, int]:
  ty, i = _parse_type_atom(tokens, i, stop, source)
  if ty is None:
    return None, i
  n = len(tokens)

  while i < n and tokens[i].kind is TokenKind.LSQB:
    # ``T[:]`` / ``T[:,:]`` / ``T[:N]`` / ``T[:R,:C]`` / ``list[T, N]`` 等
    args: list[TypeSyntax] = []
    i += 1
    if i < n and tokens[i].kind is TokenKind.RSQB:
      return None, i
    inner_stop = (stop | {TokenKind.RSQB, TokenKind.COMMA}) - {TokenKind.COLON}
    while True:
      arg, i = _parse_type_bracket_arg(tokens, i, inner_stop, source)
      if arg is None:
        return None, i
      args.append(arg)
      if i < n and tokens[i].kind is TokenKind.COMMA:
        i += 1
        continue
      break
    if i >= n or tokens[i].kind is not TokenKind.RSQB:
      return None, i
    end_sp = tokens[i].span
    i += 1
    ty = GenericApplyTypeSyntax(ty, args, _span_join(ty.span, end_sp))

  # ``Generic[T].Attr`` / ``T.Attr``（atom 内已拼裸 ``A.B``；此处接泛型后属性）
  while (
    i + 1 < n
    and tokens[i].kind is TokenKind.DOT
    and tokens[i + 1].kind is TokenKind.NAME
  ):
    attr = tokens[i + 1].text
    end_sp = tokens[i + 1].span
    i += 2
    ty = AttributeTypeSyntax(ty, attr, _span_join(ty.span, end_sp))

  while i < n and tokens[i].kind is TokenKind.QUESTION:
    end_sp = tokens[i].span
    i += 1
    ty = NullableTypeSyntax(ty, _span_join(ty.span, end_sp))

  attrs: list[TypeAttrSyntax] = []
  while i < n and tokens[i].kind is TokenKind.AT:
    at_sp = tokens[i].span
    i += 1
    if i >= n or tokens[i].kind is not TokenKind.NAME:
      return None, i
    aname = tokens[i].text
    a_end = tokens[i].span
    i += 1
    args_src: str | None = None
    if i < n and tokens[i].kind is TokenKind.LPAR:
      depth = 0
      ps = tokens[i + 1].span.start if i + 1 < n else tokens[i].span.end
      j = i
      while j < n:
        if tokens[j].kind is TokenKind.LPAR:
          depth += 1
        elif tokens[j].kind is TokenKind.RPAR:
          depth -= 1
          if depth == 0:
            break
        j += 1
      if j >= n:
        return None, i
      if source is not None and j > i + 1:
        args_src = source[ps : tokens[j - 1].span.end]
      elif j > i + 1:
        args_src = " ".join(tokens[k].text for k in range(i + 1, j))
      a_end = tokens[j].span
      i = j + 1
    attrs.append(TypeAttrSyntax(aname, args_src, _span_join(at_sp, a_end)))
  if attrs:
    ty = AttributedTypeSyntax(ty, attrs, _span_join(ty.span, attrs[-1].span))

  # ``Callable[(T)->R]`` → PyCallable 槽；禁旧 ``Callable[[…],R]``（多参 Subscript）
  if (
    isinstance(ty, GenericApplyTypeSyntax)
    and isinstance(ty.head, NameTypeSyntax)
    and ty.head.name == "Callable"
  ):
    args = ty.arguments
    if len(args) == 1 and isinstance(args[0], CallableTypeSyntax):
      inner = args[0]
      ty = CallableTypeSyntax(
        list(inner.parameter_types),
        inner.return_type,
        ty.span,
        is_py_callable=True,
      )
    elif len(args) == 1 and isinstance(args[0], NameTypeSyntax) and args[0].name == "...":
      # Callable[...] 仍允许（变参槽）
      pass
    else:
      # 旧式 Callable[[T], R] 等：拒绝（留 None 让上层报错）
      return None, i

  if (
    isinstance(ty, GenericApplyTypeSyntax)
    and isinstance(ty.head, NameTypeSyntax)
    and ty.head.name == "Function"
  ):
    # 旧式 Function[[T], R] 一律拒绝；请写 (T)->R
    return None, i

  # 裸箭头 ``T -> R`` / ``list[int] -> str``（单参无括号）
  if i < n and tokens[i].kind is TokenKind.RARROW:
    i += 1
    ret, i = _parse_type_expr(tokens, i, stop, source)
    if ret is None:
      return None, i
    ty = CallableTypeSyntax([ty], ret, _span_join(ty.span, ret.span), is_py_callable=False)

  return ty, i


def _parse_type_dim_piece(
  tokens: list[Token],
  i: int,
  source: str | None,
) -> tuple[TypeSyntax | None, int]:
  """切片维上下界：允许 ``Self._dim * 2`` 等 NTTP 算式（收到 COMMA/RSQB/COLON 止）。"""
  n = len(tokens)
  if i >= n or tokens[i].kind in (
    TokenKind.COMMA,
    TokenKind.RSQB,
    TokenKind.COLON,
    TokenKind.RPAR,
    TokenKind.RBRACE,
  ):
    return None, i
  start = tokens[i].span
  depth = 0
  j = i
  while j < n:
    k = tokens[j].kind
    if k in (TokenKind.LSQB, TokenKind.LPAR, TokenKind.LBRACE):
      depth += 1
    elif k in (TokenKind.RSQB, TokenKind.RPAR, TokenKind.RBRACE):
      if depth == 0:
        break
      depth -= 1
    elif depth == 0 and k in (TokenKind.COMMA, TokenKind.COLON):
      break
    j += 1
  if j == i:
    return None, i
  end = tokens[j - 1].span
  if source is not None:
    text = source[start.start : end.end].strip()
  else:
    text = " ".join(tokens[k].text for k in range(i, j))
  return NameTypeSyntax(text, _span_join(start, end)), j


def _parse_type_bracket_arg(
  tokens: list[Token],
  i: int,
  stop: frozenset[TokenKind],
  source: str | None,
) -> tuple[TypeSyntax | None, int]:
  """方括号实参：普通类型或切片 ``:`` / ``:N`` / ``lo:hi``（堆/栈数组维）。"""
  n = len(tokens)
  if i >= n or tokens[i].kind in stop:
    return None, i

  # 以 ``:`` 开头的切片维：``:`` / ``:N`` / ``:Self._dim * 2``
  if tokens[i].kind is TokenKind.COLON:
    start = tokens[i].span
    i += 1
    upper, i = _parse_type_dim_piece(tokens, i, source)
    end = upper.span if upper is not None else start
    text = ":" + (type_syntax_to_source(upper) if upper is not None else "")
    return NameTypeSyntax(text, _span_join(start, end)), i

  # 窥视：``lo:hi`` 切片维 vs 普通类型实参
  lower, j = _parse_type_dim_piece(tokens, i, source)
  if lower is None:
    return None, i
  if j < n and tokens[j].kind is TokenKind.COLON:
    i = j + 1
    upper, i = _parse_type_dim_piece(tokens, i, source)
    end = upper.span if upper is not None else tokens[j].span
    lo = type_syntax_to_source(lower)
    up = type_syntax_to_source(upper) if upper is not None else ""
    return NameTypeSyntax(f"{lo}:{up}", _span_join(lower.span, end)), i
  # 非切片：按完整类型实参重解析（保留 GenericApply 等结构）
  return _parse_type_expr(tokens, i, stop, source)


def _parse_type_atom(
  tokens: list[Token],
  i: int,
  stop: frozenset[TokenKind],
  source: str | None,
) -> tuple[TypeSyntax | None, int]:
  n = len(tokens)
  if i >= n or tokens[i].kind in stop:
    return None, i

  if tokens[i].kind is TokenKind.NAME:
    start = tokens[i].span
    name = tokens[i].text
    i += 1
    while (
      i + 1 < n
      and tokens[i].kind is TokenKind.DOT
      and tokens[i + 1].kind is TokenKind.NAME
    ):
      name = name + "." + tokens[i + 1].text
      i += 2
    end = tokens[i - 1].span
    return NameTypeSyntax(name, _span_join(start, end)), i

  # 类型包 ``*Ts``（``(*Ts,)`` / 形参包注解）
  if (
    tokens[i].kind is TokenKind.OP
    and tokens[i].text == "*"
    and i + 1 < n
    and tokens[i + 1].kind is TokenKind.NAME
  ):
    start = tokens[i].span
    end = tokens[i + 1].span
    return NameTypeSyntax("*" + tokens[i + 1].text, _span_join(start, end)), i + 2

  # NTTP / 容量常量：``list[T, 0]``、``int[:4]``
  if tokens[i].kind is TokenKind.NUMBER:
    sp = tokens[i].span
    return NameTypeSyntax(tokens[i].text, sp), i + 1

  if tokens[i].kind is TokenKind.ELLIPSIS:
    sp = tokens[i].span
    return NameTypeSyntax("...", sp), i + 1

  if tokens[i].kind is TokenKind.LPAR:
    start = tokens[i].span
    i += 1
    if i < n and tokens[i].kind is TokenKind.RPAR:
      i += 1
      if i < n and tokens[i].kind is TokenKind.RARROW:
        i += 1
        ret, i = _parse_type_expr(tokens, i, stop, source)
        if ret is None:
          return None, i
        return CallableTypeSyntax([], ret, _span_join(start, ret.span)), i
      return None, i

    items: list[TypeSyntax] = []
    trailing = False
    while True:
      item, i = _parse_type_expr(
        tokens,
        i,
        stop | {TokenKind.RPAR, TokenKind.COMMA, TokenKind.RARROW},
        source,
      )
      if item is None:
        return None, i
      items.append(item)
      if i < n and tokens[i].kind is TokenKind.COMMA:
        trailing = True
        i += 1
        if i < n and tokens[i].kind is TokenKind.RPAR:
          break
        trailing = False
        continue
      break
    if i >= n or tokens[i].kind is not TokenKind.RPAR:
      return None, i
    rpar = tokens[i].span
    i += 1
    if i < n and tokens[i].kind is TokenKind.RARROW:
      i += 1
      ret, i = _parse_type_expr(tokens, i, stop, source)
      if ret is None:
        return None, i
      return CallableTypeSyntax(items, ret, _span_join(start, ret.span)), i
    if len(items) == 1 and not trailing:
      return ParenthesizedTypeSyntax(items[0], _span_join(start, rpar)), i
    return TupleTypeSyntax(items, trailing, _span_join(start, rpar)), i

  return None, i
