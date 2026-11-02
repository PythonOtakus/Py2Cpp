#!/usr/bin/env python3
"""CLI：从 C 头生成 Py2Cpp ``.pyi``（核心在 ``src.tools.c_ffi_pyi``）。

见 ``docs/c-ffi-pyi.md``。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from src.tools.c_ffi_pyi import generate_pyi  # noqa: E402


def main(argv: list[str] | None = None) -> int:
  ap = argparse.ArgumentParser(
    description="Generate Py2Cpp .pyi FFI stubs from a C header (libclang). "
    "Prefer: ffi.bat <header> …",
  )
  ap.add_argument(
    "header",
    nargs="?",
    default=None,
    help="Input .h path, or bare name `windows` / `gl` (auto-finds Windows Kits)",
  )
  ap.add_argument(
    "--header",
    dest="header_opt",
    default=None,
    help="Same as positional header (kept for scripts)",
  )
  ap.add_argument(
    "--out",
    type=Path,
    default=None,
    help="Output .pyi (default: ffi/…; Win32 um→ffi/windows/<stem>.pyi; UCRT→ffi/crt/<stem>.pyi)",
  )
  ap.add_argument(
    "--check",
    action="store_true",
    help="Validate; if --out exists, require identical content (ignore Generated timestamp)",
  )
  ap.add_argument(
    "--include-deps",
    action=argparse.BooleanOptionalAction,
    default=None,
    help="Collect decls from transitive includes under SDK/third_party roots "
    "(default: on for Windows umbrella/UCRT, off for sqlite and Win32 child headers)",
  )
  ap.add_argument("--clang-arg", action="append", default=[], help="Extra libclang arg (repeatable)")
  ns = ap.parse_args(argv)
  header = ns.header_opt or ns.header
  if not header:
    ap.error("header required (e.g. ffi windows / ffi third_party\\sqlite\\sqlite3.h)")
  return generate_pyi(
    header,
    out=ns.out,
    clang_args=list(ns.clang_arg),
    check=bool(ns.check),
    include_deps=ns.include_deps,
  )


if __name__ == "__main__":
  raise SystemExit(main())
