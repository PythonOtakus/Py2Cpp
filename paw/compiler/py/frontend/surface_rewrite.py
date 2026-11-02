"""将 Paw 表面声明改写为旧方言装饰器源码（兼容桥输入）。

``enum``/``union`` 为硬关键字（``KW_*``）；其余声明头为软关键字 NAME。
类型前缀 ``ref``/``lazy`` 仅在注解位置识别。
编辑一律合并为互不重叠的 ``(start, end, new_text)``，自右向左应用。
"""
from __future__ import annotations

import re

from .lexer import Lexer
from .source import FileId
from .tokens import Token, TokenKind

_FLAG_ITEM = re.compile(
  r"(?:^|,)\s*flag\s*=\s*True\s*(?=,|$)",
  re.MULTILINE,
)

_CLASS_HEADS_NAME = frozenset(
  {"class", "record", "variant", "protocol", "mixin"}
)


def _decl_head_of(tok: Token) -> str | None:
  """声明头：``enum``/``union`` 为 ``KW_*``；其余为 NAME。"""
  if tok.kind is TokenKind.KW_ENUM:
    return "enum"
  if tok.kind is TokenKind.KW_UNION:
    return "union"
  if tok.kind is TokenKind.NAME and tok.text in _CLASS_HEADS_NAME:
    return tok.text
  return None
_TYPE_PREFIX_PREV = frozenset(
  {
    TokenKind.COLON,
    TokenKind.RARROW,
    TokenKind.COMMA,
    TokenKind.LSQB,
    TokenKind.LPAR,
  }
)


def _skip_name_and_params(tokens: list[Token], j: int) -> int:
  n = len(tokens)
  if j < n and tokens[j].kind is TokenKind.NAME:
    j += 1
  if j < n and tokens[j].kind is TokenKind.LSQB:
    depth = 1
    j += 1
    while j < n and depth:
      if tokens[j].kind is TokenKind.LSQB:
        depth += 1
      elif tokens[j].kind is TokenKind.RSQB:
        depth -= 1
      j += 1
  return j


def _paren_span(tokens: list[Token], j: int) -> tuple[int, int] | None:
  n = len(tokens)
  if j >= n or tokens[j].kind is not TokenKind.LPAR:
    return None
  depth = 0
  k = j
  while k < n:
    t = tokens[k]
    if t.kind is TokenKind.LPAR:
      depth += 1
    elif t.kind is TokenKind.RPAR:
      depth -= 1
      if depth == 0:
        return j, k
    k += 1
  return None


def _source_slice(source: str, tokens: list[Token], a: int, b: int) -> str:
  if a >= b:
    return ""
  return source[tokens[a].span.start : tokens[b - 1].span.end]


def _line_indent(source: str, pos: int) -> str:
  """``pos`` 所在物理行的前导空白。"""
  line_start = source.rfind("\n", 0, pos) + 1
  i = line_start
  while i < pos and source[i] in " \t":
    i += 1
  return source[line_start:i]


def rewrite_type_prefixes_fragment(source: str) -> str:
  """仅改写片段中的 ``ref``/``lazy`` 类型前缀（供 params/return 物化）。"""
  if not source or ("ref" not in source and "lazy" not in source):
    return source
  fid = FileId(0)
  tokens = Lexer(source, fid).tokenize()
  edits: list[tuple[int, int, str]] = []
  _collect_type_prefix_edits(source, tokens, edits)
  return _apply_edits(source, edits)


def rewrite_paw_to_legacy(source: str, *, file_id: FileId | None = None) -> str:
  fid = file_id or FileId(0)
  tokens = Lexer(source, fid).tokenize()
  return _rewrite_tokens(source, tokens)


def _rewrite_tokens(source: str, tokens: list[Token]) -> str:
  edits: list[tuple[int, int, str]] = []
  _collect_decl_edits(source, tokens, edits)
  _collect_type_prefix_edits(source, tokens, edits)
  text = _apply_edits(source, edits)
  # 声明改写后再扫箭头类型（Function/Callable 物化桥）
  return _rewrite_arrow_types_to_legacy(text)


