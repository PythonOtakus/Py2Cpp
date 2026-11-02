"""Token 种类与结构。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .source import Span


class TokenKind(Enum):
  END = auto()
  NEWLINE = auto()
  INDENT = auto()
  DEDENT = auto()
  NAME = auto()
  NUMBER = auto()
  STRING = auto()
  OP = auto()
  COMMENT = auto()
  # 软关键字在 lexer 中仍为 NAME；parser 按上下文识别
  # 硬关键字：不可作标识符
  KW_ENUM = auto()
  KW_UNION = auto()
  COLON = auto()
  COMMA = auto()
  DOT = auto()
  LPAR = auto()
  RPAR = auto()
  LSQB = auto()
  RSQB = auto()
  LBRACE = auto()
  RBRACE = auto()
  EQ = auto()
  ARROW = auto()  # =>
  RARROW = auto()  # ->
  AT = auto()
  QUESTION = auto()
  BANG = auto()
  ELLIPSIS = auto()


_HARD_KEYWORDS: dict[str, TokenKind] = {
  "enum": TokenKind.KW_ENUM,
  "union": TokenKind.KW_UNION,
}


@dataclass(frozen=True)
class Token:
  kind: TokenKind
  span: Span
  text: str
