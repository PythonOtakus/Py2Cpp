"""译器单测夹具：显式 import sqlite FFI（勿 star-import）。"""
from py2cpp import *
from ffi.sqlite.sqlite3 import SQLITE_OK, sqlite3_open, sqlite3_close


def main() -> int:
  _ = SQLITE_OK
  _ = sqlite3_open
  _ = sqlite3_close
  return 0