def _rewrite_arrow_types_to_legacy(source: str) -> str:
  """注解位置的裸箭头 / ``Callable[arrow]`` → ``Function``/``Callable`` Subscript。

  只改写：
  - ``:`` 之后的注解（参数/字段）
  - ``Callable[…->…]`` 整段
  不改写 ``def f(...) -> R`` 的函数返回箭头。
  """
  from .type_parse import parse_type, type_syntax_to_legacy_annotation

  if "->" not in source:
    return source
  fid = FileId(0)
  tokens = Lexer(source, fid).tokenize()
  edits: list[tuple[int, int, str]] = []
  n = len(tokens)
  i = 0
  while i < n:
    if tokens[i].kind is not TokenKind.RARROW:
      i += 1
      continue
    # 判定是否在 Callable[ … ]
    in_callable = False
    start_i = i
    j = i - 1
    depth_sq = 0
    depth_par = 0
    while j >= 0:
      t = tokens[j]
      if t.kind is TokenKind.RSQB:
        depth_sq += 1
      elif t.kind is TokenKind.LSQB:
        if depth_sq:
          depth_sq -= 1
        elif (
          j >= 1
          and tokens[j - 1].kind is TokenKind.NAME
          and tokens[j - 1].text == "Callable"
        ):
          in_callable = True
          start_i = j - 1
          break
        else:
          break
      elif t.kind is TokenKind.RPAR:
        depth_par += 1
      elif t.kind is TokenKind.LPAR:
        if depth_par:
          depth_par -= 1
        else:
          start_i = j
          break
      elif depth_sq == 0 and depth_par == 0 and t.kind is TokenKind.COLON:
        # 注解上下文：类型从冒号后开始
        start_i = j + 1
        break
      elif depth_sq == 0 and depth_par == 0 and t.kind in (
        TokenKind.COMMA,
        TokenKind.EQ,
        TokenKind.NEWLINE,
        TokenKind.INDENT,
        TokenKind.DEDENT,
      ):
        start_i = j + 1
        break
      elif depth_sq == 0 and depth_par == 0 and t.kind is TokenKind.NAME:
        start_i = j
        k = j - 1
        while (
          k >= 1
          and tokens[k].kind is TokenKind.DOT
          and tokens[k - 1].kind is TokenKind.NAME
        ):
          start_i = k - 1
          k -= 2
        # ``Callable[int -> …]``：左邻是 ``[`` 时继续向左，勿在参类型 NAME 处截断
        prev = _prev_significant(tokens, start_i)
        if prev is not None and prev.kind is TokenKind.LSQB:
          j -= 1
          continue
        # 若紧前不是注解语境（: 或 Callable[），可能是 def 返回 —— 再向左确认
        if prev is not None and prev.kind is TokenKind.RPAR and not in_callable:
          # ``) ->``：函数返回，跳过
          start_i = -1
        break
      j -= 1
    else:
      start_i = 0

    if start_i < 0:
      i += 1
      continue

    # ``) ->`` 且非 Callable：多半是 ``def f(...) -> R``，勿改写
    prev = _prev_significant(tokens, i)
    if (
      not in_callable
      and prev is not None
      and prev.kind is TokenKind.RPAR
    ):
      # 仅当起点紧跟字段/参数注解冒号，且片段本身是类型（非形参表）时才改写
      ann_colon = start_i > 0 and tokens[start_i - 1].kind is TokenKind.COLON
      if not ann_colon:
        i += 1
        continue
      # ``name: (T) -> R``：start 为 LPAR；``name: T -> R`` 不会走 RPAR 前回
      if tokens[start_i].kind is TokenKind.LPAR:
        # 形参表特征：括号内含 ``name:`` 模式 → 跳过
        depth = 0
        looks_like_params = False
        for k in range(start_i, i):
          t = tokens[k]
          if t.kind is TokenKind.LPAR:
            depth += 1
          elif t.kind is TokenKind.RPAR:
            depth -= 1
          elif (
            depth == 1
            and t.kind is TokenKind.NAME
            and k + 1 < n
            and tokens[k + 1].kind is TokenKind.COLON
          ):
            looks_like_params = True
            break
        if looks_like_params:
          i += 1
          continue

    end_i = _skip_type_expr(tokens, i + 1)
    # Callable[arrow]：吃到 ]
    if in_callable:
      while end_i < n and tokens[end_i].kind is not TokenKind.RSQB:
        if tokens[end_i].kind is TokenKind.END:
          break
        end_i += 1
      if end_i < n and tokens[end_i].kind is TokenKind.RSQB:
        end_i += 1

    if start_i >= end_i or end_i <= i:
      i += 1
      continue
    frag = source[tokens[start_i].span.start : tokens[end_i - 1].span.end]
    ftoks = Lexer(frag, fid).tokenize()
    ty, _ = parse_type(ftoks, 0, source=frag)
    if ty is None:
      i = max(end_i, i + 1)
      continue
    legacy = type_syntax_to_legacy_annotation(ty)
    if legacy != frag:
      edits.append((tokens[start_i].span.start, tokens[end_i - 1].span.end, legacy))
    i = max(end_i, i + 1)
  return _apply_edits(source, edits) if edits else source


