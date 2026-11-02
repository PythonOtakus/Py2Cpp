"""Paw / Python-子集 Lexer：INDENT/DEDENT、续行、字符串与运算符。"""
from __future__ import annotations

from .diagnostic import Diagnostic, FrontendError
from .source import FileId, Span
from .tokens import Token, TokenKind

_SINGLE_OPS = {
  "(": TokenKind.LPAR,
  ")": TokenKind.RPAR,
  "[": TokenKind.LSQB,
  "]": TokenKind.RSQB,
  "{": TokenKind.LBRACE,
  "}": TokenKind.RBRACE,
  ",": TokenKind.COMMA,
  ":": TokenKind.COLON,
  "@": TokenKind.AT,
  "?": TokenKind.QUESTION,
  "!": TokenKind.BANG,
}

_MULTI_OPS = (
  ("=>", TokenKind.ARROW),
  ("->", TokenKind.RARROW),
  ("...", TokenKind.ELLIPSIS),
  ("<<=", TokenKind.OP),
  (">>=", TokenKind.OP),
  ("**=", TokenKind.OP),
  ("//=", TokenKind.OP),
  ("==", TokenKind.OP),
  ("!=", TokenKind.OP),
  ("<=", TokenKind.OP),
  (">=", TokenKind.OP),
  ("<<", TokenKind.OP),
  (">>", TokenKind.OP),
  ("**", TokenKind.OP),
  ("//", TokenKind.OP),
  ("+=", TokenKind.OP),
  ("-=", TokenKind.OP),
  ("*=", TokenKind.OP),
  ("/=", TokenKind.OP),
  ("%=", TokenKind.OP),
  ("@=", TokenKind.OP),
  ("&=", TokenKind.OP),
  ("|=", TokenKind.OP),
  ("^=", TokenKind.OP),
  (":=", TokenKind.OP),
  ("??", TokenKind.OP),
  ("?.", TokenKind.OP),
  ("?[", TokenKind.OP),
)


