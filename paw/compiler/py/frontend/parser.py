"""递归下降：Paw 声明 + import/def；其余为 OpaqueStmt（禁止全文 rewrite）。"""
from __future__ import annotations

import textwrap

from .source import Span
from .syntax_nodes import (
  ClassDecl,
  ConstField,
  EnumDecl,
  EnumMember,
  FieldDecl,
  FunctionDecl,
  ImportStmt,
  ModuleConstDecl,
  ObjectModel,
  OpaqueMember,
  OpaqueStmt,
  SyntaxModule,
)
from .param_parse import params_to_source, parse_params
from .stmt_parse import parse_suite
from .tokens import Token, TokenKind
from .type_parse import parse_type, type_syntax_to_source

_DECL_HEADS_NAME = frozenset(
  {"class", "record", "variant", "protocol", "mixin"}
)
_DECL_HEADS = frozenset(
  {"class", "record", "enum", "union", "variant", "protocol", "mixin"}
)
_PREFIXES = frozenset({"frozen", "ordered", "final", "ref", "lazy", "native"})
_FN_PREFIXES = frozenset(
  {
    "static",
    "native",
    "final",
    "override",
    "abstract",
    "virtual",
    "lazy",
    "async",
    "property",
  }
)


def _decl_head_of(tok: Token) -> str | None:
  """声明头：``enum``/``union`` 为硬关键字 Token；其余为 NAME。"""
  if tok.kind is TokenKind.KW_ENUM:
    return "enum"
  if tok.kind is TokenKind.KW_UNION:
    return "union"
  if tok.kind is TokenKind.NAME and tok.text in _DECL_HEADS_NAME:
    return tok.text
  return None


