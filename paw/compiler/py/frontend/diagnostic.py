"""前端诊断。"""
from __future__ import annotations

from dataclasses import dataclass

from .source import Span


@dataclass(frozen=True)
class Diagnostic:
  code: str
  message: str
  span: Span | None = None


class FrontendError(Exception):
  """不可恢复的前端错误（首错失败路径）。"""

  def __init__(self, diagnostic: Diagnostic) -> None:
    self.diagnostic = diagnostic
    super().__init__(f"{diagnostic.code}: {diagnostic.message}")
