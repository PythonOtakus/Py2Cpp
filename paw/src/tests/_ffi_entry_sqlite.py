"""译器单测夹具：显式 import sqlite FFI（勿 star-import）。"""
from py2cpp import *
from ffi.sqlite.sqlite3 import PyiSqliteOk, pyiSqlite3Open, pyiSqlite3Close


def main() -> int:
  _ = PyiSqliteOk
  _ = pyiSqlite3Open
  _ = pyiSqlite3Close
  return 0