def parse_tokens(tokens: list[Token], source: str) -> SyntaxModule:
  items: list = []
  unsupported: list[str] = []
  i = 0
  n = len(tokens)

  def at_end() -> bool:
    return i >= n or tokens[i].kind is TokenKind.END

  def skip_nl() -> None:
    nonlocal i
    while i < n and tokens[i].kind in (
      TokenKind.NEWLINE,
      TokenKind.INDENT,
      TokenKind.DEDENT,
    ):
      i += 1

  while True:
    skip_nl()
    if at_end():
      break
    start_i = i
    start_span = tokens[i].span

    # delegate Name[…](…) -> R（无 def / 无代码块）
    if tokens[i].kind is TokenKind.NAME and tokens[i].text == "delegate":
      fn = _try_parse_function(tokens, source, i, unsupported)
      if fn is not None:
        node, ni = fn
        items.append(node)
        i = ni
        continue

    # static/native/… def（无装饰器）
    if tokens[i].kind is TokenKind.NAME and tokens[i].text in _FN_PREFIXES:
      fn = _try_parse_function(tokens, source, i, unsupported)
      if fn is not None:
        node, ni = fn
        items.append(node)
        i = ni
        continue

    # decorators + def / async def / class（含 @native_name 等）
    if tokens[i].kind is TokenKind.AT or (
      tokens[i].kind is TokenKind.NAME
      and tokens[i].text in ("def", "async")
    ):
      fn = _try_parse_function(tokens, source, i, unsupported)
      if fn is not None:
        node, ni = fn
        items.append(node)
        i = ni
        continue
      cls = _try_parse_decorated_class(tokens, source, i, unsupported)
      if cls is not None:
        node, ni = cls
        items.append(node)
        i = ni
        continue

    # 模块级 const NAME: T = ...
    if (
      tokens[i].kind is TokenKind.NAME
      and tokens[i].text == "const"
      and i + 1 < n
      and tokens[i + 1].kind is TokenKind.NAME
    ):
      cspan = tokens[i].span
      name = tokens[i + 1].text
      j = i + 2
      typ = None
      if j < n and tokens[j].kind is TokenKind.COLON:
        j += 1
        typ, j = parse_type(tokens, j, source=source)
      val = ""
      if j < n and tokens[j].kind is TokenKind.EQ:
        j += 1
        vs = j
        while j < n and tokens[j].kind not in (
          TokenKind.NEWLINE,
          TokenKind.DEDENT,
          TokenKind.END,
        ):
          j += 1
        if j > vs:
          val = source[tokens[vs].span.start : tokens[j - 1].span.end]
      end_pos = tokens[j - 1].span.end if j > i else cspan.end
      items.append(
        ModuleConstDecl(
          name=name,
          type_syntax=typ,
          value_source=val,
          span=Span(cspan.file_id, cspan.start, end_pos),
        )
      )
      i = j
      continue

    # import / from
    if tokens[i].kind is TokenKind.NAME and tokens[i].text in ("import", "from"):
      end_i = _find_next_top_stmt(tokens, i + 1)
      end_tok = tokens[end_i - 1] if end_i > i else tokens[i]
      src = source[tokens[i].span.start : end_tok.span.end]
      items.append(
        ImportStmt(
          source=src,
          span=Span(tokens[i].span.file_id, tokens[i].span.start, end_tok.span.end),
        )
      )
      i = end_i
      continue

    # type enum / type union
    if (
      tokens[i].kind is TokenKind.NAME
      and tokens[i].text == "type"
      and i + 1 < n
      and tokens[i + 1].kind in (TokenKind.KW_ENUM, TokenKind.KW_UNION)
    ):
      is_enum = tokens[i + 1].kind is TokenKind.KW_ENUM
      i += 2
      name, body_start, end_span, type_params, bases = _parse_decl_tail(
        tokens, source, i
      )
      end_i = _skip_block(tokens, body_start)
      block_end = tokens[min(end_i - 1, n - 1)].span.end if end_i > 0 else end_span.end
      if is_enum:
        members = _parse_enum_members(tokens, source, body_start)
        items.append(
          EnumDecl(
            name=name,
            is_type_enum=True,
            base_source=bases or None,
            flag=False,
            members=members,
            span=Span(start_span.file_id, start_span.start, block_end),
          )
        )
      else:
        items.append(
          ClassDecl(
            name=name,
            bases_source=bases or None,
            object_model=ObjectModel.VALUE,
            is_final=False,
            is_record=False,
            is_frozen=False,
            is_ordered=False,
            is_lazy=False,
            is_protocol=False,
            is_mixin=False,
            is_union=True,
            is_variant=False,
            members=_parse_class_members(tokens, source, body_start, unsupported),
            span=Span(start_span.file_id, start_span.start, block_end),
            is_native=False,
            type_params_source=type_params,
          )
        )
      i = end_i
      continue

    prefixes: list[str] = []
    j = i
    while (
      j < n
      and tokens[j].kind is TokenKind.NAME
      and tokens[j].text in _PREFIXES
    ):
      prefixes.append(tokens[j].text)
      j += 1

    head = _decl_head_of(tokens[j]) if j < n else None
    if head is not None:
      i = j + 1
      name, body_start, end_span, type_params, bases = _parse_decl_tail(
        tokens, source, i
      )
      end_i = _skip_block(tokens, body_start)
      block_end = (
        tokens[min(end_i - 1, n - 1)].span.end if end_i > 0 else end_span.end
      )
      span = Span(start_span.file_id, start_span.start, block_end)
      if "lazy" in prefixes:
        unsupported.append(f"lazy {head} {name}")
      if head == "enum":
        header_slice = source[start_span.start : block_end]
        items.append(
          EnumDecl(
            name=name,
            is_type_enum=False,
            base_source=bases or None,
            flag="flag" in header_slice,
            members=_parse_enum_members(tokens, source, body_start),
            span=span,
          )
        )
      else:
        items.append(
          ClassDecl(
            name=name,
            bases_source=bases or None,
            object_model=(
              ObjectModel.REF_COUNT if "ref" in prefixes else ObjectModel.VALUE
            ),
            is_final="final" in prefixes,
            is_record=head == "record",
            is_frozen="frozen" in prefixes,
            is_ordered="ordered" in prefixes,
            is_lazy="lazy" in prefixes,
            is_protocol=head == "protocol",
            is_mixin=head == "mixin",
            is_union=head == "union",
            is_variant=head == "variant",
            members=_parse_class_members(tokens, source, body_start, unsupported),
            span=span,
            is_native="native" in prefixes,
            type_params_source=type_params,
          )
        )
      i = end_i
      continue

    # opaque 直到下一顶层语句
    i = start_i
    end_i = _find_next_top_stmt(tokens, i + 1)
    end_tok = tokens[end_i - 1] if end_i > i else tokens[i]
    src = source[tokens[i].span.start : end_tok.span.end]
    items.append(
      OpaqueStmt(
        source=src,
        span=Span(tokens[i].span.file_id, tokens[i].span.start, end_tok.span.end),
      )
    )
    i = end_i

  mod_span = None
  if tokens:
    mod_span = Span(
      tokens[0].span.file_id,
      tokens[0].span.start,
      tokens[-1].span.end,
    )
  return SyntaxModule(items=items, span=mod_span, unsupported=unsupported)


