"""旧方言装饰器 → Paw 表面语法（标准库迁移用）。

保留 ``@immutable`` / ``@copyable`` / ``@property`` 等；``@native`` /
``@staticmethod`` / ``@overload`` 由 ``tools/paw_migrate_method_surface.py``
改为 ``native`` / ``static`` 关键字或删除。
"""
from __future__ import annotations

import re

from .lexer import Lexer
from .source import FileId
from .tokens import Token, TokenKind

_KEEP_DECO = frozenset(
  {
    "immutable",
    "copyable",
    "uncopyable",
    "native_name",
    "override",
    "property",
    "staticproperty",
    "virtual",
    "abstract",
    "noexcept",
    "serializable",
    "annotation",
    "descriptor",
    "context",
    "decorator",
    "delegate",
    "boxing",
    "thread_local",
    "global_call",
    "ComponentTableMeta",
  }
)


def legacy_to_paw(source: str, *, file_id: FileId | None = None) -> str:
  fid = file_id or FileId(0)
  tokens = Lexer(source, fid).tokenize()
  return _rewrite(source, tokens)


def _rewrite(source: str, tokens: list[Token]) -> str:
  edits: list[tuple[int, int, str]] = []
  i = 0
  n = len(tokens)
  at_stmt = True

  def kind(j: int) -> TokenKind | None:
    return tokens[j].kind if 0 <= j < n else None

  def text(j: int) -> str:
    return tokens[j].text if 0 <= j < n else ""

  while i < n:
    tok = tokens[i]
    if tok.kind is TokenKind.END:
      break
    if tok.kind is TokenKind.NEWLINE:
      at_stmt = True
      i += 1
      continue
    if tok.kind in (TokenKind.INDENT, TokenKind.DEDENT):
      i += 1
      continue
    if not at_stmt:
      i += 1
      continue

    if tok.kind is TokenKind.AT:
      decos: list[tuple[int, int, str, str | None]] = []
      j = i
      while kind(j) is TokenKind.AT:
        # 含行首缩进，避免嵌套 @variant 删除后把下一行缩进“顶上去”
        start = tokens[j].span.start
        while start > 0 and source[start - 1] in " \t":
          start -= 1
        j += 1
        if kind(j) is not TokenKind.NAME:
          break
        name_parts = [text(j)]
        j += 1
        while kind(j) is TokenKind.DOT and kind(j + 1) is TokenKind.NAME:
          name_parts.append(text(j + 1))
          j += 2
        full = ".".join(name_parts)
        args = None
        if kind(j) is TokenKind.LPAR:
          depth = 0
          a0 = j
          while j < n:
            if kind(j) is TokenKind.LPAR:
              depth += 1
            elif kind(j) is TokenKind.RPAR:
              depth -= 1
              if depth == 0:
                j += 1
                args = source[tokens[a0].span.start : tokens[j - 1].span.end]
                break
            j += 1
        end = tokens[j - 1].span.end if j > 0 else start
        while kind(j) is TokenKind.NEWLINE:
          end = tokens[j].span.end
          j += 1
        decos.append((start, end, full, args))

      k = j
      while kind(k) is TokenKind.AT:
        while k < n and kind(k) not in (TokenKind.NEWLINE, TokenKind.END):
          k += 1
        while kind(k) is TokenKind.NEWLINE:
          k += 1

      if kind(k) is TokenKind.NAME and text(k) == "class":
        migrate = [
          d
          for d in decos
          if d[2] not in _KEEP_DECO and not d[2].startswith("property")
        ]
        if migrate:
          prefix, new_head, extra_bases = _map_decl_decorators(migrate)
          for start, end, _, _ in migrate:
            edits.append((start, end, ""))
          class_tok = tokens[k]
          replacement = f"{prefix}{new_head}".rstrip()
          if not replacement:
            replacement = "class"
          edits.append((class_tok.span.start, class_tok.span.end, replacement))
          if extra_bases:
            name_i = k + 1
            if kind(name_i) is TokenKind.NAME:
              after = name_i + 1
              if kind(after) is TokenKind.LSQB:
                depth = 1
                after += 1
                while after < n and depth:
                  if kind(after) is TokenKind.LSQB:
                    depth += 1
                  elif kind(after) is TokenKind.RSQB:
                    depth -= 1
                  after += 1
              if kind(after) is TokenKind.LPAR:
                edits.append(
                  (tokens[after].span.end, tokens[after].span.end, extra_bases + ", ")
                )
              elif kind(after) is TokenKind.COLON:
                edits.append(
                  (
                    tokens[after].span.start,
                    tokens[after].span.start,
                    f"({extra_bases})",
                  )
                )
          at_stmt = False
          i = k + 1
          continue
      i = j if j > i else i + 1
      at_stmt = False
      continue

    if tok.kind is TokenKind.NAME:
      j = i + 1
      marker: tuple[int, int, str] | None = None
      eq_i: int | None = None
      while j < n and kind(j) not in (TokenKind.NEWLINE, TokenKind.END, TokenKind.DEDENT):
        if kind(j) is TokenKind.AT and kind(j + 1) is TokenKind.NAME:
          tag = text(j + 1)
          # ``@optional`` 仅在 record/dataclass 合法；非 record 保留后置写法由人工处理。
          # ``@const`` → ``const name``
          if tag == "const":
            left = tokens[j].span.start
            right = tokens[j + 1].span.end
            while left > 0 and source[left - 1] in " \t":
              left -= 1
            while right < len(source) and source[right] in " \t":
              right += 1
            marker = (left, right, tag)
          j += 2
          continue
        if kind(j) is TokenKind.EQ:
          eq_i = j
          break
        j += 1
      if eq_i is not None and marker is not None:
        edits.append((marker[0], marker[1], " "))
        edits.append((tok.span.start, tok.span.start, marker[2] + " "))
        at_stmt = False
        i = eq_i + 1
        continue

    at_stmt = False
    i += 1

  return _apply(source, edits)


def _map_decl_decorators(
  migrate: list[tuple[int, int, str, str | None]],
) -> tuple[str, str, str]:
  names = {d[2]: d[3] for d in migrate}
  prefixes: list[str] = []
  head = "class"
  extra = ""

  if "enum.mro" in names:
    head = "type enum"
  elif "union.mro" in names:
    head = "type union"
  elif "enum" in names:
    head = "enum"
    args = names["enum"]
    if args and "flag" in args and "True" in args:
      extra = "flag=True"
  elif "union" in names:
    head = "union"
  elif "variant" in names:
    head = "variant"
  elif "protocol" in names:
    head = "protocol"
  elif "mixin" in names:
    head = "mixin"
  elif "dataclass" in names:
    head = "record"
    args = names["dataclass"] or ""
    if "frozen=True" in args:
      prefixes.append("frozen")
    if "order=True" in args:
      prefixes.append("ordered")

  if "refcount" in names:
    prefixes.append("ref")
  if "final" in names:
    prefixes.append("final")

  order = ["frozen", "ordered", "final", "ref", "lazy"]
  prefixes = [p for p in order if p in prefixes]
  prefix = (" ".join(prefixes) + " ") if prefixes else ""
  return prefix, head, extra


def _apply(source: str, edits: list[tuple[int, int, str]]) -> str:
  edits_sorted = sorted(
    edits, key=lambda e: (e[0], 0 if e[1] > e[0] else 1), reverse=True
  )
  out = source
  last = None
  for start, end, text in edits_sorted:
    if last is not None and end > last:
      continue
    out = out[:start] + text + out[end:]
    last = start
  out = re.sub(r"\n{3,}", "\n\n", out)
  return out
