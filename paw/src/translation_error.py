"""翻译期错误：附带源文件路径与行号。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
  import ast

  from .translator import Translator

# 已有 ``path:line`` / ``path:line:col`` 前缀时不再重复包装
_LOCATION_PREFIX_RE = re.compile(
  r"^(?:[A-Za-z]:)?[\\/][\w./\\-]+:\d+"
  r"|^[\w./\\-]+\.py:\d+"
  r"|^py2cpp/[\w./\\-]+\.py:\d+",
)


@dataclass(frozen=True)
class SourceLocation:
  """显示用相对路径 + 磁盘绝对路径（用于读源码行）。"""

  display: str
  absolute: Path
  lineno: int
  col_offset: int | None = None
  end_lineno: int | None = None

  def prefix(self) -> str:
    if self.lineno > 0:
      base = f"{self.display}:{self.lineno}"
      if self.col_offset is not None:
        base += f":{self.col_offset + 1}"
      if self.end_lineno is not None and self.end_lineno != self.lineno:
        base += f"-{self.end_lineno}"
      return base
    return self.display

  def source_line(self) -> str | None:
    if self.lineno <= 0:
      return None
    try:
      lines = self.absolute.read_text(encoding="utf-8").splitlines()
    except OSError:
      return None
    if 1 <= self.lineno <= len(lines):
      return lines[self.lineno - 1]
    return None


class TranslationError(Exception):
  """``{文件}:{行}[:列]: {说明}``。"""

  def __init__(
    self,
    message: str,
    *,
    location: SourceLocation | None = None,
  ) -> None:
    self.message = message
    self.location = location
    super().__init__(self.format_message())

  def format_message(self) -> str:
    if self.location is not None:
      return f"{self.location.prefix()}: {self.message}"
    return self.message


def message_has_location_prefix(message: str) -> bool:
  return bool(_LOCATION_PREFIX_RE.match(message.strip()))


def location_from_node(
  tr: Translator,
  node: ast.AST,
  *,
  module_path: str | None = None,
) -> SourceLocation | None:
  lineno = getattr(node, "lineno", None)
  if not lineno:
    return None
  mp = module_path or tr._active_module_path()
  absolute = tr._resolve_module_py_path(mp)
  return SourceLocation(
    display=tr._display_path(absolute),
    absolute=absolute,
    lineno=lineno,
    col_offset=getattr(node, "col_offset", None),
    end_lineno=getattr(node, "end_lineno", None),
  )


def raise_translation_error(
  tr: Translator,
  node: ast.AST | None,
  message: str,
  *,
  module_path: str | None = None,
) -> NoReturn:
  loc = location_from_node(tr, node, module_path=module_path) if node is not None else None
  if loc is None and module_path is not None:
    absolute = tr._resolve_module_py_path(module_path)
    loc = SourceLocation(
      display=tr._display_path(absolute),
      absolute=absolute,
      lineno=0,
    )
  raise TranslationError(message, location=loc)


def enhance_translation_exception(
  exc: BaseException,
  tr: Translator | None,
  *,
  node: ast.AST | None = None,
  fallback_absolute: Path | None = None,
) -> BaseException:
  """为无位置信息的异常补上 ``文件:行``（已有前缀则原样返回）。"""
  if isinstance(exc, TranslationError):
    return exc
  msg = str(exc).strip() or type(exc).__name__
  if message_has_location_prefix(msg):
    return exc
  loc: SourceLocation | None = None
  if tr is not None:
    if node is None and tr._ast_node_stack:
      node = tr._ast_node_stack[-1]
    if node is not None:
      loc = location_from_node(tr, node)
    elif fallback_absolute is not None:
      loc = SourceLocation(
        display=tr._display_path(fallback_absolute),
        absolute=fallback_absolute.resolve(),
        lineno=0,
      )
  elif fallback_absolute is not None:
    try:
      disp = fallback_absolute.resolve().as_posix()
    except OSError:
      disp = str(fallback_absolute)
    loc = SourceLocation(
      display=disp,
      absolute=fallback_absolute.resolve(),
      lineno=0,
    )
  if loc is None:
    return exc
  return TranslationError(msg, location=loc)


def format_translation_failure(
  exc: BaseException,
  *,
  entry_path: Path | None = None,
) -> str:
  """``main.py`` / 测试用：多行 stderr 文案。"""
  if isinstance(exc, TranslationError):
    head = f"翻译失败: {exc.format_message()}"
    loc = exc.location
  else:
    msg = str(exc).strip() or type(exc).__name__
    if message_has_location_prefix(msg):
      head = f"翻译失败: {msg}"
      loc = None
    else:
      head = f"翻译失败: {msg}"
      if entry_path is not None:
        head += f"\n  入口: {entry_path}"
      loc = None

  lines = [head]
  if loc is not None:
    src = loc.source_line()
    if src is not None:
      lines.append(f"    {src.rstrip()}")
      if loc.col_offset is not None:
        indent = "    " + (" " * loc.col_offset) + "^"
        lines.append(indent)
  cause = exc.__cause__
  if cause is not None and cause is not exc:
    lines.append(f"  原因: {cause}")
  return "\n".join(lines)
