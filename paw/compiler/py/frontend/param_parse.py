"""函数参数表 → ``ParamDecl``（P1）。"""
from __future__ import annotations

from .source import Span
from .syntax_nodes import ParamDecl
from .tokens import Token, TokenKind
from .type_parse import parse_type, type_syntax_to_source


def parse_params(
  tokens: list[Token],
  i: int,
  *,
  source: str,
  end_kind: TokenKind = TokenKind.RPAR,
) -> tuple[list[ParamDecl], int]:
  """从 ``(`` 之后的位置解析到匹配 ``)``；``i`` 指向首个参数或 ``)``。"""
  n = len(tokens)
  params: list[ParamDecl] = []
  seen_star = False
  while i < n and tokens[i].kind is not end_kind:
    if tokens[i].kind is TokenKind.COMMA:
      i += 1
      continue
    # 位置-only 分隔符 ``/``（PEP 570）；本身不是参数
    if tokens[i].kind is TokenKind.OP and tokens[i].text == "/":
      i += 1
      continue
    if tokens[i].kind is TokenKind.OP and tokens[i].text == "*":
      star_sp = tokens[i].span
      i += 1
      if i < n and tokens[i].kind is TokenKind.NAME:
        name = tokens[i].text
        nsp = tokens[i].span
        i += 1
        typ = None
        if i < n and tokens[i].kind is TokenKind.COLON:
          i += 1
          typ, i = parse_type(tokens, i, source=source)
        params.append(
          ParamDecl(
            name=name,
            type_syntax=typ,
            default_source=None,
            span=Span(star_sp.file_id, star_sp.start, nsp.end),
            is_vararg=True,
            kind="star",
          )
        )
        seen_star = True
      else:
        seen_star = True
      continue
    if tokens[i].kind is TokenKind.OP and tokens[i].text == "**":
      star_sp = tokens[i].span
      i += 1
      if i >= n or tokens[i].kind is not TokenKind.NAME:
        break
      name = tokens[i].text
      nsp = tokens[i].span
      i += 1
      typ = None
      if i < n and tokens[i].kind is TokenKind.COLON:
        i += 1
        typ, i = parse_type(tokens, i, source=source)
      params.append(
        ParamDecl(
          name=name,
          type_syntax=typ,
          default_source=None,
          span=Span(star_sp.file_id, star_sp.start, nsp.end),
          is_kwarg=True,
          kind="dstar",
        )
      )
      continue
    if tokens[i].kind is not TokenKind.NAME:
      break
    name = tokens[i].text
    start = tokens[i].span
    i += 1
    typ = None
    if i < n and tokens[i].kind is TokenKind.COLON:
      i += 1
      typ, i = parse_type(tokens, i, source=source)
    default = None
    if i < n and tokens[i].kind is TokenKind.EQ:
      i += 1
      vs = i
      depth = 0
      while i < n:
        k = tokens[i].kind
        if k is TokenKind.LPAR or k is TokenKind.LSQB or k is TokenKind.LBRACE:
          depth += 1
        elif k is TokenKind.RPAR or k is TokenKind.RSQB or k is TokenKind.RBRACE:
          if depth == 0 and k is end_kind:
            break
          depth -= 1
        elif depth == 0 and k is TokenKind.COMMA:
          break
        i += 1
      if i > vs:
        default = source[tokens[vs].span.start : tokens[i - 1].span.end]
    end_sp = tokens[i - 1].span if i > 0 else start
    params.append(
      ParamDecl(
        name=name,
        type_syntax=typ,
        default_source=default,
        span=Span(start.file_id, start.start, end_sp.end),
        kind="kwonly" if seen_star else "pos",
      )
    )
  if i < n and tokens[i].kind is end_kind:
    i += 1
  return params, i


def params_to_source(params: list[ParamDecl]) -> str:
  parts: list[str] = []
  for p in params:
    if p.is_kwarg:
      s = f"**{p.name}"
    elif p.is_vararg:
      s = f"*{p.name}"
    else:
      s = p.name
    if p.type_syntax is not None:
      s += f": {type_syntax_to_source(p.type_syntax)}"
    if p.default_source is not None:
      s += f" = {p.default_source}"
    parts.append(s)
  return ", ".join(parts)
