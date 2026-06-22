"""SQL 协议：``Connection`` / ``Cursor`` / ``Dialect``（ORM ``SqlQuery`` 见 P2）。"""
from ..builtins import *
from ..core.protocols import protocol


@protocol
class Cursor:
  def fetchone(self) -> tuple[int] | None:
    ...

  def fetchall(self) -> list[tuple[int]]:
    ...


@protocol
class Dialect:
  def placeholder(self, index: int) -> str:
    ...

  def column_sql(self, field_type: str) -> str:
    ...

  def last_insert_id_sql(self) -> str:
    ...


@protocol
class Connection:
  def execute(self, sql: str, params: list[int]) -> Cursor:
    ...

  def executemany(self, sql: str, seq: list[list[int]]) -> None:
    ...

  def commit(self) -> None:
    ...

  def rollback(self) -> None:
    ...

  def close(self) -> None:
    ...