def _try_parse_decorated_class(
  tokens: list[Token],
  source: str,
  i: int,
  unsupported: list[str],
) -> tuple[ClassDecl, int] | None:
  """``@deco…`` + 可选前缀 + class/record/…"""
  n = len(tokens)
  if i >= n or tokens[i].kind is not TokenKind.AT:
    return None
  start_span = tokens[i].span
  deco_start = i
  while i < n and tokens[i].kind is TokenKind.AT:
    while i < n and tokens[i].kind not in (TokenKind.NEWLINE, TokenKind.END):
      i += 1
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
      i += 1
  deco_src = source[tokens[deco_start].span.start : tokens[i - 1].span.end]

  prefixes: list[str] = []
  while (
    i < n
    and tokens[i].kind is TokenKind.NAME
    and tokens[i].text in _PREFIXES
  ):
    prefixes.append(tokens[i].text)
    i += 1

  head = _decl_head_of(tokens[i]) if i < n else None
  if head is None:
    return None
  i += 1
  name, body_start, end_span, type_params, bases = _parse_decl_tail(
    tokens, source, i
  )
  end_i = _skip_block(tokens, body_start)
  block_end = tokens[min(end_i - 1, n - 1)].span.end if end_i > 0 else end_span.end
  span = Span(start_span.file_id, start_span.start, block_end)
  if "lazy" in prefixes:
    unsupported.append(f"lazy {head} {name}")
  if head == "enum":
    return None
  node = ClassDecl(
    name=name,
    bases_source=bases or None,
    object_model=(
      ObjectModel.REF_COUNT if "ref" in prefixes else ObjectModel.VALUE
    ),
    is_final="final" in prefixes,
    is_record=head == "record",
    is_frozen="frozen" in prefixes,
    is_ordered="ordered" in prefixes,
    is_lazy="lazy" in prefixes,
    is_protocol=head == "protocol",
    is_mixin=head == "mixin",
    is_union=head == "union",
    is_variant=head == "variant",
    members=_parse_class_members(tokens, source, body_start, unsupported),
    span=span,
    decorators_source=deco_src,
    is_native="native" in prefixes,
    type_params_source=type_params,
  )
  return node, end_i


