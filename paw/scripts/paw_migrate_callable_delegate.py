#!/usr/bin/env python3
"""迁写 Callable/Function/delegate/native 表面。

- ``Function[[Args], R]`` → 裸箭头 ``(Args) -> R`` / ``T -> R``
- ``Callable[[Args], R]`` → ``Callable[(Args) -> R]``
- ``@delegate`` + ``def Name…: …`` → ``delegate Name…``（无体）
- ``native def …:`` + 仅 ``...``/``pass`` 体 → 无冒号无体

用法::

  python scripts/paw_migrate_callable_delegate.py
  python scripts/paw_migrate_callable_delegate.py --check
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
  ROOT / "paw",
  ROOT / "tests",
  ROOT / "ffi",
  ROOT / "zeus",
)


def _split_top_commas(inner: str) -> list[str]:
  parts: list[str] = []
  depth = 0
  start = 0
  for i, ch in enumerate(inner):
    if ch in "([{":
      depth += 1
    elif ch in ")]}":
      depth = max(0, depth - 1)
    elif ch == "," and depth == 0:
      parts.append(inner[start:i].strip())
      start = i + 1
  tail = inner[start:].strip()
  if tail:
    parts.append(tail)
  return parts


def _format_arrow(args_inner: str, ret: str) -> str:
  args = _split_top_commas(args_inner) if args_inner.strip() else []
  ret = ret.strip()
  if not args:
    return f"() -> {ret}"
  if len(args) == 1:
    p = args[0]
    if p.startswith("(") or "->" in p or "[" in p:
      return f"({p}) -> {ret}"
    return f"{p} -> {ret}"
  return f"({', '.join(args)}) -> {ret}"


def _find_balanced(src: str, open_idx: int, open_ch: str, close_ch: str) -> int | None:
  depth = 0
  i = open_idx
  while i < len(src):
    ch = src[i]
    if ch == open_ch:
      depth += 1
    elif ch == close_ch:
      depth -= 1
      if depth == 0:
        return i
    i += 1
  return None


def _rewrite_fn_callable_types(text: str) -> str:
  """反复替换 ``Function[[…], …]`` / ``Callable[[…], …]``。"""
  out = text
  changed = True
  while changed:
    changed = False
    i = 0
    buf: list[str] = []
    while i < len(out):
      m = re.search(r"\b(Function|Callable)\[\[", out[i:])
      if not m:
        buf.append(out[i:])
        break
      abs_start = i + m.start()
      head = m.group(1)
      first_br = i + m.end() - 2  # ``[[`` 的第一个 [
      inner_open = first_br + 1
      inner_close = _find_balanced(out, inner_open, "[", "]")
      if inner_close is None:
        buf.append(out[i : abs_start + 1])
        i = abs_start + 1
        continue
      j = inner_close + 1
      while j < len(out) and out[j] in " \t\n\r":
        j += 1
      if j >= len(out) or out[j] != ",":
        buf.append(out[i : abs_start + 1])
        i = abs_start + 1
        continue
      j += 1
      while j < len(out) and out[j] in " \t\n\r":
        j += 1
      ret_start = j
      # 外层 [ 仍开着，depth=1
      k = ret_start
      depth = 1
      while k < len(out):
        if out[k] == "[":
          depth += 1
        elif out[k] == "]":
          depth -= 1
          if depth == 0:
            break
        k += 1
      if k >= len(out) or depth != 0:
        buf.append(out[i : abs_start + 1])
        i = abs_start + 1
        continue
      args_inner = out[inner_open + 1 : inner_close]
      ret = out[ret_start:k]
      arrow = _format_arrow(args_inner, ret)
      repl = f"Callable[{arrow}]" if head == "Callable" else arrow
      buf.append(out[i:abs_start])
      buf.append(repl)
      i = k + 1
      changed = True
    out = "".join(buf)
  return out


def _rewrite_delegate(text: str) -> str:
  """``@delegate\\ndef Name[T](...) -> R: ...`` → ``delegate Name[T](...) -> R``。"""
  out: list[str] = []
  i = 0
  lines = text.splitlines(keepends=True)
  while i < len(lines):
    line = lines[i]
    m = re.match(r"^([ \t]*)@delegate[ \t]*\r?\n?$", line)
    if not m or i + 1 >= len(lines):
      out.append(line)
      i += 1
      continue
    indent = m.group(1)
    nxt = lines[i + 1]
    dm = re.match(
      rf"^{re.escape(indent)}def[ \t]+(.+)$",
      nxt.rstrip("\r\n"),
    )
    if not dm:
      out.append(line)
      i += 1
      continue
    rest = dm.group(1).rstrip()
    # 先剥同行体，再剥冒号（``-> None: ...``）
    inline_body = False
    if rest.endswith("..."):
      rest = rest[: -3].rstrip()
      inline_body = True
    elif rest.endswith("pass"):
      rest = rest[: -4].rstrip()
      inline_body = True
    if rest.endswith(":"):
      rest = rest[:-1].rstrip()
    out.append(f"{indent}delegate {rest}\n")
    i += 2
    if inline_body:
      continue
    # 吞掉下一行仅 ... / pass
    if i < len(lines):
      stub = lines[i].strip()
      if stub in ("...", "pass") or stub.startswith("...") or stub.startswith("pass"):
        i += 1
  return "".join(out)


def _rewrite_native_bodyless(text: str) -> str:
  """``native def … -> T:\\n  ...`` → ``native def … -> T``。"""
  lines = text.splitlines(keepends=True)
  out: list[str] = []
  i = 0
  head_re = re.compile(
    r"^([ \t]*)((?:(?:static|final|override|abstract|virtual|lazy)[ \t]+)*"
    r"native[ \t]+def[ \t].+?)[ \t]*:[ \t]*(?:\#.*)?$"
  )
  while i < len(lines):
    raw = lines[i]
    core = raw.rstrip("\r\n")
    hm = head_re.match(core)
    if not hm or i + 1 >= len(lines):
      out.append(raw)
      i += 1
      continue
    indent, head = hm.group(1), hm.group(2).rstrip()
    # 下一非空行须仅为 ... / pass（可带注释）
    j = i + 1
    while j < len(lines) and not lines[j].strip():
      j += 1
    if j >= len(lines):
      out.append(raw)
      i += 1
      continue
    stub = lines[j].strip()
    if stub.split("#", 1)[0].strip() not in ("...", "pass"):
      out.append(raw)
      i += 1
      continue
    # 保留行尾注释（从原 def 行）
    trail = ""
    if "#" in core:
      trail = "  #" + core.split("#", 1)[1]
    out.append(f"{indent}{head}{trail}\n")
    i = j + 1
  return "".join(out)


def migrate_text(text: str) -> str:
  text = _rewrite_fn_callable_types(text)
  text = _rewrite_delegate(text)
  text = _rewrite_native_bodyless(text)
  return text


def iter_paw_files() -> list[Path]:
  files: list[Path] = []
  for root in TARGETS:
    if not root.is_dir():
      continue
    files.extend(sorted(root.rglob("*.paw")))
  return files


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--check", action="store_true", help="只检查，不写回")
  args = ap.parse_args()
  n_files = 0
  n_changed = 0
  for path in iter_paw_files():
    n_files += 1
    old = path.read_text(encoding="utf-8")
    new = migrate_text(old)
    if new != old:
      n_changed += 1
      if args.check:
        print(f"need: {path.relative_to(ROOT)}")
      else:
        path.write_text(new, encoding="utf-8", newline="\n")
        print(f"ok: {path.relative_to(ROOT)}")
  print(f"scanned={n_files} changed={n_changed}")
  return 1 if args.check and n_changed else 0


if __name__ == "__main__":
  sys.exit(main())