def _prev_significant(tokens: list[Token], i: int) -> Token | None:
  j = i - 1
  while j >= 0 and tokens[j].kind in (
    TokenKind.NEWLINE,
    TokenKind.INDENT,
    TokenKind.DEDENT,
  ):
    j -= 1
  return tokens[j] if j >= 0 else None


def _skip_type_expr(tokens: list[Token], j: int) -> int:
  """从类型起始 token 跳到类型表达式结束后（不含尾随 ``@Meta``）。"""
  n = len(tokens)
  if j >= n:
    return j
  depth_sq = 0
  depth_par = 0
  while j < n:
    t = tokens[j]
    if t.kind is TokenKind.END:
      break
    if depth_sq == 0 and depth_par == 0:
      if t.kind in (
        TokenKind.COMMA,
        TokenKind.EQ,
        TokenKind.COLON,
        TokenKind.NEWLINE,
        TokenKind.DEDENT,
        TokenKind.INDENT,
        TokenKind.AT,
        TokenKind.RPAR,
        TokenKind.RSQB,
        TokenKind.RBRACE,
      ):
        break
      if t.kind is TokenKind.RARROW and j > 0:
        # 返回注解 ``-> T:`` 的冒号在外层；类型内 Callable 的 ``->`` 继续
        pass
    if t.kind is TokenKind.LSQB:
      depth_sq += 1
    elif t.kind is TokenKind.RSQB:
      if depth_sq:
        depth_sq -= 1
      else:
        break
    elif t.kind is TokenKind.LPAR:
      depth_par += 1
    elif t.kind is TokenKind.RPAR:
      if depth_par:
        depth_par -= 1
      else:
        break
    j += 1
  return j


def _collect_type_prefix_edits(
  source: str, tokens: list[Token], edits: list[tuple[int, int, str]]
) -> None:
  n = len(tokens)
  i = 0
  while i < n:
    tok = tokens[i]
    if tok.kind is TokenKind.END:
      break
    if tok.kind is not TokenKind.NAME or tok.text not in ("ref", "lazy"):
      i += 1
      continue
    prev = _prev_significant(tokens, i)
    if prev is None or prev.kind not in _TYPE_PREFIX_PREV:
      i += 1
      continue
    # ``ref class`` 等声明头由声明改写处理
    if tok.text == "ref" and i + 1 < n and _decl_head_of(tokens[i + 1]) is not None:
      i += 1
      continue
    markers: list[str] = []
    j = i
    if tokens[j].text == "lazy":
      markers.append("lazy")
      j += 1
      if j < n and tokens[j].kind is TokenKind.NAME and tokens[j].text == "ref":
        markers.append("ref")
        j += 1
      elif j < n and tokens[j].kind is TokenKind.NAME and tokens[j].text == "lazy":
        # 重复 lazy：跳过改写
        i += 1
        continue
    elif tokens[j].text == "ref":
      markers.append("ref")
      j += 1
      if j < n and tokens[j].kind is TokenKind.NAME and tokens[j].text == "lazy":
        # 反序 ``ref lazy``：不改写（由诊断拒绝）
        i += 1
        continue
    else:
      i += 1
      continue
    if j >= n or tokens[j].kind not in (
      TokenKind.NAME,
      TokenKind.LPAR,
      TokenKind.LSQB,
    ):
      i += 1
      continue
    type_end = _skip_type_expr(tokens, j)
    if type_end <= j:
      i += 1
      continue
    type_text = source[tokens[j].span.start : tokens[type_end - 1].span.end]
    suffix = ""
    if "ref" in markers:
      suffix += " @ref"
    if "lazy" in markers:
      suffix += " @lazy"
    edits.append((tokens[i].span.start, tokens[type_end - 1].span.end, type_text + suffix))
    i = type_end


