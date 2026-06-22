"""I/O 协议：``TextWriter`` / ``TextReader`` / ``TextIO``（``@protocol``，供 ``Json`` 等）。"""
from ..builtins import *
from __future__ import annotations

from ..core.protocols import Self, protocol


@protocol
class TextWriter:
  """文本写出端；``TextIOWrapper`` / ``StringIO`` 均实现。"""

  @overload
  def write(self, s: str) -> int: ...

  @overload
  def write(self, src: char[:], end: int) -> int: ...


@protocol
class TextReader:
  """文本读入端；``TextIOWrapper`` / ``StringIO`` 均实现。"""

  def read(self, size: int = -1) -> str: ...


@protocol
class TextIO:
  """文本双向流（``io.TextIOBase`` 子集）；``StringIO`` / ``TextIOWrapper`` 均实现。"""

  def __bool__(self) -> bool: ...

  def __enter__(self) -> Self: ...

  def __exit__(self): ...

  def read(self, size: int = -1) -> str: ...

  def readline(self, size: int = -1) -> str: ...

  def readlines(self, hint: int = -1) -> list[str]: ...

  @overload
  def write(self, s: str) -> int: ...

  @overload
  def write(self, src: char[:], end: int) -> int: ...

  def writelines(self, lines: list[str]) -> None: ...

  def __iter__(self) -> Self: ...

  def __next__(self) -> str: ...

  def close(self) -> None: ...

  def seek(self, pos: int, whence: int = 0) -> int: ...

  def tell(self) -> int: ...
