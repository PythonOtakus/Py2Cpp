from ..builtins import *
from ..core.exceptions import Exception
from .protocols import Connection, Cursor, Dialect
# 翻译闭包拉取 FFI 声明 + glue（``templates/sql/+sqlite.inl`` 经 ``ffi::sqlite::sqlite3`` 调 C）
from ffi.sqlite.sqlite3 import sqlite3_open as _ffi_sqlite3_open


class Error(Exception):
  """``sqlite3.Error`` 对齐。"""

  pass


class DatabaseError(Error):
  pass


class IntegrityError(DatabaseError):
  pass


class OperationalError(DatabaseError):
  pass


@copyable
class SqliteDialect:
  @immutable
  def placeholder(self, index: int) -> str:
    return "?"

  @immutable
  def column_sql(self, field_type: str) -> str:
    match field_type:
      case "int":
        return "INTEGER"
      case "bool":
        return "INTEGER"
      case "varint":
        return "INTEGER"
      case "str":
        return "TEXT"
      case "float":
        return "REAL"
      case "bytes":
        return "BLOB"
      case _:
        return "TEXT"

  @immutable
  def last_insert_id_sql(self) -> str:
    return "SELECT last_insert_rowid()"


@native
@uncopyable
@native_name("Py*")
class SqliteCursor:
  """``sqlite3.Cursor`` 子集；当前行由 C++ 侧 ``sqlite3_stmt`` 持有。"""

  _stmt: uint64
  _done: bool

  def __init__(self, stmt: uint64): ...

  def __del__(self): ...

  def fetchone(self) -> tuple[int] | None:
    ...

  def fetchall(self) -> list[tuple[int]]:
    ...


@native
@uncopyable
@native_name("Py*")
class SqliteConnection:
  _db: uint64
  _closed: bool

  def __init__(self): ...

  def __del__(self): ...

  def _open_impl(self, path: str) -> None:
    ...

  @staticmethod
  def open(path: str) -> Self:
    ...

  def execute(self, sql: str, params: list[int]) -> SqliteCursor:
    ...

  def executemany(self, sql: str, seq: list[list[int]]) -> None:
    ...

  def commit(self) -> None:
    ...

  def rollback(self) -> None:
    ...

  def close(self) -> None:
    ...


@native
@immutable
def connect(path: str) -> SqliteConnection:
  ...