def _find_matching_block_end(tokens: list[Token], colon_i: int) -> int:
  """``NAME:`` 后 INDENT 块的结束 token 下标（DEDENT 后）。"""
  n = len(tokens)
  i = colon_i + 1
  while i < n and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  if i >= n or tokens[i].kind is not TokenKind.INDENT:
    return colon_i + 1
  depth = 0
  while i < n:
    if tokens[i].kind is TokenKind.INDENT:
      depth += 1
    elif tokens[i].kind is TokenKind.DEDENT:
      depth -= 1
      if depth == 0:
        return i + 1
    i += 1
  return n


def _extract_accessor_defs(
  source: str, tokens: list[Token], block_start: int, block_end: int
) -> dict[str, tuple[str, str, str]]:
  """块内 ``def __get__/__set__/__post_set__`` → name → (params, return, body)。"""
  n = min(block_end, len(tokens))
  out: dict[str, tuple[str, str, str]] = {}
  i = block_start
  while i < n:
    if tokens[i].kind is TokenKind.NAME and tokens[i].text == "def":
      if i + 1 >= n or tokens[i + 1].kind is not TokenKind.NAME:
        i += 1
        continue
      aname = tokens[i + 1].text
      if aname not in ("__get__", "__set__", "__post_set__"):
        i += 1
        continue
      j = i + 2
      if j >= n or tokens[j].kind is not TokenKind.LPAR:
        i += 1
        continue
      ps = j + 1
      depth = 0
      while j < n:
        if tokens[j].kind is TokenKind.LPAR:
          depth += 1
        elif tokens[j].kind is TokenKind.RPAR:
          depth -= 1
          if depth == 0:
            break
        j += 1
      params = (
        source[tokens[ps].span.start : tokens[j - 1].span.end] if j > ps else ""
      )
      j += 1
      ret = ""
      if j < n and tokens[j].kind is TokenKind.RARROW:
        j += 1
        rs = j
        while j < n and tokens[j].kind not in (
          TokenKind.COLON,
          TokenKind.NEWLINE,
          TokenKind.END,
        ):
          j += 1
        if j > rs:
          ret = source[tokens[rs].span.start : tokens[j - 1].span.end]
      if j < n and tokens[j].kind is TokenKind.COLON:
        j += 1
      while j < n and tokens[j].kind is TokenKind.NEWLINE:
        j += 1
      body_start = j
      if j < n and tokens[j].kind is TokenKind.INDENT:
        j += 1
        body_start = j
        depth = 1
        while j < n and depth:
          if tokens[j].kind is TokenKind.INDENT:
            depth += 1
          elif tokens[j].kind is TokenKind.DEDENT:
            depth -= 1
            if depth == 0:
              break
          j += 1
        body_end = j
      else:
        while j < n and tokens[j].kind not in (
          TokenKind.NEWLINE,
          TokenKind.DEDENT,
          TokenKind.END,
        ):
          j += 1
        body_end = j
      if body_end > body_start:
        # 取到最后一个非 DEDENT/NEWLINE
        be = body_end - 1
        while be >= body_start and tokens[be].kind in (
          TokenKind.DEDENT,
          TokenKind.NEWLINE,
        ):
          be -= 1
        first_pos = tokens[body_start].span.start
        line_start = source.rfind("\n", 0, first_pos) + 1
        ws = line_start
        while ws < first_pos and source[ws] in " \t":
          ws += 1
        src_start = line_start if ws == first_pos else first_pos
        body = source[src_start : tokens[be].span.end]
      else:
        body = "pass"
      out[aname] = (params, ret, body)
      i = max(j, i + 1)
      continue
    i += 1
  return out


def _reindent_method_body(body: str, indent: str) -> str:
  """访问器体挂到 ``indent + '  '`` 下。"""
  lines = body.splitlines()
  min_ws = None
  for ln in lines:
    if ln.strip():
      ws = len(ln) - len(ln.lstrip(" \t"))
      min_ws = ws if min_ws is None else min(min_ws, ws)
  min_ws = min_ws or 0
  prefix = indent + "  "
  out: list[str] = []
  for ln in lines:
    if not ln.strip():
      out.append("")
    else:
      out.append(prefix + ln[min_ws:])
  return "\n".join(out) + "\n"


