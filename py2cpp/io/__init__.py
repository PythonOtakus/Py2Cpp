"""``io``：文本文件 I/O 与内存字符串流（对齐 Python 3.13 ``io`` 子集）。

参考 CPython 3.13 ``Modules/_io``、``Objects/fileobject.c``（``FILE*``）与
``Lib/_pyio.py`` 中 ``StringIO`` 语义；实现不用 STL，文件层用 C stdio，
``StringIO`` 用 ``char[:]`` 码点缓冲 + ``str.copy_to``（见编码规范 §9）。
"""
from ..builtins import *
from ..text import str
from ..util.list import list
from ..util.memory import append_chars


@mixin
class CloseMixin:
  """带 ``close()`` 的同步上下文管理器：``with`` 展开为 ``__enter__`` / ``__exit__``。"""

  def __enter__(self) -> Self:
    return self

  def __exit__(self):
    self.close()


@mixin
class AsyncCloseMixin:
  """带 ``async def close()`` 的异步上下文管理器：``__aexit__`` 内 ``await self.close()``。"""

  async def __aenter__(self) -> Self:
    return self

  async def __aexit__(self):
    await self.close()
    return None


@copyable
@native_name("Py*")
class StringIO(CloseMixin):
  """内存文本流：``write`` / ``read`` / ``value`` / ``pos`` / ``seek`` / ``tell``。"""

  def __init__(self, initial: str = ""):
    self._buf: char[:] = ""
    self._pos: int = 0
    self._closed: bool = False
    if initial:
      self.write(initial)
      self._pos = 0

  @immutable
  def __bool__(self) -> bool:
    return not self._closed

  @immutable
  def __len__(self) -> int:
    return len(self._buf)

  def close(self) -> None:
    self._closed = True

  @immutable
  def tell(self) -> int:
    return self._pos

  def seek(self, pos: int, whence: int = 0) -> int:
    if self._closed:
      return -1
    n: int = len(self._buf)
    if whence == 1:
      pos = self._pos + pos
    elif whence == 2:
      pos = n + pos
    if pos < 0:
      pos = 0
    if pos > n:
      pos = n
    self._pos = pos
    return pos

  @overload
  def write(self, s: str) -> int:
    if self._closed:
      return 0
    if not self._buf:
      self._pos = 0
    sn: int = len(s)
    if sn == 0:
      return 0
    self._pos = s.copy_to(self._buf, self._pos)
    return sn

  @overload
  def write(self, src: char[:], end: int) -> int:
    """自 ``_pos`` 写入 ``src[0:end]``（无 ``str`` 中间对象；``Json.dump`` 紧凑路径）。"""
    if self._closed:
      return 0
    if end <= 0:
      return 0
    self._pos = append_chars(self._buf, self._pos, src, end)
    return end

  def read(self, size: int = -1) -> str:
    if self._closed:
      return ""
    n: int = len(self._buf)
    at: int = self._pos
    if at >= n:
      return ""
    if size < 0:
      size = n - at
    if size > (n - at):
      size = n - at
    if size <= 0:
      return ""
    buf: char[:] = new(size)
    for i in range(size):
      buf[i] = self._buf[at + i]
    self._pos = at + size
    return str(buf)

  def readline(self, size: int = -1) -> str:
    if self._closed:
      return ""
    n: int = len(self._buf)
    at: int = self._pos
    if at >= n:
      return ""
    limit: int = n
    if size >= 0:
      limit = at + size
      if limit > n:
        limit = n
    i: int = at
    while i < limit:
      c: char = self._buf[i]
      if c == ord("\n"):
        i += 1
        break
      i += 1
    cnt: int = i - at
    if cnt <= 0:
      return ""
    buf: char[:] = new(cnt)
    for j in range(cnt):
      buf[j] = self._buf[at + j]
    self._pos = at + cnt
    return str(buf)

  def readlines(self, hint: int = -1) -> list[str]:
    """按行读到 EOF；``hint`` 为已读字符累计上界（对齐 CPython ``TextIOBase.readlines``）。"""
    lines: list[str] = []
    while True:
      line: str = self.readline()
      if not line:
        break
      lines.append(line)
      if hint >= 0:
        hint -= len(line)
        if hint <= 0:
          break
    return lines

  def writelines(self, lines: list[str]) -> None:
    """逐行 ``write``（不自动补换行，对齐 CPython ``TextIOBase.writelines``）。"""
    for line in lines:
      self.write(line)

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> str:
    line: str = self.readline()
    if not line:
      raise StopIteration
    return line

  @property
  @immutable
  def value(self) -> str:
    if self._closed:
      return ""
    n: int = len(self._buf)
    if n == 0:
      return ""
    buf: char[:] = new(n)
    for i in range(n):
      buf[i] = self._buf[i]
    return str(buf)

  def take(self) -> str:
    """移动取出缓冲为 ``str``（``str(self._buf)`` 接管 ``char[:]``，流内缓冲置空）。"""
    self._pos = 0
    return str(self._buf)

  @property
  @immutable
  def pos(self) -> int:
    return self.tell()

  @property.setter
  def pos(self, value: int):
    self.seek(value)

  def _ensure_room(self, end: int) -> None:
    n: int = len(self._buf)
    if end <= n:
      return
    self._buf.reshape(end, 0)

  def clear_buffer(self) -> None:
    """清空缓冲（保留容量）；流式 ``dump`` 前可调用。"""
    self._buf.reshape(0, 0)
    self._pos = 0


@native
@uncopyable
@native_name("Py*")
class TextIOWrapper:
  """基于 ``FILE*`` 的文本文件包装（实现见 ``io.inl``）。"""

  _fp: uintptr
  _closed: bool

  def __init__(self, path: str, mode: str = "r"): ...

  def __del__(self): ...

  def __bool__(self) -> bool: ...

  def __enter__(self) -> Self: ...

  def __exit__(self): ...

  def read(self, size: int = -1) -> str: ...

  def readline(self, size: int = -1) -> str: ...

  def readlines(self, hint: int = -1) -> list[str]: ...

  @overload
  def write(self, data: str) -> int: ...

  @overload
  def write(self, src: char[:], end: int) -> int: ...

  def writelines(self, lines: list[str]) -> None: ...

  def __iter__(self) -> Self: ...

  def __next__(self) -> str: ...

  def close(self) -> None: ...

  def seek(self, pos: int, whence: int = 0) -> int: ...

  def tell(self) -> int: ...


@native
@global_call("py_*")
def open(path: str, mode: str = "r", encoding: str = "utf-8") -> TextIOWrapper:
  """``open(path, mode)`` → ``TextIOWrapper``（``encoding`` 暂仅支持类 UTF-8 码点路径）。"""
  ...
