#!/usr/bin/env python3
"""Scan py2cpp/test/examples for stuck all-lowercase / snake / expandtabsXxx names."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORCE: dict[str, str] = {
  "fillchar": "fillChar",
  "tabsize": "tabSize",
  "keepends": "keepEnds",
  "maxsplit": "maxSplit",
  "chunksize": "chunkSize",
  "maxsize": "maxSize",
  "newsize": "newSize",
  "numbytes": "numBytes",
  "nondirs": "nonDirs",
  "pathname": "pathName",
  "multimode": "multiMode",
  "expandtabs": "expandTabs",
  "maketrans": "makeTrans",
  "swapcase": "swapCase",
  "startswith": "startsWith",
  "endswith": "endsWith",
  "removeprefix": "removePrefix",
  "removesuffix": "removeSuffix",
  "splitlines": "splitLines",
  "setdefault": "setDefault",
  "fromkeys": "fromKeys",
  "fromordinal": "fromOrdinal",
  "fromtimestamp": "fromTimestamp",
  "toordinal": "toOrdinal",
  "isoformat": "isoFormat",
  "returncode": "returnCode",
  "readinto": "readInto",
  "readlines": "readLines",
  "writelines": "writeLines",
  "readline": "readLine",
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
  "appendleft": "appendLeft",
  "extendleft": "extendLeft",
  "popleft": "popLeft",
  "encodebytes": "encodeBytes",
  "decodebytes": "decodeBytes",
  "executemany": "executeMany",
  "randbytes": "randBytes",
  "iterdir": "iterDir",
  "copysign": "copySign",
  "joinpath": "joinPath",
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
  "isatty": "isAtty",
  "isfile": "isFile",
  "isdir": "isDir",
  "islink": "isLink",
  "isabs": "isAbs",
  "lexists": "lExists",
  "rpartition": "rPartition",
  "bitlength": "bitLength",
  "bitcount": "bitCount",
  "lineterminator": "lineTerminator",
  "bufsize": "bufSize",
  "closefd": "closeFd",
  "exist_ok": "existOk",
  "missing_ok": "missingOk",
  "follow_symlinks": "followSymlinks",
  "case_sensitive": "caseSensitive",
  "ignore_case": "ignoreCase",
  "ignorecase": "ignoreCase",
  "dir_fd": "dirFd",
  "effective_ids": "effectiveIds",
  "asctime": "ascTime",
  "localtime": "localTime",
  "gmtime": "gmTime",
  "mktime": "mkTime",
  # keep strftime/strptime as coined single tokens (not in FORCE)
  "wrap_std": "wrapStd",
  "wrap_fp": "wrapFp",
  "altsep": "AltSep",
  "extsep": "ExtSep",
  "pathsep": "PathSep",
  "curdir": "CurDir",
  "pardir": "ParDir",
  "defpath": "DefPath",
  "devnull": "DevNull",
}

# Already-correct camelCase compounds we still want to detect if stuck form remains
SKIP_BODY = {
  "xsplit",
  "xrsplit",
  "xsplitLines",
  "native_name",
  "global_call",
  "strftime",
  "strptime",
  "datetime",
  "timestamp",
  "password",
  "symlink",
  "scandir",
  "frozenset",
  "capitalize",
  "partition",
  "translate",
  "replace",
}


def suggest(name: str) -> str | None:
  private = name.startswith("_") and not name.startswith("__")
  body = name[1:] if private else name
  if body in SKIP_BODY or name.startswith("__"):
    return None
  # expandtabsResetsCol
  m = re.fullmatch(r"([a-z]+)([A-Z].*)", body)
  if m and m.group(1) in FORCE:
    sug = ("_" if private else "") + FORCE[m.group(1)] + m.group(2)
    return sug if sug != name else None
  if body in FORCE:
    sug = ("_" if private else "") + FORCE[body]
    return sug if sug != name else None
  if re.fullmatch(r"[a-z]+(_[a-z0-9]+)+", body):
    parts = body.split("_")
    camel = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    sug = ("_" if private else "") + camel
    return sug if sug != name else None
  return None


def main() -> None:
  found: dict[str, dict] = {}
  for d in ("py2cpp", "test", "examples"):
    base = ROOT / d
    if not base.exists():
      continue
    for path in base.rglob("*.py"):
      if "generated" in path.parts:
        continue
      try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
      except SyntaxError:
        continue
      rel = str(path.relative_to(ROOT))
      for node in ast.walk(tree):
        names: list[tuple[str, str]] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
          names.append((node.name, "func"))
          for a in (
            list(node.args.args)
            + list(node.args.posonlyargs)
            + list(node.args.kwonlyargs)
          ):
            names.append((a.arg, "param"))
          if node.args.vararg:
            names.append((node.args.vararg.arg, "param"))
          if node.args.kwarg:
            names.append((node.args.kwarg.arg, "param"))
        elif isinstance(node, ast.ClassDef):
          for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
              names.append((stmt.target.id, "field"))
            elif isinstance(stmt, ast.Assign):
              for t in stmt.targets:
                if isinstance(t, ast.Name):
                  names.append((t.id, "field"))
        for name, kind in names:
          sug = suggest(name)
          if not sug:
            continue
          info = found.setdefault(name, {"sug": sug, "kind": set(), "files": set()})
          info["kind"].add(kind)
          info["files"].add(rel)

  print("=== NEED RENAME ===")
  for name in sorted(found, key=lambda n: (found[n]["sug"], n)):
    info = found[name]
    kinds = ",".join(sorted(info["kind"]))
    nfiles = len(info["files"])
    sample = sorted(info["files"])[0]
    print(f"{name:40} -> {info['sug']:40}  [{kinds}]  {nfiles}  {sample}")
  print("TOTAL", len(found))


if __name__ == "__main__":
  main()