def _emit_property_methods(
  *,
  indent: str,
  prop_name: str,
  static: bool,
  accessors: dict[str, tuple[str, str, str]],
  extra_deco_lines: list[str],
) -> str:
  """将 property 块访问器写成 legacy ``@property`` / setter / postsetter。"""
  root = "@staticproperty" if static else "@property"
  parts: list[str] = []
  # 有 post_set 时旧入口与 getter/setter 互斥：只发 postsetter（后端合成 get/set）
  if "__post_set__" in accessors:
    params, _ret, body = accessors["__post_set__"]
    if "__set__" in accessors and not params.strip():
      params = accessors["__set__"][0]
    head = f"{indent}{root}.postsetter\n"
    for d in extra_deco_lines:
      head += f"{indent}{d}\n"
    parts.append(f"{head}{indent}def {prop_name}({params}):\n")
    parts.append(_reindent_method_body(body, indent))
    return "".join(parts)
  if "__get__" in accessors:
    params, ret, body = accessors["__get__"]
    ret_s = f" -> {ret}" if ret else ""
    head = f"{indent}{root}\n"
    for d in extra_deco_lines:
      head += f"{indent}{d}\n"
    parts.append(f"{head}{indent}def {prop_name}({params}){ret_s}:\n")
    parts.append(_reindent_method_body(body, indent))
  if "__set__" in accessors:
    params, ret, body = accessors["__set__"]
    ret_s = f" -> {ret}" if ret else ""
    parts.append(f"{indent}{root}.setter\n{indent}def {prop_name}({params}){ret_s}:\n")
    parts.append(_reindent_method_body(body, indent))
  return "".join(parts)