def _try_parse_function(
  tokens: list[Token],
  source: str,
  i: int,
  unsupported: list[str] | None = None,
) -> tuple[FunctionDecl, int] | None:
  n = len(tokens)
  start = i
  start_span = tokens[i].span
  deco_start = i
  while i < n and tokens[i].kind is TokenKind.AT:
    # skip decorator line(s)
    while i < n and tokens[i].kind not in (TokenKind.NEWLINE, TokenKind.END):
      i += 1
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
      i += 1
  deco_src = ""
  if i > deco_start:
    deco_src = source[tokens[deco_start].span.start : tokens[i - 1].span.end]

  fn_mods: list[str] = []
  while (
    i < n
    and tokens[i].kind is TokenKind.NAME
    and tokens[i].text in _FN_PREFIXES
    and tokens[i].text != "def"
  ):
    fn_mods.append(tokens[i].text)
    i += 1
  if (
    unsupported is not None
    and "static" in fn_mods
    and "async" in fn_mods
    and fn_mods.index("async") < fn_mods.index("static")
  ):
    unsupported.append("须写 static async（禁止 async 在 static 之前）")
  is_async = "async" in fn_mods
  is_delegate = False
  # 新表面：``delegate Name[…](…) -> R``（无 def）
  if i < n and tokens[i].kind is TokenKind.NAME and tokens[i].text == "delegate":
    is_delegate = True
    i += 1
  elif i < n and tokens[i].kind is TokenKind.NAME and tokens[i].text == "def":
    i += 1
  else:
    return None

  # 过渡：``@delegate`` + ``def`` → 视为 delegate 声明
  if not is_delegate and "@delegate" in deco_src.replace(" ", ""):
    is_delegate = True
    if unsupported is not None:
      unsupported.append("请改用 delegate Name(...) -> R（禁止 @delegate def）")

  if i >= n or tokens[i].kind is not TokenKind.NAME:
    return None
  name = tokens[i].text
  i += 1

  type_params = ""
  if i < n and tokens[i].kind is TokenKind.LSQB:
    open_i = i
    depth_sq = 0
    while i < n:
      if tokens[i].kind is TokenKind.LSQB:
        depth_sq += 1
      elif tokens[i].kind is TokenKind.RSQB:
        depth_sq -= 1
        if depth_sq == 0:
          i += 1
          type_params = source[tokens[open_i].span.start : tokens[i - 1].span.end]
          break
      i += 1

  if i >= n or tokens[i].kind is not TokenKind.LPAR:
    return None
  i += 1  # (
  param_list, i = parse_params(tokens, i, source=source)
  params = params_to_source(param_list)
  ret = None
  ret_ty = None
  if i < n and tokens[i].kind is TokenKind.RARROW:
    i += 1
    ret_ty, i = parse_type(
      tokens,
      i,
      source=source,
      stop=frozenset(
        {
          TokenKind.COLON,
          TokenKind.NEWLINE,
          TokenKind.END,
          TokenKind.DEDENT,
        }
      ),
    )
    if ret_ty is not None:
      ret = type_syntax_to_source(ret_ty)

  if is_delegate and ret is None and unsupported is not None:
    unsupported.append("delegate 须写显式返回类型（事件类用 -> None）")

  is_native = "native" in fn_mods
  bodyless = is_delegate or is_native

  has_colon = i < n and tokens[i].kind is TokenKind.COLON
  if has_colon:
    i += 1
  elif not bodyless:
    # 普通 def 通常要冒号；缺省时仍尝试吃体（兼容残缺表面）
    pass

  # 无代码块：``native def f(...) -> T`` / ``delegate F(...) -> None``
  if bodyless and not has_colon:
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
      i += 1
    end_i = i
    span_end = tokens[min(end_i - 1, n - 1)].span.end if end_i > start else start_span.end
    # 若有行尾注释落在 NEWLINE 前，用上一实词
    j = end_i - 1
    while j >= start and tokens[j].kind in (
      TokenKind.DEDENT,
      TokenKind.INDENT,
      TokenKind.NEWLINE,
    ):
      j -= 1
    if j >= start:
      span_end = tokens[j].span.end
    span = Span(start_span.file_id, start_span.start, span_end)
    return (
      FunctionDecl(
        name=name,
        decorators_source="" if is_delegate else deco_src,
        params_source=params,
        return_source=ret,
        body_source="...",
        is_async=False,
        span=span,
        is_static="static" in fn_mods,
        is_native=is_native,
        is_override="override" in fn_mods,
        is_final="final" in fn_mods,
        is_abstract="abstract" in fn_mods,
        is_virtual="virtual" in fn_mods,
        is_delegate=is_delegate,
        is_property="property" in fn_mods,
        return_type=ret_ty,
        params=param_list,
        body=[],
        type_params_source=type_params,
      ),
      end_i,
    )

  while i < n and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  body_start = i
  if i < n and tokens[i].kind is TokenKind.INDENT:
    i += 1
    body_start = i
  elif bodyless:
    # ``native def f() -> T:`` 后无缩进体（仅 ... 同行或空）
    end_i = i
    span_end = tokens[min(max(end_i - 1, start), n - 1)].span.end
    span = Span(start_span.file_id, start_span.start, span_end)
    return (
      FunctionDecl(
        name=name,
        decorators_source="" if is_delegate else deco_src,
        params_source=params,
        return_source=ret,
        body_source="...",
        is_async=False,
        span=span,
        is_static="static" in fn_mods,
        is_native=is_native,
        is_override="override" in fn_mods,
        is_final="final" in fn_mods,
        is_abstract="abstract" in fn_mods,
        is_virtual="virtual" in fn_mods,
        is_delegate=is_delegate,
        is_property="property" in fn_mods,
        return_type=ret_ty,
        params=param_list,
        body=[],
        type_params_source=type_params,
      ),
      end_i,
    )

  end_i = _skip_block(tokens, body_start)
  body_src = _function_body_source(tokens, source, body_start, end_i)
  # native/delegate 有体时仅允许 ``...`` / ``pass``；物化仍写存根
  if bodyless:
    stripped = body_src.strip()
    if stripped not in ("...", "pass", "..."):
      # 允许多行空白 + ...
      lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
      if lines and all(x in ("...", "pass") for x in lines):
        body_src = "..."
      elif unsupported is not None and is_native:
        unsupported.append("native def/方法勿写实现体（无代码块或仅 ...）")
      elif unsupported is not None and is_delegate:
        unsupported.append("delegate 勿写实现体")
    body_src = "..."
    body_stmts: list = []
  else:
    body_stmts, _ = parse_suite(tokens, body_start, end_i, source=source)
  span_end = tokens[min(end_i - 1, n - 1)].span.end if end_i > 0 else start_span.end
  # 函数 span 不含尾随「吞注释的 NEWLINE」
  j = end_i - 1
  while j >= body_start and tokens[j].kind in (
    TokenKind.DEDENT,
    TokenKind.INDENT,
    TokenKind.NEWLINE,
  ):
    j -= 1
  if j >= start:
    span_end = tokens[j].span.end
  span = Span(start_span.file_id, start_span.start, span_end)
  _ = start
  return (
    FunctionDecl(
      name=name,
      decorators_source="" if is_delegate else deco_src,
      params_source=params,
      return_source=ret,
      body_source=body_src,
      is_async=is_async,
      span=span,
      is_static="static" in fn_mods,
      is_native=is_native,
      is_override="override" in fn_mods,
      is_final="final" in fn_mods,
      is_abstract="abstract" in fn_mods,
      is_virtual="virtual" in fn_mods,
      is_delegate=is_delegate,
      is_property="property" in fn_mods,
      return_type=ret_ty,
      params=param_list,
      body=body_stmts,
      type_params_source=type_params,
    ),
    end_i,
  )


def _function_body_source(
  tokens: list[Token], source: str, body_start: int, end_i: int
) -> str:
  """取函数体原文；忽略 lexer 把块注释折进超长 NEWLINE 的尾跨度。"""
  if end_i <= body_start:
    return "pass"
  j = end_i - 1
  while j >= body_start and tokens[j].kind in (TokenKind.DEDENT, TokenKind.INDENT):
    j -= 1
  while j >= body_start and tokens[j].kind is TokenKind.NEWLINE:
    # 超长 NEWLINE（含中间 # 注释）不是函数体
    if tokens[j].span.end - tokens[j].span.start > 2:
      j -= 1
      continue
    j -= 1
  if j < body_start:
    return "pass"
  return source[tokens[body_start].span.start : tokens[j].span.end]