class Lexer:
  def __init__(self, text: str, file_id: FileId) -> None:
    self._text = text.replace("\r\n", "\n").replace("\r", "\n")
    if self._text.startswith("\ufeff"):
      self._text = self._text[1:]
    self._file_id = file_id
    self._i = 0
    self._line_start = True
    self._indent_stack: list[int] = [0]
    self._paren_depth = 0
    self._pending: list[Token] = []

  def tokenize(self) -> list[Token]:
    out: list[Token] = []
    while True:
      tok = self._next()
      out.append(tok)
      if tok.kind is TokenKind.END:
        break
    return out

  def _span(self, start: int, end: int) -> Span:
    return Span(self._file_id, start, end)

  def _peek(self, n: int = 0) -> str:
    j = self._i + n
    if j >= len(self._text):
      return ""
    return self._text[j]

  def _error(self, msg: str, start: int) -> None:
    raise FrontendError(
      Diagnostic("P0001", msg, self._span(start, max(start + 1, self._i)))
    )

  def _next(self) -> Token:
    if self._pending:
      return self._pending.pop(0)
    # 行首先量缩进，禁止先吃掉前导空白
    if self._line_start and self._paren_depth == 0:
      ind = self._measure_indent()
      if ind is not None:
        return ind
    else:
      self._skip_spaces_and_comments_inline()

    if self._i >= len(self._text):
      while len(self._indent_stack) > 1:
        self._indent_stack.pop()
        self._pending.append(
          Token(TokenKind.DEDENT, self._span(self._i, self._i), "")
        )
      if self._pending:
        return self._pending.pop(0)
      return Token(TokenKind.END, self._span(self._i, self._i), "")

    ch = self._peek()
    if ch == "\n":
      start = self._i
      self._i += 1
      self._line_start = True
      if self._paren_depth > 0:
        return self._next()
      return Token(TokenKind.NEWLINE, self._span(start, self._i), "\n")

    # 行首缩进与当前相同：跳过空白后继续
    if self._line_start:
      self._skip_spaces_and_comments_inline()
      ch = self._peek()
      if ch == "\n" or ch == "":
        return self._next()
      if ch == "#":
        self._skip_spaces_and_comments_inline()
        return self._next()

    self._line_start = False
    if ch in "\"'":
      return self._string()
    if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
      return self._number()
    if ch == "." and self._peek(1) == "." and self._peek(2) == ".":
      start = self._i
      self._i += 3
      return Token(TokenKind.ELLIPSIS, self._span(start, self._i), "...")
    if ch.isalpha() or ch == "_":
      # ``f"…"`` / ``rf'…'`` 等：前缀字母后紧跟引号 → 字符串，勿拆成 NAME
      j = self._i
      while j < len(self._text) and self._text[j].isalpha():
        j += 1
      if j < len(self._text) and self._text[j] in "\"'":
        return self._string()
      return self._name()
    for op, kind in _MULTI_OPS:
      if self._text.startswith(op, self._i):
        start = self._i
        self._i += len(op)
        if op == "(":
          self._paren_depth += 1
        return Token(kind if kind is not TokenKind.OP else TokenKind.OP, self._span(start, self._i), op)
    if ch == "=":
      start = self._i
      self._i += 1
      return Token(TokenKind.EQ, self._span(start, self._i), "=")
    if ch == ".":
      start = self._i
      self._i += 1
      return Token(TokenKind.DOT, self._span(start, self._i), ".")
    if ch in _SINGLE_OPS:
      start = self._i
      self._i += 1
      kind = _SINGLE_OPS[ch]
      if kind is TokenKind.LPAR or kind is TokenKind.LSQB or kind is TokenKind.LBRACE:
        self._paren_depth += 1
      elif kind is TokenKind.RPAR or kind is TokenKind.RSQB or kind is TokenKind.RBRACE:
        self._paren_depth = max(0, self._paren_depth - 1)
      return Token(kind, self._span(start, self._i), ch)
    # 其它单字符算子
    start = self._i
    self._i += 1
    return Token(TokenKind.OP, self._span(start, self._i), ch)

  def _skip_spaces_and_comments_inline(self) -> None:
    while self._i < len(self._text):
      ch = self._peek()
      if ch in " \t":
        self._i += 1
        continue
      if ch == "#":
        while self._i < len(self._text) and self._peek() != "\n":
          self._i += 1
        continue
      if ch == "\\" and self._peek(1) == "\n":
        self._i += 2
        continue
      break

  def _measure_indent(self) -> Token | None:
    start = self._i
    col = 0
    while True:
      ch = self._peek()
      if ch == " ":
        col += 1
        self._i += 1
      elif ch == "\t":
        col = (col // 8 + 1) * 8
        self._i += 1
      else:
        break
    if self._peek() in ("", "\n", "#"):
      # 空白行：不改缩进栈
      return None
    self._line_start = False
    cur = self._indent_stack[-1]
    if col == cur:
      return None
    if col > cur:
      self._indent_stack.append(col)
      return Token(TokenKind.INDENT, self._span(start, self._i), "")
    while self._indent_stack[-1] > col:
      self._indent_stack.pop()
      self._pending.append(Token(TokenKind.DEDENT, self._span(start, self._i), ""))
    if self._indent_stack[-1] != col:
      self._error("inconsistent dedent", start)
    if self._pending:
      return self._pending.pop(0)
    return None

  def _name(self) -> Token:
    from .tokens import _HARD_KEYWORDS

    start = self._i
    self._i += 1
    while True:
      ch = self._peek()
      if ch.isalnum() or ch == "_":
        self._i += 1
      else:
        break
    text = self._text[start : self._i]
    kind = _HARD_KEYWORDS.get(text, TokenKind.NAME)
    return Token(kind, self._span(start, self._i), text)

  def _number(self) -> Token:
    start = self._i
    while True:
      ch = self._peek()
      # ``"" in "._"`` 为 True，EOF 时必须显式停止（否则死循环）
      if not ch or not (ch.isalnum() or ch in "._"):
        break
      self._i += 1
    return Token(TokenKind.NUMBER, self._span(start, self._i), self._text[start : self._i])

  def _string(self) -> Token:
    start = self._i
    # 前缀
    while self._peek().isalpha():
      self._i += 1
    quote = self._peek()
    if quote not in "\"'":
      self._error("expected string quote", start)
    self._i += 1
    triple = self._peek() == quote and self._peek(1) == quote
    if triple:
      self._i += 2
      end_pat = quote * 3
      while self._i < len(self._text):
        if self._text.startswith(end_pat, self._i):
          self._i += 3
          break
        if self._peek() == "\\":
          self._i += 2
          continue
        self._i += 1
      else:
        self._error("unterminated triple string", start)
    else:
      while self._i < len(self._text):
        ch = self._peek()
        if ch == "\\":
          self._i += 2
          continue
        if ch == quote:
          self._i += 1
          break
        if ch == "\n":
          self._error("unterminated string", start)
        self._i += 1
      else:
        self._error("unterminated string", start)
    return Token(TokenKind.STRING, self._span(start, self._i), self._text[start : self._i])
