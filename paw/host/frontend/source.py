"""宿主侧 SourceManager 包装（委托 compiler.py.frontend）。"""
from __future__ import annotations

import hashlib

from compiler.py.frontend.source import FileId, SourceFile, SourceManager, Span

__all__ = ["FileId", "SourceFile", "SourceManager", "Span", "digest_text"]


def digest_text(text: str) -> str:
  return hashlib.sha256(text.encode("utf-8")).hexdigest()
