"""译器单测夹具：显式 import sqlite FFI（勿 star-import）。"""
from py2cpp import *
from ffi.sqlite.sqlite3 import Pyi_SQLITE_OK, Pyi_sqlite3_open, Pyi_sqlite3_close


def main() -> int:
  _ = Pyi_SQLITE_OK
  _ = Pyi_sqlite3_open
  _ = Pyi_sqlite3_close
  return 0
