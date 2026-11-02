#!/usr/bin/env python3
"""按编码规范批量改名：snake→camel/Pascal，SCREAMING 常量/枚举→Pascal，CPython 粘连词→camel。

仅替换「盘点得到的标识符」+ 明确复合词表，避免误伤 MSVC/JSON 等文档缩写。
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMPOUNDS: dict[str, str] = {
  "splitlines": "splitLines",
  "xsplitlines": "xsplitLines",
  "xsplitLines": "xsplitLines",
  "striplines": "stripLines",
  "removeprefix": "removePrefix",
  "removesuffix": "removeSuffix",
  "keepends": "keepEnds",
  "setdefault": "setDefault",
  "startswith": "startsWith",
  "endswith": "endsWith",
  "isatty": "isAtty",
  "isfile": "isFile",
  "isdir": "isDir",
  "islink": "isLink",
  "isabs": "isAbs",
  "lexists": "lExists",
  "wrap_std": "wrapStd",
  "wrap_fp": "wrapFp",
  "isascii": "isAscii",
  "isdigit": "isDigit",
  "isalpha": "isAlpha",
  "isalnum": "isAlnum",
  "islower": "isLower",
  "isupper": "isUpper",
  "isspace": "isSpace",
  "istitle": "isTitle",
  "isidentifier": "isIdentifier",
  "isprintable": "isPrintable",
  "isdecimal": "isDecimal",
  "isnumeric": "isNumeric",
  "isdisjoint": "isDisjoint",
  "issubset": "isSubset",
  "issuperset": "isSuperset",
  "isclose": "isClose",
  "isfinite": "isFinite",
  "ismount": "isMount",
  "isjunction": "isJunction",
  "isdevdrive": "isDevDrive",
  "isreserved": "isReserved",
  "fromkeys": "fromKeys",
  "fromordinal": "fromOrdinal",
  "fromtimestamp": "fromTimestamp",
  "toordinal": "toOrdinal",
  "readlines": "readLines",
  "writelines": "writeLines",
  "readline": "readLine",
  "readinto": "readInto",
  "readexactly": "readExactly",
  "readuntil": "readUntil",
  "readlink": "readLink",
  "finditer": "findIter",
  "fullmatch": "fullMatch",
  "splitext": "splitExt",
  "splitdrive": "splitDrive",
  "splitroot": "splitRoot",
  "basename": "baseName",
  "dirname": "dirName",
  "getcwd": "getCwd",
  "getcwdb": "getCwdb",
  "getpid": "getPid",
  "abspath": "absPath",
  "realpath": "realPath",
  "relpath": "relPath",
  "normpath": "normPath",
  "normcase": "normCase",
  "expanduser": "expandUser",
  "expandvars": "expandVars",
  "expandtabs": "expandTabs",
  "commonpath": "commonPath",
  "commonprefix": "commonPrefix",
  "samefile": "sameFile",
  "sameopenfile": "sameOpenFile",
  "samestat": "sameStat",
  "getsize": "getSize",
  "getmtime": "getMtime",
  "getctime": "getCtime",
  "getatime": "getAtime",
  "getcontext": "getContext",
  "setcontext": "setContext",
  "getstate": "getState",
  "setstate": "setState",
  "getrandbits": "getRandBits",
  "listdir": "listDir",
  "makedirs": "makeDirs",
  "removedirs": "removeDirs",
  "maketrans": "makeTrans",
  "isoformat": "isoFormat",
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
  "xsplit": "xsplit",
  "xrsplit": "xrsplit",
  "follow_symlinks": "followSymlinks",
  "effective_ids": "effectiveIds",
  "case_sensitive": "caseSensitive",
  "ignore_case": "ignoreCase",
  "missing_ok": "missingOk",
  "exist_ok": "existOk",
  "asctimeNow": "ascTimeNow",
  "gmtimeNow": "gmTimeNow",
  "localtimeNow": "localTimeNow",
  "lineterminator": "lineTerminator",
  "asctime": "ascTime",
  "gmtime": "gmTime",
  "localtime": "localTime",
  "mktime": "mkTime",
  "fillchar": "fillChar",
  "tabsize": "tabSize",
  "chunksize": "chunkSize",
  "maxsize": "maxSize",
  "newsize": "newSize",
  "numbytes": "numBytes",
  "nondirs": "nonDirs",
  "pathname": "pathName",
  "multimode": "multiMode",
  "popitem": "popItem",
  "randrange": "randRange",
  "randint": "randInt",
  "fetchone": "fetchOne",
  "fetchall": "fetchAll",
  "maxlen": "maxLen",
  "nbits": "nBits",
  "bufsize": "bufSize",
  "closefd": "closeFd",
  "dir_fd": "dirFd",
  "ignorecase": "ignoreCase",
  "maxsplit": "maxSplit",
  "returncode": "returnCode",
}

SCREAMING_SPECIAL: dict[str, str] = {
  "DEVNULL": "DevNull",
  "MAXBINSIZE": "MaxBinSize",
  "MAXLINESIZE": "MaxLineSize",
  "PIPE": "Pipe",
}

SNAKE_CLASSES = {
  "c_stat", "c_str", "c_time",
  "deque_iterator", "deque_node", "deque_reverse_iterator",
  "dict_entry", "dict_items_iterator", "dict_items_view",
  "dict_key_iterator", "dict_key_reverse_iterator", "dict_keys_view",
  "dict_values_iterator", "dict_values_view",
  "enumerate_iterator",
  "frozendict_items_iterator", "frozendict_items_view",
  "frozendict_key_iterator", "frozendict_key_reverse_iterator",
  "frozendict_keys_view", "frozendict_values_iterator", "frozendict_values_view",
  "frozenlist_iterator", "frozenset_entry", "frozenset_iterator",
  "list_iterator", "list_reverse_iterator",
  "pool_slot_loc", "range_iterator", "scandir_iterator",
  "set_iterator", "set_reverse_iterator",
  "stack_array", "stack_array2d", "stack_array3d", "stack_array_iterator",
  "str_iterator", "str_reverse_iterator",
  "thread_local", "tuple_iterator", "zip_iterator",
}

KEEP = frozenset({
  "self", "cls", "True", "False", "None", "Ellipsis", "NotImplemented",
  "args", "kwargs", "match", "case", "new", "pass", "raise", "return",
  "yield", "await", "async", "lambda", "import", "from", "as", "with",
  "if", "elif", "else", "for", "while", "break", "continue", "try", "except",
  "finally", "assert", "global", "nonlocal", "del", "in", "is", "not", "and", "or",
  "int", "float", "bool", "char", "byte", "int64", "uint", "uint64", "uintptr",
  "float64", "str", "bytes", "list", "dict", "set", "tuple", "optional",
  "array", "range", "object", "slice", "span", "deque", "frozendict", "frozenset",
  "frozenlist", "type", "super", "property", "staticmethod", "classmethod",
  "enumerate", "zip", "map", "filter", "reversed", "iter", "next", "len", "print",
  "min", "max", "abs", "open", "ord", "chr", "hex", "oct", "bin", "repr",
  "T", "K", "V", "N", "R", "Y", "E", "Ts", "Self",
  # 译器/语言装饰器与表面 API：保持原拼写
  "native_name", "global_call", "native", "overload", "immutable", "mutable",
  "copyable", "uncopyable", "boxing", "refcount", "mixin", "protocol", "dataclass",
  "enum", "variant", "union", "override", "final", "abstract", "const", "constexpr",
  "serializable", "annotation", "lazy", "moved", "weakref", "OneOf", "Never",
  "DictKeyType", "IteratorElementType", "None_",
})

IDENT_RE = re.compile(r"\b_?[A-Za-z][A-Za-z0-9_]*\b")
NATIVE_STR_RE = re.compile(
  r"""(?:@native_name|@global_call)\s*\(\s*["'][^"']*["']"""
)


def snake_to_camel(name: str) -> str:
  lead = len(name) - len(name.lstrip("_"))
  core = name[lead:]
  parts = [p for p in core.split("_") if p]
  if not parts:
    return name
  out = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
  return "_" * lead + out


def snake_to_pascal(name: str) -> str:
  lead = len(name) - len(name.lstrip("_"))
  core = name[lead:]
  parts = [p for p in core.split("_") if p]
  out = "".join(p[:1].upper() + p[1:] for p in parts)
  # 粘连前缀：frozendict / frozenlist / frozenset
  for bad, good in (
    ("Frozendict", "FrozenDict"),
    ("Frozenlist", "FrozenList"),
    ("Frozenset", "FrozenSet"),
  ):
    if out.startswith(bad):
      out = good + out[len(bad) :]
      break
  return "_" * lead + out


def screaming_to_pascal(name: str) -> str:
  lead = len(name) - len(name.lstrip("_"))
  core = name[lead:]
  if core in SCREAMING_SPECIAL:
    return "_" * lead + SCREAMING_SPECIAL[core]
  if "_" not in core:
    return "_" * lead + core[:1] + core[1:].lower()
  parts = [p for p in core.split("_") if p]
  return "_" * lead + "".join(p[:1].upper() + p[1:].lower() for p in parts)


def is_snake(name: str) -> bool:
  if name.startswith("__") and name.endswith("__"):
    return False
  # ``None_`` 等尾部下划线哨兵
  if name.endswith("_") and not name.startswith("__"):
    return False
  if name in KEEP:
    return False
  core = name.lstrip("_")
  return "_" in core and core.replace("_", "").isalnum() and not core.isupper()


def is_screaming(name: str) -> bool:
  if name.startswith("__") and name.endswith("__"):
    return False
  if name.endswith("_") and not name.startswith("__"):
    return False
  if name in KEEP:
    return False
  core = name.lstrip("_")
  return bool(core) and core.isupper() and any(c.isalpha() for c in core)


def _collect_file(path: Path, snakes: set[str], screams: set[str], classes: set[str]) -> None:
  try:
    tree = ast.parse(path.read_text(encoding="utf-8"))
  except SyntaxError:
    return
  for n in ast.walk(tree):
    if isinstance(n, ast.ClassDef):
      if is_snake(n.name):
        classes.add(n.name)
        snakes.add(n.name)
      is_enum = any(
        (isinstance(d, ast.Name) and d.id == "enum")
        or (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "enum")
        for d in n.decorator_list
      )
      for b in n.body:
        if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
          if is_snake(b.name) or b.name.lstrip("_") in COMPOUNDS:
            snakes.add(b.name)
          for a in b.args.args + b.args.kwonlyargs:
            if is_snake(a.arg):
              snakes.add(a.arg)
        if isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name):
          if is_snake(b.target.id) or is_screaming(b.target.id):
            (screams if is_screaming(b.target.id) else snakes).add(b.target.id)
        if is_enum and isinstance(b, ast.Assign):
          for t in b.targets:
            if isinstance(t, ast.Name) and is_screaming(t.id):
              screams.add(t.id)
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
      if is_snake(n.name) or n.name.lstrip("_") in COMPOUNDS:
        snakes.add(n.name)
      for a in n.args.args + n.args.kwonlyargs:
        if is_snake(a.arg):
          snakes.add(a.arg)
    if isinstance(n, ast.Name) and isinstance(getattr(n, "ctx", None), ast.Store):
      if is_snake(n.id):
        snakes.add(n.id)
      if is_screaming(n.id):
        screams.add(n.id)
    if isinstance(n, ast.arg) and is_snake(n.arg):
      snakes.add(n.arg)
    if isinstance(n, ast.Attribute) and (is_snake(n.attr) or n.attr.lstrip("_") in COMPOUNDS):
      snakes.add(n.attr)
    if isinstance(n, ast.Assign):
      for t in n.targets:
        if isinstance(t, ast.Name):
          if is_screaming(t.id):
            screams.add(t.id)
          if is_snake(t.id):
            snakes.add(t.id)
    if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
      if is_screaming(n.target.id):
        screams.add(n.target.id)
      if is_snake(n.target.id):
        snakes.add(n.target.id)


def collect_idents() -> tuple[set[str], set[str], set[str]]:
  """返回 (snake_idents, screaming_idents, class_snakes)。"""
  snakes: set[str] = set(SNAKE_CLASSES)
  screams: set[str] = set(SCREAMING_SPECIAL)
  classes: set[str] = set(SNAKE_CLASSES)

  for root_name in ("py2cpp", "test", "examples"):
    base = ROOT / root_name
    if not base.exists():
      continue
    for p in base.rglob("*.py"):
      _collect_file(p, snakes, screams, classes)

  for c in COMPOUNDS:
    snakes.add(c)
    snakes.add("_" + c)
  return snakes, screams, classes


def build_map() -> dict[str, str]:
  snakes, screams, classes = collect_idents()
  m: dict[str, str] = {}
  for c in classes:
    if c.startswith("__") and c.endswith("__"):
      continue
    m[c] = snake_to_pascal(c)
  for s in snakes:
    if s in m:
      continue
    if s.startswith("__") and s.endswith("__"):
      continue
    if s.lstrip("_") in COMPOUNDS or s in COMPOUNDS:
      lead = len(s) - len(s.lstrip("_"))
      core = s.lstrip("_")
      m[s] = "_" * lead + COMPOUNDS[core]
    elif is_snake(s):
      if s in classes:
        m[s] = snake_to_pascal(s)
      else:
        m[s] = snake_to_camel(s)
  for s in screams:
    if s in KEEP:
      continue
    if s.startswith("__") and s.endswith("__"):
      continue
    m[s] = screaming_to_pascal(s)
  for k, v in SCREAMING_SPECIAL.items():
    m[k] = v
  # 绝对禁止改 dunder
  m = {k: v for k, v in m.items() if not (k.startswith("__") and k.endswith("__"))}
  return m


def protect_native_strings(text: str) -> tuple[str, list[str]]:
  held: list[str] = []

  def hold(m: re.Match[str]) -> str:
    held.append(m.group(0))
    return f"__PY2CPP_HOLD_{len(held) - 1}__"

  return NATIVE_STR_RE.sub(hold, text), held


def restore_held(text: str, held: list[str]) -> str:
  for i, s in enumerate(held):
    text = text.replace(f"__PY2CPP_HOLD_{i}__", s)
  return text


# 模板/C++ 中勿改的 POSIX / CRT 符号（与 py2cpp 方法同名时保留 C 拼写）
C_API_KEEP = frozenset({
  "isatty", "_isatty", "getcwd", "getpid", "realpath", "readlink",
  "dirname", "basename", "mkdir", "rmdir", "remove", "rename", "unlink",
  "symlink", "getenv", "setenv", "putenv", "system", "abort", "exit",
  "atoi", "atol", "atof", "strtol", "strtod", "memcpy", "memmove", "memset",
  "memcmp", "strlen", "strcmp", "strncmp", "strcpy", "strncpy", "strcat",
  "printf", "sprintf", "snprintf", "fprintf", "fopen", "fclose", "fread",
  "fwrite", "fflush", "fseek", "ftell", "rewind", "malloc", "calloc", "realloc",
  "free", "qsort", "bsearch", "time", "clock", "sleep", "usleep",
})


def transform_text(text: str, mapping: dict[str, str], *, native_file: bool = False) -> str:
  if not mapping:
    return text
  use = mapping
  if native_file:
    use = {k: v for k, v in mapping.items() if k.lstrip("_") not in C_API_KEEP and k not in C_API_KEEP}
  if not use:
    return text
  text, held = protect_native_strings(text)
  keys = sorted(use.keys(), key=len, reverse=True)
  pat = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b")

  def repl(m: re.Match[str]) -> str:
    return use.get(m.group(0), m.group(0))

  text = pat.sub(repl, text)
  return restore_held(text, held)


ROOT_DIRS = ("py2cpp", "test", "examples", "docs", "templates")
SKIP_PARTS = {"generated", ".git", ".cache", "node_modules", "__pycache__"}
EXT_OK = {".py", ".md", ".inl", ".h", ".hpp", ".cpp", ".txt"}


def iter_files() -> list[Path]:
  out: list[Path] = []
  for d in ROOT_DIRS:
    base = ROOT / d
    if not base.exists():
      continue
    for p in base.rglob("*"):
      if not p.is_file():
        continue
      if any(part in SKIP_PARTS for part in p.parts):
        continue
      if p.suffix.lower() not in EXT_OK:
        continue
      if p.name.startswith("_rename_naming") or p.name.startswith("_fix_dunders"):
        continue
      out.append(p)
  skill = ROOT / ".cursor" / "skills" / "py2cpp-design"
  if skill.exists():
    out.extend(skill.rglob("*.md"))
  return out


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--dry-run", action="store_true")
  ap.add_argument("--dump-map", action="store_true")
  args = ap.parse_args()

  mapping = build_map()
  # 去掉恒等映射与 KEEP
  mapping = {
    k: v for k, v in mapping.items()
    if k != v and k not in KEEP and not (k.endswith("_") and not k.startswith("__"))
  }
  assert "native_name" not in mapping
  assert "None_" not in mapping
  assert "__init__" not in mapping
  if args.dump_map:
    for k in sorted(mapping, key=lambda x: (-len(x), x)):
      print(f"{k} -> {mapping[k]}")
    print(f"total={len(mapping)}")
    return 0

  changed = 0
  for p in iter_files():
    try:
      raw = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
      continue
    native = p.suffix.lower() in {".inl", ".h", ".hpp", ".cpp"}
    new = transform_text(raw, mapping, native_file=native)
    if new != raw:
      changed += 1
      print(f"rewrite {p.relative_to(ROOT)}")
      if not args.dry_run:
        p.write_text(new, encoding="utf-8", newline="\n")
  print(f"files_changed={changed} map_size={len(mapping)}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
