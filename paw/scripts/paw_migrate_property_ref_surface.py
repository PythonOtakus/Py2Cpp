"""将 ``*.paw`` 中旧 property / @ref/@lazy / async static 迁到 Paw 新表面。

- ``async static def`` → ``static async def``
- ``T @ref @lazy`` / ``T @ref`` / ``T @lazy`` → ``lazy ref T`` / ``ref T`` / ``lazy T``
- ``@property``(+其它装饰器) ``def`` → 装饰器保留 + ``property def``
- ``@staticproperty`` → ``static property def``
- getter+setter(+postsetter) 对 → ``property name:`` 块
- 字段 ``x: T @property = v`` → ``x__value: T = v`` + ``property def x``
- 字段 ``x: T @property.postsetter(cb…) = v`` → 存储 + property 块

用法::

  python scripts/paw_migrate_property_ref_surface.py [--dry-run] [path...]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.source import FileId
from compiler.py.frontend.tokens import Token, TokenKind

_KEEP_AT = frozenset(
  {
    "native_name",
    "serializable",
    "copyable",
    "uncopyable",
    "boxing",
    "annotation",
    "descriptor",
    "delegate",
    "immutable",
    "noexcept",
    "context",
    "decorator",
    "global_call",
    "LazyCache",
    "thread_local",
    "optional",
    "const",
    "final",
    "Meta",
    "RangeVar",
    "TagMeta",
  }
)


def _line_range(source: str, start: int, end: int) -> tuple[int, int]:
  ls = source.rfind("\n", 0, start) + 1
  le = end
  if le < len(source) and source[le] == "\n":
    le += 1
  return ls, le


def _line_indent(source: str, pos: int) -> str:
  ls = source.rfind("\n", 0, pos) + 1
  i = ls
  while i < pos and source[i] in " \t":
    i += 1
  return source[ls:i]


def _apply_edits(source: str, edits: list[tuple[int, int, str]]) -> str:
  by_start: dict[int, tuple[int, int, str]] = {}
  inserts: list[tuple[int, int, str]] = []
  for a, b, r in edits:
    if a == b:
      inserts.append((a, b, r))
    else:
      prev = by_start.get(a)
      if prev is None or (b - a) > (prev[1] - prev[0]):
        by_start[a] = (a, b, r)
  merged = list(by_start.values()) + inserts
  merged.sort(key=lambda e: (e[0], e[0] - e[1]), reverse=True)
  out = source
  last = None
  for a, b, repl in merged:
    if last is not None and b > last:
      continue
    if 0 <= a <= b <= len(out):
      out = out[:a] + repl + out[b:]
      last = a
  while "\n\n\n" in out:
    out = out.replace("\n\n\n", "\n\n")
  return out


def _migrate_async_static(source: str) -> str:
  return re.sub(r"\basync\s+static\s+def\b", "static async def", source)


def _migrate_type_markers(source: str) -> str:
  """``T @ref @lazy`` / ``T @ref`` / ``T @lazy`` → 前缀形式。"""
  tokens = Lexer(source, FileId(0)).tokenize()
  n = len(tokens)
  edits: list[tuple[int, int, str]] = []
  i = 0

  def kind(j: int) -> TokenKind | None:
    return tokens[j].kind if 0 <= j < n else None

  def text(j: int) -> str:
    return tokens[j].text if 0 <= j < n else ""

  while i < n:
    if kind(i) is not TokenKind.AT or kind(i + 1) is not TokenKind.NAME:
      i += 1
      continue
    name = text(i + 1)
    if name not in ("ref", "lazy"):
      i += 1
      continue
    # 收集连续 @ref / @lazy
    markers: list[str] = []
    j = i
    while kind(j) is TokenKind.AT and kind(j + 1) is TokenKind.NAME and text(j + 1) in (
      "ref",
      "lazy",
    ):
      markers.append(text(j + 1))
      j += 2
    # 向前找类型起点：跳过空白，类型结束于本 AT 之前
    # 类型文本 = 从最近的 : / -> / , / [ / ( 之后到 AT 之前
    k = i - 1
    while k >= 0 and kind(k) in (TokenKind.NEWLINE, TokenKind.INDENT, TokenKind.DEDENT):
      k -= 1
    if k < 0:
      i = j
      continue
    type_end = tokens[k].span.end
    # 向左找类型起始分隔
    depth_sq = 0
    depth_par = 0
    t = k
    type_start_tok = 0
    while t >= 0:
      tk = tokens[t]
      if tk.kind is TokenKind.RSQB:
        depth_sq += 1
      elif tk.kind is TokenKind.LSQB:
        if depth_sq:
          depth_sq -= 1
        elif depth_par == 0:
          type_start_tok = t + 1
          break
      elif tk.kind is TokenKind.RPAR:
        depth_par += 1
      elif tk.kind is TokenKind.LPAR:
        if depth_par:
          depth_par -= 1
        elif depth_sq == 0:
          type_start_tok = t + 1
          break
      elif depth_sq == 0 and depth_par == 0 and tk.kind in (
        TokenKind.COLON,
        TokenKind.RARROW,
        TokenKind.COMMA,
        TokenKind.EQ,
      ):
        type_start_tok = t + 1
        break
      t -= 1
    # 跳过类型前空白 token
    while type_start_tok < i and kind(type_start_tok) in (
      TokenKind.NEWLINE,
      TokenKind.INDENT,
      TokenKind.DEDENT,
    ):
      type_start_tok += 1
    if type_start_tok >= i:
      i = j
      continue
    type_text = source[tokens[type_start_tok].span.start : type_end].strip()
    has_ref = "ref" in markers
    has_lazy = "lazy" in markers
    if has_lazy and has_ref:
      prefix = "lazy ref "
    elif has_ref:
      prefix = "ref "
    else:
      prefix = "lazy "
    # 替换类型 + markers
    marker_end = tokens[j - 1].span.end if j > i else tokens[i].span.end
    edits.append(
      (
        tokens[type_start_tok].span.start,
        marker_end,
        prefix + type_text,
      )
    )
    i = j

  return _apply_edits(source, edits)


def _skip_def_block(tokens: list[Token], colon_i: int) -> int:
  n = len(tokens)
  i = colon_i + 1
  while i < n and tokens[i].kind is TokenKind.NEWLINE:
    i += 1
  if i >= n or tokens[i].kind is not TokenKind.INDENT:
    # 单行 suite
    while i < n and tokens[i].kind not in (TokenKind.NEWLINE, TokenKind.END, TokenKind.DEDENT):
      i += 1
    return i
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


def _read_deco_chain(
  tokens: list[Token], i: int
) -> tuple[list[tuple[int, int, str, str | None]], int]:
  """读连续 ``@Name[.attr]`` 装饰器，返回 [(start,end,root,attr|None),…] 与下一 token。"""
  n = len(tokens)
  decos: list[tuple[int, int, str, str | None]] = []
  while i < n and tokens[i].kind is TokenKind.AT:
    if i + 1 >= n or tokens[i + 1].kind is not TokenKind.NAME:
      break
    root = tokens[i + 1].text
    attr = None
    k = i + 2
    if k < n and tokens[k].kind is TokenKind.DOT and k + 1 < n and tokens[k + 1].kind is TokenKind.NAME:
      attr = tokens[k + 1].text
      k += 2
    # 跳过可能的调用参数
    if k < n and tokens[k].kind is TokenKind.LPAR:
      depth = 0
      while k < n:
        if tokens[k].kind is TokenKind.LPAR:
          depth += 1
        elif tokens[k].kind is TokenKind.RPAR:
          depth -= 1
          if depth == 0:
            k += 1
            break
        k += 1
    end = tokens[k - 1].span.end if k > i else tokens[i].span.end
    decos.append((tokens[i].span.start, end, root, attr))
    i = k
    while i < n and tokens[i].kind in (
      TokenKind.NEWLINE,
      TokenKind.INDENT,
      TokenKind.DEDENT,
    ):
      i += 1
  return decos, i


def _def_head_info(
  source: str, tokens: list[Token], i: int
) -> tuple[str, str, str, str, int] | None:
  """从 ``def Name(params)[->ret]:`` 起解析，返回 (name, params, ret, body, end_i)。"""
  n = len(tokens)
  if i >= n or tokens[i].kind is not TokenKind.NAME or tokens[i].text != "def":
    return None
  if i + 1 >= n or tokens[i + 1].kind is not TokenKind.NAME:
    return None
  name = tokens[i + 1].text
  j = i + 2
  if j >= n or tokens[j].kind is not TokenKind.LPAR:
    return None
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
  params = source[tokens[ps].span.start : tokens[j - 1].span.end] if j > ps else ""
  j += 1
  ret = ""
  if j < n and tokens[j].kind is TokenKind.RARROW:
    j += 1
    rs = j
    while j < n and tokens[j].kind not in (TokenKind.COLON, TokenKind.NEWLINE, TokenKind.END):
      j += 1
    if j > rs:
      ret = source[tokens[rs].span.start : tokens[j - 1].span.end]
  if j >= n or tokens[j].kind is not TokenKind.COLON:
    return None
  end_i = _skip_def_block(tokens, j)
  body_start = j + 1
  while body_start < end_i and tokens[body_start].kind in (
    TokenKind.NEWLINE,
    TokenKind.INDENT,
  ):
    body_start += 1
  body_end = end_i - 1
  while body_end >= body_start and tokens[body_end].kind in (
    TokenKind.DEDENT,
    TokenKind.NEWLINE,
  ):
    body_end -= 1
  if body_end >= body_start:
    first_pos = tokens[body_start].span.start
    line_start = source.rfind("\n", 0, first_pos) + 1
    ws_end = line_start
    while ws_end < first_pos and source[ws_end] in " \t":
      ws_end += 1
    # 块体首行：保留行首缩进；单行 suite 则从 token 起
    src_start = line_start if ws_end == first_pos else first_pos
    body = source[src_start : tokens[body_end].span.end]
  else:
    body = "pass"
  return name, params, ret, body, end_i


def _indent_body(body: str, indent: str, extra: str = "  ") -> str:
  """把方法体挂到 ``indent+extra`` 下，保留相对缩进。"""
  raw_lines = body.splitlines()
  min_ws = None
  for ln in raw_lines:
    if ln.strip():
      ws = len(ln) - len(ln.lstrip(" \t"))
      min_ws = ws if min_ws is None else min(min_ws, ws)
  min_ws = min_ws or 0
  stripped: list[str] = []
  prefix = indent + extra
  for ln in raw_lines:
    if not ln.strip():
      stripped.append("")
    else:
      stripped.append(prefix + ln[min_ws:])
  return "\n".join(stripped) + "\n"


def _migrate_property_decorators(source: str) -> str:
  """装饰器形式的 property/staticproperty → 新表面。"""
  tokens = Lexer(source, FileId(0)).tokenize()
  n = len(tokens)
  edits: list[tuple[int, int, str]] = []
  consumed: set[int] = set()
  i = 0

  while i < n:
    if i in consumed or tokens[i].kind is not TokenKind.AT:
      i += 1
      continue
    decos, after = _read_deco_chain(tokens, i)
    if not decos:
      i += 1
      continue
    prop_decos = [
      d for d in decos if d[2] in ("property", "staticproperty")
    ]
    if not prop_decos:
      i = after
      continue
    other_decos = [d for d in decos if d[2] not in ("property", "staticproperty")]
    info = _def_head_info(source, tokens, after)
    if info is None:
      i = after
      continue
    name, params, ret, body, end_i = info
    indent = _line_indent(source, tokens[i].span.start)
    static = any(d[2] == "staticproperty" for d in prop_decos)
    kinds = {(d[2], d[3]) for d in prop_decos}
    # 收集同名相邻 setter/postsetter（向后扫描）
    accessors: dict[str, tuple[str, str, str]] = {}
    span_end = end_i
    primary = prop_decos[0]
    if primary[3] is None:
      accessors["get"] = (params, ret, body)
    elif primary[3] == "setter":
      accessors["set"] = (params, ret, body)
    elif primary[3] == "postsetter":
      accessors["post"] = (params, ret, body)

    # 向后找同名 setter/postsetter/getter
    look = end_i
    while look < n:
      while look < n and tokens[look].kind in (
        TokenKind.NEWLINE,
        TokenKind.INDENT,
        TokenKind.DEDENT,
      ):
        look += 1
      if look >= n or tokens[look].kind is not TokenKind.AT:
        break
      d2, after2 = _read_deco_chain(tokens, look)
      p2 = [d for d in d2 if d[2] in ("property", "staticproperty")]
      if not p2:
        break
      info2 = _def_head_info(source, tokens, after2)
      if info2 is None or info2[0] != name:
        break
      if any(d[2] == "staticproperty" for d in p2) != static:
        break
      n2, p2params, p2ret, p2body, e2 = info2
      attr = p2[0][3]
      if attr is None:
        accessors["get"] = (p2params, p2ret, p2body)
      elif attr == "setter":
        accessors["set"] = (p2params, p2ret, p2body)
      elif attr == "postsetter":
        accessors["post"] = (p2params, p2ret, p2body)
      else:
        break
      span_end = e2
      look = e2

    # 其它装饰器文本（如 @immutable）
    extra_lines = []
    for a, b, root, attr in other_decos:
      chunk = source[a:b].strip()
      if chunk:
        extra_lines.append(chunk)

    repl_parts: list[str] = []
    for el in extra_lines:
      repl_parts.append(f"{indent}{el}")

    has_get = "get" in accessors
    has_set = "set" in accessors
    has_post = "post" in accessors

    if has_set or has_post:
      # 完整块
      head = f"{indent}{'static ' if static else ''}property {name}:"
      repl_parts.append(head)
      if has_get:
        gp, gr, gb = accessors["get"]
        ret_s = f" -> {gr}" if gr else ""
        repl_parts.append(f"{indent}  def __get__({gp}){ret_s}:")
        repl_parts.append(_indent_body(gb, indent, "    ").rstrip("\n"))
      elif has_post:
        # postsetter 旧语义隐含 getter；块内补平凡 get 需类型——用 set/post 的 value 注解
        sp = accessors.get("set") or accessors.get("post")
        assert sp is not None
        # params like "self, value: T" → 提取 T
        m = re.search(r"value\s*:\s*([^,)=]+)", sp[0])
        typ = m.group(1).strip() if m else "object"
        recv = "self" if not static else ""
        if static:
          repl_parts.append(f"{indent}  def __get__() -> {typ}:")
          repl_parts.append(f"{indent}    return Self.{name}__value")
        else:
          repl_parts.append(f"{indent}  def __get__(self) -> {typ}:")
          repl_parts.append(f"{indent}    return self.{name}__value")
      if has_set:
        sp, sr, sb = accessors["set"]
        ret_s = f" -> {sr}" if sr else ""
        repl_parts.append(f"{indent}  def __set__({sp}){ret_s}:")
        repl_parts.append(_indent_body(sb, indent, "    ").rstrip("\n"))
      elif has_post:
        # 旧 postsetter 隐含赋值到 storage
        sp = accessors["post"][0]
        m = re.search(r"value\s*:\s*([^,)=]+)", sp)
        typ = m.group(1).strip() if m else "object"
        if static:
          repl_parts.append(f"{indent}  def __set__(value: {typ}) -> None:")
          repl_parts.append(f"{indent}    Self.{name}__value = value")
        else:
          repl_parts.append(f"{indent}  def __set__(self, value: {typ}) -> None:")
          repl_parts.append(f"{indent}    self.{name}__value = value")
      if has_post:
        pp, pr, pb = accessors["post"]
        ret_s = f" -> {pr}" if pr else ""
        repl_parts.append(f"{indent}  def __post_set__({pp}){ret_s}:")
        repl_parts.append(_indent_body(pb, indent, "    ").rstrip("\n"))
      repl = "\n".join(repl_parts) + "\n"
    else:
      # 仅 getter → property def / static property def
      head = f"{'static ' if static else ''}property def"
      gp, gr, gb = accessors["get"]
      ret_s = f" -> {gr}" if gr else ""
      # 保留 extra 装饰器在 property def 上方
      lines = [f"{indent}{el}" for el in extra_lines]
      lines.append(f"{indent}{head} {name}({gp}){ret_s}:")
      # body：保持相对缩进
      body_lines = gb.splitlines() or ["pass"]
      min_ws = None
      for ln in body_lines:
        if ln.strip():
          ws = len(ln) - len(ln.lstrip(" \t"))
          min_ws = ws if min_ws is None else min(min_ws, ws)
      min_ws = min_ws or 0
      for ln in body_lines:
        if not ln.strip():
          lines.append("")
        else:
          lines.append(indent + "  " + ln[min_ws:])
      repl = "\n".join(lines) + "\n"

    start = tokens[i].span.start
    # 含前导缩进
    start = _line_range(source, start, start)[0]
    # 结束于最后一个非缩进/换行 token，避免吞掉下一条声明的 ``@``
    j_end = span_end - 1
    while j_end >= i and tokens[j_end].kind in (
      TokenKind.DEDENT,
      TokenKind.INDENT,
      TokenKind.NEWLINE,
    ):
      j_end -= 1
    end_pos = tokens[j_end].span.end if j_end >= i else tokens[end_i - 1].span.end
    if end_pos < len(source) and source[end_pos] == "\n":
      end_pos += 1
    edits.append((start, end_pos, repl))
    for x in range(i, span_end):
      consumed.add(x)
    i = span_end

  return _apply_edits(source, edits)


_FIELD_PROP = re.compile(
  r"^([ \t]*)([A-Za-z_][\w]*)\s*:\s*(.+?)\s*@property\s*(?:=\s*(.*))?$"
)
_FIELD_POST = re.compile(
  r"^([ \t]*)([A-Za-z_][\w]*)\s*:\s*(.+?)\s*@(?:property|staticproperty)\.postsetter\((.+)\)\s*=\s*(.*)$"
)


def _migrate_field_shorthand(source: str) -> str:
  lines = source.splitlines(keepends=True)
  out: list[str] = []
  i = 0
  while i < len(lines):
    raw = lines[i]
    line = raw.rstrip("\n\r")
    mpost = _FIELD_POST.match(line)
    mprop = _FIELD_PROP.match(line) if mpost is None else None
    if mpost:
      ind, name, typ, cbs, default = mpost.groups()
      storage = f"{name}__value"
      out.append(f"{ind}{storage}: {typ.strip()} = {default}\n")
      out.append(f"{ind}property {name}:\n")
      out.append(f"{ind}  def __get__(self) -> {typ.strip()}:\n")
      out.append(f"{ind}    return self.{storage}\n")
      out.append(f"{ind}  def __set__(self, value: {typ.strip()}) -> None:\n")
      out.append(f"{ind}    self.{storage} = value\n")
      out.append(f"{ind}  def __post_set__(self, value: {typ.strip()}) -> None:\n")
      for cb in [c.strip() for c in cbs.split(",")]:
        if not cb:
          continue
        if cb.startswith("Self.") or cb.startswith("self."):
          out.append(f"{ind}    {cb}(value)\n")
        elif cb.startswith("_"):
          # 常见无参同步方法（``_applyTitle`` / ``_syncToNative``）
          out.append(f"{ind}    self.{cb}()\n")
        else:
          out.append(f"{ind}    self.{cb}(value)\n")
      i += 1
      continue
    if mprop:
      ind, name, typ, default = mprop.groups()
      typ = typ.strip()
      storage = f"{name}__value"
      if default is not None and default.strip() != "":
        out.append(f"{ind}{storage}: {typ} = {default.strip()}\n")
      else:
        out.append(f"{ind}{storage}: {typ}\n")
      out.append(f"{ind}property def {name}(self) -> {typ}:\n")
      out.append(f"{ind}  return self.{storage}\n")
      i += 1
      continue
    out.append(raw)
    i += 1
  return "".join(out)


def migrate(source: str) -> str:
  s = _migrate_async_static(source)
  s = _migrate_type_markers(s)
  s = _migrate_property_decorators(s)
  s = _migrate_field_shorthand(s)
  return s


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("paths", nargs="*", default=["py2cpp", "test", "compiler"])
  ap.add_argument("--dry-run", action="store_true")
  ns = ap.parse_args()
  files: list[Path] = []
  for p in ns.paths:
    path = Path(p)
    if not path.is_absolute():
      path = ROOT / path
    if path.is_file():
      files.append(path)
    else:
      files.extend(sorted(path.rglob("*.paw")))
  changed = 0
  for f in files:
    src = f.read_text(encoding="utf-8")
    new = migrate(src)
    if new != src:
      changed += 1
      if ns.dry_run:
        print(f"DRY {f.relative_to(ROOT)}")
      else:
        f.write_text(new, encoding="utf-8", newline="\n")
        print(f"OK  {f.relative_to(ROOT)}")
  print(f"done: {changed} changed / {len(files)} files")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