def _parse_decl_tail(
  tokens: list[Token], source: str, i: int
) -> tuple[str, int, Span, str, str]:
  """返回 ``(name, body_start, end_span, type_params_source, bases_source)``。

  ``type_params_source`` 含方括号（``[T]``）；``bases_source`` 含圆括号（``(A, friends=(B,))``）。
  """
  n = len(tokens)
  if i >= n or tokens[i].kind is not TokenKind.NAME:
    name = "_"
  else:
    name = tokens[i].text
    i += 1
  type_params = ""
  if i < n and tokens[i].kind is TokenKind.LSQB:
    open_i = i
    depth_sq = 0
    while i < n:
      if tokens[i].kind is TokenKind.LSQB:
        depth_sq += 1
      elif tokens[i].kind is TokenKind.RSQB:
        depth_sq -= 1
        if depth_sq == 0:
          i += 1
          type_params = source[tokens[open_i].span.start : tokens[i - 1].span.end]
          break
      i += 1
  bases = ""
  if i < n and tokens[i].kind is TokenKind.LPAR:
    open_i = i
    depth_par = 0
    while i < n:
      if tokens[i].kind is TokenKind.LPAR:
        depth_par += 1
      elif tokens[i].kind is TokenKind.RPAR:
        depth_par -= 1
        if depth_par == 0:
          i += 1
          bases = source[tokens[open_i].span.start : tokens[i - 1].span.end]
          break
      i += 1
  depth_sq = 0
  depth_par = 0
  while i < n:
    t = tokens[i]
    if t.kind is TokenKind.LSQB:
      depth_sq += 1
    elif t.kind is TokenKind.RSQB:
      depth_sq = max(0, depth_sq - 1)
    elif t.kind is TokenKind.LPAR:
      depth_par += 1
    elif t.kind is TokenKind.RPAR:
      depth_par = max(0, depth_par - 1)
    elif t.kind is TokenKind.COLON and depth_sq == 0 and depth_par == 0:
      i += 1
      break
    i += 1
  while i < n and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  body = i
  if i < n and tokens[i].kind is TokenKind.INDENT:
    i += 1
    body = i
  end_span = tokens[min(i, n - 1)].span
  return name, body, end_span, type_params, bases


def _try_parse_nested_decl_opaque(
  tokens: list[Token],
  source: str,
  i: int,
  unsupported: list[str] | None = None,
) -> tuple[OpaqueMember, int] | None:
  """类体内嵌套声明：收成单段 opaque，并改写成 ``@variant``/``@dataclass`` 等可 ``ast.parse`` 形式。"""
  n = len(tokens)
  start = i
  start_span = tokens[i].span
  prefixes: list[str] = []
  j = i
  while j < n and tokens[j].kind is TokenKind.NAME and tokens[j].text in _PREFIXES:
    prefixes.append(tokens[j].text)
    j += 1
  head = _decl_head_of(tokens[j]) if j < n else None
  if head is None:
    return None
  # 顶层已处理的大类声明不在此；此处仅嵌套成员
  name, body_start, _end_span, type_params, bases = _parse_decl_tail(tokens, source, j + 1)
  end_i = _skip_block(tokens, body_start)
  raw = source[tokens[start].span.start : tokens[min(end_i - 1, n - 1)].span.end]
  # 物化桥：去公共缩进后写成装饰器 + class（供 class 体 ast.parse）
  raw_ded = textwrap.dedent(raw.expandtabs(2)).strip("\n") + "\n"
  deco = {
    "variant": "@variant",
    "protocol": "@protocol",
    "mixin": "@mixin",
    "union": "@union",
    "record": "@dataclass",
    "enum": "@enum",
  }.get(head)
  if deco is None:
    text = raw_ded
  else:
    rest = raw_ded
    for p in prefixes:
      rest = rest.lstrip()
      if rest.startswith(p):
        rest = rest[len(p) :].lstrip()
    if rest.startswith(head):
      rest = rest[len(head) :].lstrip()
    # rest: ``Unknown:\n  pass``；体相对 class 再缩进一档
    text = f"{deco}\nclass {rest}"
    if not text.endswith("\n"):
      text += "\n"
  _ = unsupported
  _ = type_params
  _ = bases
  _ = name
  return (
    OpaqueMember(
      source=text,
      span=Span(start_span.file_id, start_span.start, tokens[min(end_i - 1, n - 1)].span.end),
    ),
    end_i,
  )


