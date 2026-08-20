from ..builtins import *
from ..core.exceptions import Exception
from .protocols import ConnectionType, CursorType, DialectType
# 翻译闭包拉取 FFI 声明 + glue（``templates/sql/+sqlite.inl`` 经 ``ffi::sqlite::sqlite3`` 调 C）
from ffi.sqlite.sqlite3 import PyiSqlite3, PyiSqlite3Stmt
from ffi.sqlite.sqlite3 import pyiSqlite3Open as _ffi_sqlite3_open


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
  def columnSql(self, fieldType: str) -> str:
    match fieldType:
      case "int":
        return "INTEGER"
      case "bool":
        return "INTEGER"
      case "long":
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
  def lastInsertIdSql(self) -> str:
    return "SELECT last_insert_rowid()"


@native
@uncopyable
class SqliteCursor:
  """``sqlite3.CursorType`` 子集；当前行由 C++ 侧 ``sqlite3_stmt`` 持有。"""

  _stmt: Pointer[PyiSqlite3Stmt]
  _done: bool

  def __init__(self, stmt: Pointer[PyiSqlite3Stmt]): ...

  def __del__(self): ...

  def fetchOne(self) -> tuple[int] | None:
    ...

  def fetchAll(self) -> list[tuple[int]]:
    ...


@native
@uncopyable
class SqliteConnection:
  _db: Pointer[PyiSqlite3]
  _closed: bool

  def __init__(self): ...

  def __del__(self): ...

  def _openImpl(self, path: str) -> None:
    ...

  @staticmethod
  def open(path: str) -> Self:
    ...

  def execute(self, sql: str, params: list[int]) -> SqliteCursor:
    ...

  def executeMany(self, sql: str, seq: list[list[int]]) -> None:
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