"""将 ``*.paw`` 中旧方法装饰器迁到 Paw 表面写法。

- ``@staticmethod`` → ``static def``
- ``@native``（装饰器）→ ``native class`` / ``native def``
- 删除 ``@overload`` 行（同名重载由编译器自动识别）
- 不改 ``@native_name``；若仍有 ``@classmethod`` 则报错退出

用法::

  python scripts/paw_migrate_method_surface.py [--dry-run] [path...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.source import FileId
from compiler.py.frontend.tokens import Token, TokenKind


_DECL_HEADS = frozenset(
  {"def", "class", "record", "enum", "union", "protocol", "mixin", "variant"}
)
_SOFT_PREFIX = frozenset(
  {"static", "native", "final", "ref", "lazy", "frozen", "ordered", "async"}
)


def _line_range(source: str, start: int, end: int) -> tuple[int, int]:
  """扩展到整物理行（含结尾换行）。"""
  ls = source.rfind("\n", 0, start) + 1
  le = end
  if le < len(source) and source[le] == "\n":
    le += 1
  return ls, le


def migrate(source: str) -> tuple[str, list[str]]:
  warnings: list[str] = []
  tokens = Lexer(source, FileId(0)).tokenize()
  n = len(tokens)
  edits: list[tuple[int, int, str]] = []
  i = 0

  def kind(j: int) -> TokenKind | None:
    return tokens[j].kind if 0 <= j < n else None

  def text(j: int) -> str:
    return tokens[j].text if 0 <= j < n else ""

  while i < n and kind(i) is not TokenKind.END:
    if kind(i) is not TokenKind.AT:
      i += 1
      continue

    deco_start = i
    decos: list[tuple[int, int, str]] = []
    j = i
    while kind(j) is TokenKind.AT:
      if kind(j + 1) is not TokenKind.NAME:
        break
      name = text(j + 1)
      k = j + 2
      depth = 0
      while k < n and not (
        depth == 0 and kind(k) in (TokenKind.NEWLINE, TokenKind.END)
      ):
        if kind(k) is TokenKind.LPAR:
          depth += 1
        elif kind(k) is TokenKind.RPAR:
          depth = max(0, depth - 1)
        k += 1
      end_tok = tokens[k - 1] if k > j else tokens[j]
      decos.append((tokens[j].span.start, end_tok.span.end, name))
      j = k
      while kind(j) in (TokenKind.NEWLINE, TokenKind.INDENT, TokenKind.DEDENT):
        j += 1

    tgt = j
    while kind(tgt) is TokenKind.NAME and text(tgt) in _SOFT_PREFIX:
      tgt += 1
    if kind(tgt) is not TokenKind.NAME or text(tgt) not in _DECL_HEADS:
      i = deco_start + 1
      continue

    head = text(tgt)
    existing_prefix = [
      text(t)
      for t in range(j, tgt)
      if kind(t) is TokenKind.NAME
    ]
    insert_mods: list[str] = []
    for start, end, name in decos:
      if name == "overload":
        edits.append((*_line_range(source, start, end), ""))
      elif name == "staticmethod":
        if head != "def":
          warnings.append(f"@staticmethod before {head}")
        else:
          edits.append((*_line_range(source, start, end), ""))
          if "static" not in existing_prefix and "static" not in insert_mods:
            insert_mods.append("static")
      elif name == "native":
        edits.append((*_line_range(source, start, end), ""))
        if "native" not in existing_prefix and "native" not in insert_mods:
          insert_mods.append("native")
      elif name in ("override", "abstract", "virtual", "final"):
        # ``@override`` / ``@abstract`` / ``@virtual`` / ``@final`` → 关键字前缀
        if head == "def" or (head == "class" and name == "final"):
          edits.append((*_line_range(source, start, end), ""))
          if name not in existing_prefix and name not in insert_mods:
            insert_mods.append(name)
        else:
          warnings.append(f"@{name} before {head}")
      elif name == "classmethod":
        warnings.append("@classmethod unsupported")

    if insert_mods:
      edits.append(
        (
          tokens[tgt].span.start,
          tokens[tgt].span.start,
          " ".join(insert_mods) + " ",
        )
      )

    i = max(j, deco_start + 1)

  # 去重重叠删除（同 start 保最长）
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
  for a, b, repl in merged:
    if 0 <= a <= b <= len(out):
      out = out[:a] + repl + out[b:]
  while "\n\n\n" in out:
    out = out.replace("\n\n\n", "\n\n")
  return out, warnings


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("paths", nargs="*", default=["py2cpp"])
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
  fail = 0
  changed = 0
  # CPython/IDE 辅助，不进 STDLIB；允许保留 @classmethod
  _classmethod_ok = frozenset(
    {str((ROOT / "py2cpp" / "reflect" / "mixin.paw").resolve())}
  )
  for f in files:
    src = f.read_text(encoding="utf-8")
    resolved = str(f.resolve())
    if "@classmethod" in src and resolved not in _classmethod_ok:
      print(f"FAIL {f}: @classmethod present（Paw 不支持）")
      fail += 1
      continue
    new, warns = migrate(src)
    for w in warns:
      print(f"WARN {f}: {w}")
      if "classmethod" in w and resolved not in _classmethod_ok:
        fail += 1
    if new != src:
      changed += 1
      if ns.dry_run:
        print(f"DRY {f}")
      else:
        f.write_text(new, encoding="utf-8", newline="\n")
        print(f"OK  {f}")
    elif "@classmethod" in src and resolved in _classmethod_ok:
      print(f"SKIP {f}: keep @classmethod (CPython/IDE stub)")
  print(f"done: {changed} changed, {fail} failed / {len(files)} files")
  return 1 if fail else 0


if __name__ == "__main__":
  raise SystemExit(main())