def _try_parse_property_block(
  tokens: list[Token],
  source: str,
  i: int,
  unsupported: list[str] | None = None,
) -> tuple[list[FunctionDecl], int] | None:
  """``[@deco] [static] property Name:`` + ``__get__``/``__set__``/``__post_set__``。"""
  n = len(tokens)
  start = i
  start_span = tokens[i].span
  deco_start = i
  while i < n and tokens[i].kind is TokenKind.AT:
    while i < n and tokens[i].kind not in (TokenKind.NEWLINE, TokenKind.END):
      i += 1
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
      i += 1
  deco_src = ""
  if i > deco_start:
    deco_src = source[tokens[deco_start].span.start : tokens[i - 1].span.end]

  is_static = False
  if (
    i < n
    and tokens[i].kind is TokenKind.NAME
    and tokens[i].text == "static"
    and i + 1 < n
    and tokens[i + 1].kind is TokenKind.NAME
    and tokens[i + 1].text == "property"
  ):
    is_static = True
    i += 1
  if i >= n or tokens[i].kind is not TokenKind.NAME or tokens[i].text != "property":
    return None
  i += 1
  # ``property def`` 走普通函数解析
  if i < n and tokens[i].kind is TokenKind.NAME and tokens[i].text == "def":
    return None
  if i >= n or tokens[i].kind is not TokenKind.NAME:
    return None
  prop_name = tokens[i].text
  i += 1
  if i >= n or tokens[i].kind is not TokenKind.COLON:
    return None
  i += 1
  while i < n and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  body_start = i
  if i < n and tokens[i].kind is TokenKind.INDENT:
    i += 1
    body_start = i
  end_i = _skip_block(tokens, body_start)

  accessors: dict[str, FunctionDecl] = {}
  j = body_start
  while j < end_i:
    if tokens[j].kind in (TokenKind.NEWLINE, TokenKind.INDENT, TokenKind.DEDENT):
      j += 1
      continue
    fn = _try_parse_function(tokens, source, j, unsupported)
    if fn is None:
      j += 1
      continue
    node, nj = fn
    if nj > end_i:
      break
    if node.name in ("__get__", "__set__", "__post_set__"):
      accessors[node.name] = node
    j = nj

  out: list[FunctionDecl] = []
  if "__post_set__" in accessors:
    post = accessors["__post_set__"]
    params = post.params_source
    if "__set__" in accessors and not params.strip():
      params = accessors["__set__"].params_source
    root = "@staticproperty" if is_static else "@property"
    out.append(
      FunctionDecl(
        name=prop_name,
        decorators_source=(deco_src + "\n" if deco_src else "") + f"{root}.postsetter",
        params_source=params,
        return_source=post.return_source,
        body_source=post.body_source,
        is_async=False,
        span=Span(start_span.file_id, start_span.start, post.span.end),
        is_static=is_static,
        is_property=False,
        return_type=post.return_type,
        params=list(post.params),
        body=list(post.body),
      )
    )
  else:
    if "__get__" in accessors:
      get = accessors["__get__"]
      out.append(
        FunctionDecl(
          name=prop_name,
          decorators_source=deco_src,
          params_source=get.params_source,
          return_source=get.return_source,
          body_source=get.body_source,
          is_async=False,
          span=Span(start_span.file_id, start_span.start, get.span.end),
          is_static=is_static,
          is_property=True,
          return_type=get.return_type,
          params=list(get.params),
          body=list(get.body),
        )
      )
    if "__set__" in accessors:
      sett = accessors["__set__"]
      root = "@staticproperty" if is_static else "@property"
      out.append(
        FunctionDecl(
          name=prop_name,
          decorators_source=f"{root}.setter",
          params_source=sett.params_source,
          return_source=sett.return_source,
          body_source=sett.body_source,
          is_async=False,
          span=sett.span,
          is_static=is_static,
          is_property=False,
          return_type=sett.return_type,
          params=list(sett.params),
          body=list(sett.body),
        )
      )
  if not out:
    # 空块：仍消费 span，避免整段变 Opaque 拖垮 class_rewrite
    span_end = tokens[min(end_i - 1, n - 1)].span.end if end_i > start else start_span.end
    out.append(
      FunctionDecl(
        name=prop_name,
        decorators_source=deco_src,
        params_source="self",
        return_source=None,
        body_source="...",
        is_async=False,
        span=Span(start_span.file_id, start_span.start, span_end),
        is_static=is_static,
        is_property=True,
        body=[],
      )
    )
  _ = start
  return out, end_i


def _skip_block(tokens: list[Token], body_start: int) -> int:
  n = len(tokens)
  i = body_start
  j = body_start - 1
  while j >= 0 and tokens[j].kind is TokenKind.NEWLINE:
    j -= 1
  if j >= 0 and tokens[j].kind is TokenKind.INDENT:
    i = body_start
    depth = 1
    while i < n and depth > 0:
      if tokens[i].kind is TokenKind.INDENT:
        depth += 1
      elif tokens[i].kind is TokenKind.DEDENT:
        depth -= 1
      i += 1
    return i
  while i < n and tokens[i].kind not in (TokenKind.NEWLINE, TokenKind.END):
    i += 1
  if i < n and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  return i


def _skip_suite_after_colon(tokens: list[Token], colon_i: int, end: int) -> int:
  """``:`` 后套件结束下标（含匹配 DEDENT）；无缩进块则吃掉本行。"""
  i = colon_i + 1
  while i < end and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  if i >= end or tokens[i].kind is not TokenKind.INDENT:
    while i < end and tokens[i].kind not in (TokenKind.NEWLINE, TokenKind.END):
      i += 1
    if i < end and tokens[i].kind is TokenKind.NEWLINE:
      i += 1
    return i
  depth = 0
  while i < end:
    if tokens[i].kind is TokenKind.INDENT:
      depth += 1
    elif tokens[i].kind is TokenKind.DEDENT:
      depth -= 1
      if depth == 0:
        return i + 1
    i += 1
  return end


