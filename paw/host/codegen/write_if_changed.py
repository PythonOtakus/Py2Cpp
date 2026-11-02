"""生成物写盘：正文未变则保留 mtime（忽略 ``// 生成时间:``）。"""
from __future__ import annotations

from pathlib import Path

GENERATED_AT_PREFIX = "// 生成时间:"


def strip_generated_at_lines(text: str) -> str:
  """去掉生成时间注释后再比较，避免无语义改动刷新 mtime。"""
  if GENERATED_AT_PREFIX not in text:
    return text
  return "\n".join(
    ln for ln in text.splitlines() if not ln.startswith(GENERATED_AT_PREFIX)
  )


def write_text_if_changed(path: Path, text: str, *, encoding: str = "utf-8") -> bool:
  """写入 UTF-8 文本；正文（忽略生成时间）与现文件相同则跳过。

  返回 True 表示新建或正文有变。
  """
  path.parent.mkdir(parents=True, exist_ok=True)
  new_body = strip_generated_at_lines(text)
  if path.is_file():
    try:
      old = path.read_text(encoding=encoding)
    except OSError:
      old = ""
    if strip_generated_at_lines(old) == new_body:
      return False
  path.write_text(text, encoding=encoding)
  return True
