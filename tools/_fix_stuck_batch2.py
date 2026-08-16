#!/usr/bin/env python3
"""§1.0 残留粘连名 → camelCase（用户已确认批次）。

不改：r*/l* 族、strftime/strptime、xsplit*、C 库调用、src 内 lru_cache(maxsize=)、
pathlib exist_ok 等 CPython API。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 长名优先
MAP: list[tuple[str, str]] = [
  ("_expandtabsResetsCol", "_expandTabsResetsCol"),
  ("follow_symlinks", "followSymlinks"),
  ("effective_ids", "effectiveIds"),
  ("case_sensitive", "caseSensitive"),
  ("ignore_case", "ignoreCase"),
  ("missing_ok", "missingOk"),
  ("exist_ok", "existOk"),  # 仅 py2cpp/test/examples/docs/templates；src 单独处理
  ("asctimeNow", "ascTimeNow"),
  ("gmtimeNow", "gmTimeNow"),
  ("localtimeNow", "localTimeNow"),
  ("lineterminator", "lineTerminator"),
  ("_NoMaxlen", "_NoMaxLen"),
  ("_maxlen", "_maxLen"),
  ("asctime", "ascTime"),
  ("gmtime", "gmTime"),
  ("localtime", "localTime"),
  ("mktime", "mkTime"),
  ("py_mktime", "py_mkTime"),
  ("fillchar", "fillChar"),
  ("tabsize", "tabSize"),
  ("chunksize", "chunkSize"),
  ("maxsize", "maxSize"),
  ("newsize", "newSize"),
  ("numbytes", "numBytes"),
  ("nondirs", "nonDirs"),
  ("pathname", "pathName"),
  ("multimode", "multiMode"),
  ("popitem", "popItem"),
  ("randrange", "randRange"),
  ("randint", "randInt"),
  ("fetchone", "fetchOne"),
  ("fetchall", "fetchAll"),
  ("maxlen", "maxLen"),
  ("nbits", "nBits"),
  ("bufsize", "bufSize"),
  ("closefd", "closeFd"),
  ("dir_fd", "dirFd"),
  ("ignorecase", "ignoreCase"),
]

# 模板内禁止替换的 C 库片段（整词替换后需回滚）
C_LIB_PROTECT = [
  # 已用更长前缀匹配时，下列为危险的短名上下文
]

DIRS = (
  "py2cpp",
  "test",
  "examples",
  "docs",
  "templates",
  ".cursor",
  "scripts",
  "tools",
)
EXTS = {".py", ".md", ".inl", ".h", ".cpp", ".txt"}

# src 中仅改译器对 py2cpp API 的引用
SRC_SAFE_FILES = {
  "src/emit/prange_emit.py",
  "src/emit/call_emit.py",
  "src/emit/literal_sequence_lookup_emit.py",
  "src/passes/strict_style.py",
  "src/passes/generators.py",
  "src/constant/mixin.py",
}


def transform(text: str, *, protect_c_lib: bool) -> str:
  # 保护 C 库：临时占位
  placeholders: list[tuple[str, str]] = []
  if protect_c_lib:
    patterns = [
      (r"\b::mktime\b", "§§MKTIME§§"),
      (r"\bgmtime_s\b", "§§GMTIME_S§§"),
      (r"\bgmtime_r\b", "§§GMTIME_R§§"),
      (r"\blocaltime_s\b", "§§LOCALTIME_S§§"),
      (r"\blocaltime_r\b", "§§LOCALTIME_R§§"),
      (r"\b::strftime\b", "§§STRFTIME§§"),
      (r"\b::gmtime\b", "§§GMTIME§§"),
      (r"\b::localtime\b", "§§LOCALTIME§§"),
    ]
    for pat, ph in patterns:
      text = re.sub(pat, ph, text)
      placeholders.append((ph, None))  # type: ignore

  for old, new in sorted(MAP, key=lambda kv: -len(kv[0])):
    text = re.sub(rf"\b{re.escape(old)}\b", new, text)

  if protect_c_lib:
    text = text.replace("§§MKTIME§§", "::mktime")
    text = text.replace("§§GMTIME_S§§", "gmtime_s")
    text = text.replace("§§GMTIME_R§§", "gmtime_r")
    text = text.replace("§§LOCALTIME_S§§", "localtime_s")
    text = text.replace("§§LOCALTIME_R§§", "localtime_r")
    text = text.replace("§§STRFTIME§§", "::strftime")
    text = text.replace("§§GMTIME§§", "::gmtime")
    text = text.replace("§§LOCALTIME§§", "::localtime")

  return text


def should_skip(path: Path) -> bool:
  parts = path.parts
  if "generated" in parts or "node_modules" in parts or "third_party" in parts:
    return True
  # 工具脚本自身的 MAP 表勿二次改写键
  if path.name in (
    "_fix_stuck_batch2.py",
    "_scan_stuck_idents.py",
    "_rename_naming_convention.py",
    "_fix_stuck_names.py",
    "_fix_xsplit_maxsplit.py",
  ):
    return True
  return False


def main() -> None:
  n = 0
  for d in DIRS:
    base = ROOT / d
    if not base.exists():
      continue
    for path in base.rglob("*"):
      if not path.is_file() or path.suffix.lower() not in EXTS:
        continue
      if should_skip(path):
        continue
      raw = path.read_text(encoding="utf-8")
      protect = path.suffix.lower() in {".inl", ".h", ".cpp"} or "templates" in path.parts
      # docs/scripts 里的 exist_ok 是 pathlib — 对 scripts 跳过 exist_ok
      text = raw
      if "scripts" in path.parts or path.parts[:1] == ("scripts",):
        # 仍改其它 API 文档名，但 exist_ok 在 scripts 是 CPython
        text2 = transform(text, protect_c_lib=protect)
        # 回滚 scripts 中的 existOk → exist_ok（pathlib）
        text2 = re.sub(r"\bexistOk\b", "exist_ok", text2)
        text2 = re.sub(r"\bmissingOk\b", "missing_ok", text2)
        new = text2
      else:
        new = transform(text, protect_c_lib=protect)
      if new != raw:
        path.write_text(new, encoding="utf-8", newline="\n")
        print(path.relative_to(ROOT))
        n += 1

  for rel in SRC_SAFE_FILES:
    path = ROOT / rel
    if not path.exists():
      continue
    raw = path.read_text(encoding="utf-8")
    new = transform(raw, protect_c_lib=False)
    # 保护 lru_cache(maxSize= → 还原
    new = re.sub(r"lru_cache\(maxSize=", "lru_cache(maxsize=", new)
    if new != raw:
      path.write_text(new, encoding="utf-8", newline="\n")
      print(rel)
      n += 1

  # COMPOUNDS 同步
  rename_tool = ROOT / "tools/_rename_naming_convention.py"
  if rename_tool.exists():
    rt = rename_tool.read_text(encoding="utf-8")
    extras = {old: new for old, new in MAP if not old.startswith("_") and "_" not in old or old in (
      "exist_ok", "missing_ok", "follow_symlinks", "case_sensitive", "ignore_case",
      "effective_ids", "dir_fd",
    )}
    rt2 = rt
    for old, new in extras.items():
      if f'"{old}":' in rt2:
        rt2 = re.sub(rf'"{re.escape(old)}":\s*"[^"]*"', f'"{old}": "{new}"', rt2)
      elif '"returncode":' in rt2 or '"maxsplit":' in rt2:
        anchor = '"maxsplit": "maxSplit",' if '"maxsplit":' in rt2 else '"returncode": "returnCode",'
        if anchor in rt2 and f'"{old}":' not in rt2:
          rt2 = rt2.replace(anchor, f'"{old}": "{new}",\n  {anchor}', 1)
    if rt2 != rt:
      rename_tool.write_text(rt2, encoding="utf-8", newline="\n")
      print("tools/_rename_naming_convention.py")
      n += 1

  print(f"updated {n} files")


if __name__ == "__main__":
  main()
