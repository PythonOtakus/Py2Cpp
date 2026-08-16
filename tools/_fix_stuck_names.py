#!/usr/bin/env python3
"""补漏：CPython 粘连名 / snake 别名 → camelCase（§1.0）。

勿对整个 ``src/`` 无差别替换（会弄坏 ``str.startswith``、``path.removesuffix`` 等）。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 仅替换这些遗漏标识符
MAP: dict[str, str] = {
  "removeprefix": "removePrefix",
  "removesuffix": "removeSuffix",
  "striplines": "stripLines",
  "xsplitlines": "xsplitLines",
  "xsplitLines": "xsplitLines",
  "xrsplit": "xrsplit",
  "xsplit": "xsplit",
  "keepends": "keepEnds",
  "isfile": "isFile",
  "isdir": "isDir",
  "islink": "isLink",
  "isabs": "isAbs",
  "lexists": "lExists",
  "wrap_std": "wrapStd",
  "wrap_fp": "wrapFp",
  "appendleft": "appendLeft",
  "extendleft": "extendLeft",
  "popleft": "popLeft",
  "encodebytes": "encodeBytes",
  "decodebytes": "decodeBytes",
  "executemany": "executeMany",
  "swapcase": "swapCase",
  "randbytes": "randBytes",
  "iterdir": "iterDir",
  "joinpath": "joinPath",
  "path_basename": "pathBaseName",
  "path_dirname": "pathDirName",
  "path_exists": "pathExists",
  "path_isdir": "pathIsDir",
  "path_isfile": "pathIsFile",
  "path_islink": "pathIsLink",
  "path_join": "pathJoin",
  "path_split": "pathSplit",
  "altsep": "AltSep",
  "extsep": "ExtSep",
  "pathsep": "PathSep",
  "curdir": "CurDir",
  "pardir": "ParDir",
  "defpath": "DefPath",
  "devnull": "DevNull",
  # 勿批量改 gmtime/localtime/mktime/copysign：templates 内含 C 库同名调用
}

DIRS = ("py2cpp", "test", "examples", "docs", "templates", ".cursor")
EXTS = {".py", ".md", ".inl", ".h", ".cpp", ".txt"}
# 勿改 scripts/：其中 ``pathlib.Path.iterdir`` 等为 CPython API


def replace_idents(text: str) -> str:
  for old, new in sorted(MAP.items(), key=lambda kv: -len(kv[0])):
    text = re.sub(rf"\b{re.escape(old)}\b", new, text)
  return text


def main() -> None:
  n = 0
  for d in DIRS:
    base = ROOT / d
    if not base.exists():
      continue
    for path in base.rglob("*"):
      if not path.is_file() or path.suffix.lower() not in EXTS:
        continue
      if "node_modules" in path.parts or "generated" in path.parts:
        continue
      try:
        raw = path.read_text(encoding="utf-8")
      except (UnicodeDecodeError, OSError):
        continue
      new = replace_idents(raw)
      if new != raw:
        path.write_text(new, encoding="utf-8", newline="\n")
        n += 1
        print(path.relative_to(ROOT))

  # src 硬编码的 py2cpp API 名（勿改 .removesuffix / .splitlines 等 Python 调用）
  for rel, pairs in (
    (
      "src/emit/call_emit.py",
      [
        ("attr == 'striplines'", "attr == 'stripLines'"),
        ("attr == 'stripLines'", "attr == 'stripLines'"),
      ],
    ),
    (
      "src/emit/literal_sequence_lookup_emit.py",
      [
        ("striplines", "stripLines"),
      ],
    ),
    (
      "src/passes/strict_style.py",
      [
        ("'popleft'", "'popLeft'"),
        ("'appendleft'", "'appendLeft'"),
        ("deque.appendleft", "deque.appendLeft"),
        ("'popleft'", "popLeft"),
      ],
    ),
  ):
    p = ROOT / rel
    if not p.exists():
      continue
    t = p.read_text(encoding="utf-8")
    orig = t
    for a, b in pairs:
      t = t.replace(a, b)
    # strict_style allowlist tokens
    t = re.sub(r"'popleft'", "'popLeft'", t)
    t = re.sub(r"'appendleft'", "'appendLeft'", t)
    t = t.replace("deque.appendleft", "deque.appendLeft")
    t = t.replace("'popleft'", "popLeft")  # alias hint leftover
    if "push_front" in t and "appendLeft" not in t.split("push_front")[1][:80]:
      t = t.replace(
        "insert(0, item) 或 deque.appendleft",
        "insert(0, item) 或 deque.appendLeft",
      )
      t = t.replace("'pop_front': 'popleft'", "'pop_front': 'popLeft'")
    if t != orig:
      p.write_text(t, encoding="utf-8", newline="\n")
      n += 1
      print(rel)

  # COMPOUNDS 表同步
  rename_tool = ROOT / "tools/_rename_naming_convention.py"
  rt = rename_tool.read_text(encoding="utf-8")
  extra = {
    "appendleft": "appendLeft",
    "extendleft": "extendLeft",
    "popleft": "popLeft",
    "encodebytes": "encodeBytes",
    "decodebytes": "decodeBytes",
    "executemany": "executeMany",
    "swapcase": "swapCase",
    "randbytes": "randBytes",
    "iterdir": "iterDir",
    "copysign": "copySign",
    "joinpath": "joinPath",
    "xsplitlines": "xsplitLines",
    "xsplit": "xsplit",
    "xrsplit": "xrsplit",
  }
  rt2 = rt
  for old, new in extra.items():
    needle = f'"{old}":'
    if needle not in rt2:
      # insert into COMPOUNDS
      rt2 = rt2.replace(
        '"returncode": "returnCode",\n}',
        f'"{old}": "{new}",\n  "returncode": "returnCode",\n}}',
        1,
      )
    else:
      rt2 = re.sub(rf'"{re.escape(old)}":\s*"[^"]*"', f'"{old}": "{new}"', rt2)
  # fix existing xsplitlines mapping
  rt2 = rt2.replace('"xsplitlines": "xsplitLines"', '"xsplitlines": "xsplitLines"')
  rt2 = rt2.replace('"xsplitLines": "xsplitlines"', '"xsplitLines": "xsplitLines"')
  if rt2 != rt:
    rename_tool.write_text(rt2, encoding="utf-8", newline="\n")
    n += 1
    print("tools/_rename_naming_convention.py")

  print(f"updated {n} files")


if __name__ == "__main__":
  main()
