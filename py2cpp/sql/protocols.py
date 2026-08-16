"""SQL 协议：``ConnectionType`` / ``CursorType`` / ``DialectType``（ORM ``SqlQuery`` 见 P2）。"""
from ..builtins import *
from ..core.protocols import protocol


@protocol
class CursorType:
  def fetchOne(self) -> tuple[int] | None:
    ...

  def fetchAll(self) -> list[tuple[int]]:
    ...


@protocol
class DialectType:
  def placeholder(self, index: int) -> str:
    ...

  def columnSql(self, fieldType: str) -> str:
    ...

  def lastInsertIdSql(self) -> str:
    ...


@protocol
class ConnectionType:
  def execute(self, sql: str, params: list[int]) -> CursorType:
    ...

  def executeMany(self, sql: str, seq: list[list[int]]) -> None:
    ...

  def commit(self) -> None:
    ...

  def rollback(self) -> None:
    ...

  def close(self) -> None:
    ...