def _skip_to_header_colon(tokens: list[Token], i: int, end: int) -> int | None:
  """从复合句头后扫到套件 ``:``（括号深度 0），返回冒号下标。"""
  depth_par = 0
  depth_sq = 0
  while i < end:
    k = tokens[i].kind
    if k is TokenKind.LPAR:
      depth_par += 1
    elif k is TokenKind.RPAR:
      depth_par = max(0, depth_par - 1)
    elif k is TokenKind.LSQB:
      depth_sq += 1
    elif k is TokenKind.RSQB:
      depth_sq = max(0, depth_sq - 1)
    elif k is TokenKind.COLON and depth_par == 0 and depth_sq == 0:
      return i
    elif k in (TokenKind.NEWLINE, TokenKind.DEDENT, TokenKind.END) and depth_par == 0 and depth_sq == 0:
      return None
    i += 1
  return None


_CLASS_COMPOUND_HEADS = frozenset({"if", "while", "for", "match", "try", "with"})
_FIELD_RESERVED = frozenset({"else", "elif", "except", "finally", "case"}) | _CLASS_COMPOUND_HEADS


def _try_parse_class_compound_opaque(
  tokens: list[Token],
  source: str,
  i: int,
  end: int,
) -> tuple[OpaqueMember, int] | None:
  """类体 ``if``/``while``/… 整段收成 opaque（含 ``elif``/``else``），避免分支成员摊平。"""
  if i >= end or tokens[i].kind is not TokenKind.NAME:
    return None
  head = tokens[i].text
  if head not in _CLASS_COMPOUND_HEADS:
    return None
  start = i
  start_span = tokens[i].span
  colon_i = _skip_to_header_colon(tokens, i + 1, end)
  if colon_i is None:
    return None
  i = _skip_suite_after_colon(tokens, colon_i, end)
  if head == "if":
    while True:
      while i < end and tokens[i].kind is TokenKind.NEWLINE:
        i += 1
      if i >= end or tokens[i].kind is not TokenKind.NAME:
        break
      nxt = tokens[i].text
      if nxt == "elif":
        colon_i = _skip_to_header_colon(tokens, i + 1, end)
        if colon_i is None:
          break
        i = _skip_suite_after_colon(tokens, colon_i, end)
        continue
      if nxt == "else":
        colon_i = _skip_to_header_colon(tokens, i + 1, end)
        if colon_i is None:
          break
        i = _skip_suite_after_colon(tokens, colon_i, end)
      break
  elif head == "try":
    while True:
      while i < end and tokens[i].kind is TokenKind.NEWLINE:
        i += 1
      if i >= end or tokens[i].kind is not TokenKind.NAME:
        break
      nxt = tokens[i].text
      if nxt not in ("except", "else", "finally"):
        break
      colon_i = _skip_to_header_colon(tokens, i + 1, end)
      if colon_i is None:
        break
      i = _skip_suite_after_colon(tokens, colon_i, end)
      if nxt == "finally":
        break
  # 源切片止于块内最后实词，保留后续兄弟成员的换行/缩进令牌
  j_end = i - 1
  while j_end >= start and tokens[j_end].kind in (
    TokenKind.DEDENT,
    TokenKind.INDENT,
    TokenKind.NEWLINE,
  ):
    j_end -= 1
  if j_end < start:
    return None
  # 从首行行首截取，使 ``if``/``elif`` 与体共享公共缩进，``dedent`` 才合法
  line_start = source.rfind("\n", 0, tokens[start].span.start) + 1
  raw = source[line_start : tokens[j_end].span.end]
  text = textwrap.dedent(raw.expandtabs(2)).strip("\n") + "\n"
  return (
    OpaqueMember(
      source=text,
      span=Span(start_span.file_id, start_span.start, tokens[j_end].span.end),
    ),
    i,
  )


def _find_next_top_stmt(tokens: list[Token], start: int) -> int:
  n = len(tokens)
  i = start
  depth = 0
  while i < n:
    t = tokens[i]
    if t.kind is TokenKind.INDENT:
      depth += 1
    elif t.kind is TokenKind.DEDENT:
      depth = max(0, depth - 1)
    elif t.kind is TokenKind.END:
      return i
    elif depth == 0 and t.kind is TokenKind.NEWLINE:
      j = i + 1
      while j < n and tokens[j].kind in (TokenKind.NEWLINE,):
        j += 1
      if j < n and tokens[j].kind not in (TokenKind.INDENT, TokenKind.DEDENT, TokenKind.END):
        if tokens[j].kind in (
          TokenKind.NAME,
          TokenKind.AT,
          TokenKind.KW_ENUM,
          TokenKind.KW_UNION,
        ):
          return j
    i += 1
  return n - 1 if n else 0