def _collect_decl_edits(
  source: str, tokens: list[Token], edits: list[tuple[int, int, str]]
) -> None:
  i = 0
  n = len(tokens)
  at_stmt_start = True

  def kind(j: int) -> TokenKind | None:
    if j < 0 or j >= n:
      return None
    return tokens[j].kind

  def text(j: int) -> str:
    return tokens[j].text if 0 <= j < n else ""

  while i < n:
    tok = tokens[i]
    if tok.kind is TokenKind.END:
      break
    if tok.kind is TokenKind.NEWLINE:
      at_stmt_start = True
      i += 1
      continue
    if tok.kind in (TokenKind.INDENT, TokenKind.DEDENT):
      i += 1
      continue
    if not at_stmt_start:
      i += 1
      continue

    if tok.kind is TokenKind.NAME and tok.text == "type":
      type_head = _decl_head_of(tokens[i + 1]) if i + 1 < n else None
      if type_head in ("enum", "union"):
        deco = "@enum.mro" if type_head == "enum" else "@union.mro"
        ind = _line_indent(source, tok.span.start)
        edits.append(
          (tok.span.start, tokens[i + 1].span.end, f"{deco}\n{ind}class")
        )
        at_stmt_start = False
        i += 2
        continue

    # ``static property`` / ``property`` 声明
    prop_static = False
    prop_i = i
    if (
      kind(i) is TokenKind.NAME
      and text(i) == "static"
      and kind(i + 1) is TokenKind.NAME
      and text(i + 1) == "property"
    ):
      prop_static = True
      prop_i = i + 1
    if kind(prop_i) is TokenKind.NAME and text(prop_i) == "property":
      line_indent = _line_indent(source, tokens[i].span.start)
      # 从行首替换，避免残留缩进叠在 ``@property`` 前
      line_start = source.rfind("\n", 0, tokens[i].span.start) + 1
      j = prop_i + 1
      # property def Name
      if kind(j) is TokenKind.NAME and text(j) == "def":
        root = "@staticproperty" if prop_static else "@property"
        edits.append(
          (
            line_start,
            tokens[j].span.end,
            f"{line_indent}{root}\n{line_indent}def",
          )
        )
        at_stmt_start = False
        i = j + 1
        continue
      # property Name:
      if kind(j) is TokenKind.NAME:
        prop_name = text(j)
        k = j + 1
        if kind(k) is TokenKind.COLON:
          block_end = _find_matching_block_end(tokens, k)
          accessors = _extract_accessor_defs(source, tokens, k + 1, block_end)
          repl = _emit_property_methods(
            indent=line_indent,
            prop_name=prop_name,
            static=prop_static,
            accessors=accessors,
            extra_deco_lines=[],
          )
          # 结束于块内最后实词，保留其后换行给下一声明
          j_end = block_end - 1
          while j_end >= i and tokens[j_end].kind in (
            TokenKind.DEDENT,
            TokenKind.INDENT,
            TokenKind.NEWLINE,
          ):
            j_end -= 1
          end_pos = tokens[j_end].span.end if j_end >= i else tokens[k].span.end
          if end_pos < len(source) and source[end_pos] == "\n":
            end_pos += 1
          if not repl.endswith("\n"):
            repl += "\n"
          edits.append((line_start, end_pos, repl))
          # block_end 指向下一条声明起始 token
          at_stmt_start = True
          i = block_end
          continue

    # ``override def`` / ``virtual def`` / ``static def`` / ``native def`` …
    # 注意：``static property`` 已在上方处理
    if kind(i) is TokenKind.NAME and text(i) in (
      "static",
      "native",
      "async",
      "final",
      "override",
      "abstract",
      "virtual",
      "lazy",
    ):
      mods: list[str] = []
      j = i
      while kind(j) is TokenKind.NAME and text(j) in (
        "static",
        "native",
        "async",
        "final",
        "override",
        "abstract",
        "virtual",
        "lazy",
      ):
        mods.append(text(j))
        j += 1
      if kind(j) is TokenKind.NAME and text(j) == "property":
        # ``static lazy property`` 等：暂不支持 lazy property（后端无声明缓存）
        at_stmt_start = False
        i = j
        continue
      if kind(j) is TokenKind.NAME and text(j) == "def":
        line_indent = _line_indent(source, tok.span.start)
        decos: list[str] = []
        if "static" in mods:
          decos.append("@staticmethod")
        if "native" in mods:
          decos.append("@native")
        if "final" in mods:
          decos.append("@final")
        if "override" in mods:
          decos.append("@override")
        if "abstract" in mods:
          decos.append("@abstract")
        if "virtual" in mods:
          decos.append("@virtual")
        # lazy 留给后续；async 保留在 def 前
        keep = []
        if "async" in mods:
          keep.append("async")
        prefix = "".join(d + "\n" + line_indent for d in decos)
        repl_head = (" ".join(keep) + " " if keep else "") + "def"
        edits.append((tokens[i].span.start, tokens[j].span.end, prefix + repl_head))
        # bodyless ``native def f(...)``：补 ``: ...`` 以便 CPython 解析
        if "native" in mods:
          k = j + 1
          depth = 0
          saw_colon = False
          while k < n:
            tk = tokens[k]
            if tk.kind is TokenKind.LPAR:
              depth += 1
            elif tk.kind is TokenKind.RPAR:
              depth = max(0, depth - 1)
            elif depth == 0 and tk.kind is TokenKind.COLON:
              saw_colon = True
              break
            elif depth == 0 and tk.kind in (
              TokenKind.NEWLINE,
              TokenKind.DEDENT,
              TokenKind.END,
            ):
              break
            k += 1
          if not saw_colon and k > j:
            # 在签名末尾插入 ``: ...``
            end_pos = tokens[k - 1].span.end if k > 0 else tokens[j].span.end
            # 跳过已在 NEWLINE 上时插在前一 token 后
            inserts = ": ..."
            edits.append((end_pos, end_pos, inserts))
        at_stmt_start = False
        i = j + 1
        continue

    prefixes: list[str] = []
    j = i
    while kind(j) is TokenKind.NAME and text(j) in (
      "frozen",
      "ordered",
      "final",
      "ref",
      "lazy",
      "native",
    ):
      prefixes.append(text(j))
      j += 1

    head = _decl_head_of(tokens[j]) if j < n else None
    if head is not None:
      # 硬关键字后接 ``.`` 非法作标识符；软关键字 ``X.mro`` 赋值不是声明
      if head in ("enum", "union", "variant", "protocol", "mixin", "record") and kind(
        j + 1
      ) is TokenKind.DOT:
        at_stmt_start = False
        i = j + 1
        continue
      # 声明须有类型名
      if head != "class" and kind(j + 1) is not TokenKind.NAME:
        at_stmt_start = False
        i = j + 1
        continue

      decos: list[str] = []
      if "ref" in prefixes:
        decos.append("@refcount")
      if "final" in prefixes:
        decos.append("@final")
      if "native" in prefixes:
        decos.append("@native")

      line_indent = _line_indent(source, tokens[i].span.start)

      if head == "enum":
        after = _skip_name_and_params(tokens, j + 1)
        paren = _paren_span(tokens, after)
        deco = "@enum"
        if paren is not None:
          open_i, close_i = paren
          inner = _source_slice(source, tokens, open_i + 1, close_i)
          has_flag = bool(_FLAG_ITEM.search(inner))
          cleaned = _FLAG_ITEM.sub("", inner)
          cleaned = re.sub(r"^\s*,\s*", "", cleaned)
          cleaned = re.sub(r"\s*,\s*$", "", cleaned)
          cleaned = re.sub(r"\s*,\s*,", ",", cleaned).strip()
          if has_flag:
            deco = "@enum(flag=True)"
          if cleaned:
            edits.append(
              (tokens[open_i].span.start, tokens[close_i].span.end, f"({cleaned})")
            )
          else:
            edits.append((tokens[open_i].span.start, tokens[close_i].span.end, ""))
        edits.append(
          (
            tokens[i].span.start,
            tokens[j].span.end,
            f"{deco}\n{line_indent}class",
          )
        )
      elif head == "record":
        args: list[str] = []
        if "frozen" in prefixes:
          args.append("frozen=True")
        if "ordered" in prefixes:
          args.append("order=True")
        arg_s = f"({', '.join(args)})" if args else ""
        edits.append(
          (
            tokens[i].span.start,
            tokens[j].span.end,
            f"@dataclass{arg_s}\n{line_indent}class",
          )
        )
      elif head in ("union", "variant", "protocol", "mixin"):
        edits.append(
          (
            tokens[i].span.start,
            tokens[j].span.end,
            f"@{head}\n{line_indent}class",
          )
        )
      else:
        prefix = "".join(d + "\n" + line_indent for d in decos)
        if prefixes:
          edits.append((tokens[i].span.start, tokens[j].span.start, prefix))
        elif decos:
          edits.append((tokens[j].span.start, tokens[j].span.start, prefix))
      at_stmt_start = False
      i = j + 1
      continue

    if tok.kind is TokenKind.NAME and tok.text == "const" and kind(i + 1) is TokenKind.NAME:
      name_tok = tokens[i + 1]
      edits.append((tok.span.start, name_tok.span.start, ""))
      k = i + 2
      while k < n and kind(k) is not TokenKind.EQ and kind(k) not in (
        TokenKind.NEWLINE,
        TokenKind.END,
      ):
        k += 1
      if kind(k) is TokenKind.EQ:
        edits.append((tokens[k].span.start, tokens[k].span.start, "@const "))
      at_stmt_start = False
      i = i + 2
      continue

    if tok.kind is TokenKind.NAME and tok.text == "optional" and kind(i + 1) is TokenKind.NAME:
      name_tok = tokens[i + 1]
      edits.append((tok.span.start, name_tok.span.start, ""))
      k = i + 2
      while k < n and kind(k) is not TokenKind.EQ and kind(k) not in (
        TokenKind.NEWLINE,
        TokenKind.END,
      ):
        k += 1
      if kind(k) is TokenKind.EQ:
        edits.append((tokens[k].span.start, tokens[k].span.start, "@optional "))
      at_stmt_start = False
      i = i + 2
      continue

    at_stmt_start = False
    i += 1


def _apply_edits(source: str, edits: list[tuple[int, int, str]]) -> str:
  # 按 start 降序；同 start 时先做非空 tip（end>start）再做纯插入
  edits_sorted = sorted(edits, key=lambda e: (e[0], 0 if e[1] > e[0] else 1), reverse=True)
  out = source
  last_start = None
  for start, end, text in edits_sorted:
    if last_start is not None and end > last_start:
      # 与已应用区间重叠：跳过（防御）
      continue
    out = out[:start] + text + out[end:]
    last_start = start
  return out
