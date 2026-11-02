"""Paw 原生前端（可自举子集）。宿主经 ``src.frontend`` 调用。"""
from __future__ import annotations

SCHEMA_VERSION = "paw-frontend-0.3.0"

from .diagnostic import Diagnostic, FrontendError
from .lexer import Lexer
from .parser import parse_tokens
from .source import FileId, SourceFile, SourceManager, Span
from .syntax_nodes import SyntaxModule
from .tokens import Token, TokenKind

__all__ = [
  "SCHEMA_VERSION",
  "Diagnostic",
  "FrontendError",
  "FileId",
  "Lexer",
  "SourceFile",
  "SourceManager",
  "Span",
  "SyntaxModule",
  "Token",
  "TokenKind",
  "parse_tokens",
]