def _parse_enum_members(
  tokens: list[Token], source: str, body_start: int
) -> list[EnumMember]:
  members: list[EnumMember] = []
  end = _skip_block(tokens, body_start)
  i = body_start
  while i < end:
    if tokens[i].kind is TokenKind.NAME:
      name = tokens[i].text
      span = tokens[i].span
      i += 1
      val = None
      if i < end and tokens[i].kind is TokenKind.EQ:
        i += 1
        vs = i
        while i < end and tokens[i].kind not in (
          TokenKind.NEWLINE,
          TokenKind.DEDENT,
        ):
          i += 1
        if i > vs:
          val = source[tokens[vs].span.start : tokens[i - 1].span.end]
      members.append(EnumMember(name=name, value_source=val, span=span))
    else:
      i += 1
  return members


def _parse_class_members(
  tokens: list[Token],
  source: str,
  body_start: int,
  unsupported: list[str] | None = None,
) -> list:
  members: list = []
  end = _skip_block(tokens, body_start)
  i = body_start
  while i < end:
    if tokens[i].kind in (TokenKind.NEWLINE, TokenKind.INDENT, TokenKind.DEDENT):
      i += 1
      continue
    if (
      tokens[i].kind is TokenKind.NAME
      and tokens[i].text == "const"
      and i + 1 < end
      and tokens[i + 1].kind is TokenKind.NAME
    ):
      cspan = tokens[i].span
      name = tokens[i + 1].text
      i += 2
      typ = None
      if i < end and tokens[i].kind is TokenKind.COLON:
        i += 1
        typ, i = parse_type(tokens, i, source=source)
      val = ""
      if i < end and tokens[i].kind is TokenKind.EQ:
        i += 1
        vs = i
        while i < end and tokens[i].kind not in (
          TokenKind.NEWLINE,
          TokenKind.DEDENT,
        ):
          i += 1
        if i > vs:
          val = source[tokens[vs].span.start : tokens[i - 1].span.end]
      members.append(
        ConstField(
          name=name,
          type_syntax=typ,
          value_source=val,
          span=Span(cspan.file_id, cspan.start, tokens[max(i - 1, 0)].span.end),
        )
      )
      continue
    # ``property Name:`` / ``static property Name:`` 块 → 展开为 get/set 方法
    prop = _try_parse_property_block(tokens, source, i, unsupported)
    if prop is not None:
      nodes, ni = prop
      if ni <= end:
        members.extend(nodes)
        i = ni
        continue

    # 嵌套 ``variant`` / ``class`` / ``record`` … → 物化友好 opaque（避免 class_rewrite）
    nested = _try_parse_nested_decl_opaque(tokens, source, i, unsupported)
    if nested is not None:
      mem, ni = nested
      if ni <= end:
        members.append(mem)
        i = ni
        continue

    # 类体 ``if``/``while``/…（含 type_if 链）：整段 opaque，勿摊平分支字段/方法
    compound = _try_parse_class_compound_opaque(tokens, source, i, end)
    if compound is not None:
      mem, ni = compound
      members.append(mem)
      i = ni
      continue

    # 方法：delegate / @deco / static|native|… def（结构化，供 MidIR 直构）
    if tokens[i].kind is TokenKind.AT or (
      tokens[i].kind is TokenKind.NAME
      and tokens[i].text in _FN_PREFIXES | {"def", "async", "delegate"}
    ):
      fn = _try_parse_function(tokens, source, i, unsupported)
      if fn is not None:
        node, ni = fn
        if ni <= end:
          members.append(node)
          i = ni
          continue
    # 实例字段：NAME : type [= value]
    if (
      tokens[i].kind is TokenKind.NAME
      and i + 1 < end
      and tokens[i + 1].kind is TokenKind.COLON
      and tokens[i].text not in _FN_PREFIXES | _DECL_HEADS | _PREFIXES | _FIELD_RESERVED
    ):
      fname = tokens[i].text
      fspan = tokens[i].span
      i += 2
      ftyp, i = parse_type(tokens, i, source=source)
      fval = ""
      if i < end and tokens[i].kind is TokenKind.EQ:
        i += 1
        vs = i
        while i < end and tokens[i].kind not in (
          TokenKind.NEWLINE,
          TokenKind.DEDENT,
        ):
          i += 1
        if i > vs:
          fval = source[tokens[vs].span.start : tokens[i - 1].span.end]
      members.append(
        FieldDecl(
          name=fname,
          type_syntax=ftyp,
          value_source=fval,
          span=Span(
            fspan.file_id,
            fspan.start,
            tokens[max(i - 1, 0)].span.end,
          ),
        )
      )
      continue
    vs = i
    while i < end and tokens[i].kind not in (TokenKind.NEWLINE, TokenKind.DEDENT):
      i += 1
    if i > vs:
      src = source[tokens[vs].span.start : tokens[i - 1].span.end]
      members.append(
        OpaqueMember(
          source=src,
          span=Span(tokens[vs].span.file_id, tokens[vs].span.start, tokens[i - 1].span.end),
        )
      )
    else:
      i += 1
  return members
