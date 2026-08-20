"""``io``：文本文件 I/O 与内存字符串流（对齐 Python 3.13 ``io`` 子集）。

参考 CPython 3.13 ``Modules/_io``、``Objects/fileobject.c``（``FILE*``）与
``Lib/_pyio.py`` 中 ``StringIO`` 语义；实现不用 STL，文件层经 ``ffi.crt.stdio``，
``StringIO`` 用 ``char[:]`` 码点缓冲 + ``str.copyTo``（见编码规范 §9）。
"""
from ..builtins import *
from ..text import str
from ..util.list import list
from ..util.memory import appendChars
from ffi.crt.stdio import (
  PyiIobuf,
  PyiSeekCur,
  PyiSeekEnd,
  PyiSeekSet,
  pyiAcrtIobFunc,
  pyiFclose,
  pyiFflush,
  pyiFgets,
  pyiFileno,
  pyiFopen,
  pyiFread,
  pyiFseek,
  pyiFtell,
  pyiFwrite,
)
from ffi.crt.io import pyiIsatty


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

  def flush(self) -> None:
    """内存流无缓冲副作用；保留 API 与 ``TextIOWrapper.flush`` 对齐。"""
    return

  @property
  @immutable
  def isAtty(self) -> bool:
    return False

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
    self._pos = s.copyTo(self._buf, self._pos)
    return sn

  @overload
  def write(self, src: char[:], end: int = int.Max) -> int:
    """自 ``_pos`` 写入 ``src[0:end]``（无 ``str`` 中间对象；``Json.dump`` 紧凑路径）。"""
    if self._closed:
      return 0
    if end > len(src):
      end = len(src)
    if end <= 0:
      return 0
    self._pos = appendChars(self._buf, self._pos, src, end)
    return end

  def read(self, size: int = int.Max) -> str:
    if self._closed:
      return ""
    if size < 0:
      raise ValueError("size must be non-negative")
    n: int = len(self._buf)
    at: int = self._pos
    if at >= n:
      return ""
    if size == int.Max:
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

  def readLine(self, size: int = int.Max) -> str:
    if self._closed:
      return ""
    if size < 0:
      raise ValueError("size must be non-negative")
    n: int = len(self._buf)
    at: int = self._pos
    if at >= n:
      return ""
    limit: int = n
    if size != int.Max:
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

  def readLines(self, hint: int = int.Max) -> list[str]:
    """按行读到 EOF；``hint`` 为已读字符累计上界（对齐 CPython ``TextIOBase.readLines``）。"""
    if hint < 0:
      raise ValueError("hint must be non-negative")
    lines: list[str] = []
    while True:
      line: str = self.readLine()
      if not line:
        break
      lines.append(line)
      if hint != int.Max:
        hint -= len(line)
        if hint <= 0:
          break
    return lines

  def writeLines(self, lines: list[str]) -> None:
    """逐行 ``write``（不自动补换行，对齐 CPython ``TextIOBase.writeLines``）。"""
    for line in lines:
      self.write(line)

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> str:
    line: str = self.readLine()
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

  def _ensureRoom(self, end: int) -> None:
    n: int = len(self._buf)
    if end <= n:
      return
    self._buf.reshape(end, 0)

  def clearBuffer(self) -> None:
    """清空缓冲（保留容量）；流式 ``dump`` 前可调用。"""
    self._buf.reshape(0, 0)
    self._pos = 0


@uncopyable
class TextIOWrapper(CloseMixin):
  """基于 ``FILE*`` 的文本文件包装（``ffi.crt.stdio``）。

  ``wrapFp`` / ``wrapStd`` 可绑定已有句柄；``owns=False`` 时 ``close``/``with``/析构
  **不** ``fclose`` 真实标准流（见 ``docs/console.md``）。
  """

  _fp: Pointer[PyiIobuf]
  _closed: bool = True
  _owns: bool = False

  @overload
  def __init__(self, path: str, mode: str = "r"):
    self._owns = True
    self._closed = False
    m: str = mode
    if not m:
      m = "r"
    with path.useUtf8() as cpath:
      with m.useUtf8() as cmode:
        self._fp = pyiFopen(cpath, cmode)
    if self._fp is None:
      self._closed = True

  @overload
  def __init__(self, fp: uintptr, owns: bool):
    self._fp = cast(fp)
    self._owns = owns
    self._closed = fp == 0

  def __del__(self):
    if self._owns:
      self.close()

  @immutable
  def __bool__(self) -> bool:
    return (self._fp is not None) and (not self._closed)

  def read(self, size: int = int.Max) -> str:
    if self._fp is None or self._closed:
      return ""
    if size < 0:
      raise ValueError("size must be non-negative")
    if size == int.Max:
      codes: char[:] = new(0)
      total: int = 0
      chunk: byte[:] = new(4096)
      tmp: char[:] = new(4096)
      addr: uintptr = cast(chunk.view.at(0))
      while True:
        n = int(pyiFread(addr, 1, 4096, self._fp))
        if n <= 0:
          break
        for i in range(n):
          tmp[i] = char(chunk[i])
        total = appendChars(codes, total, tmp, n)
      if total <= 0:
        return ""
      return str.fromArray(codes, total)
    cap: int = size
    if cap <= 0:
      return ""
    if cap > 4096:
      cap = 4096
    buf: byte[:] = new(cap)
    addr2: uintptr = cast(buf.view.at(0))
    n2 = int(pyiFread(addr2, 1, uint64(cap), self._fp))
    if n2 <= 0:
      return ""
    return str.fromSpanBytes(buf.view[:n2])

  def readLine(self, size: int = int.Max) -> str:
    if self._fp is None or self._closed:
      return ""
    if size < 0:
      raise ValueError("size must be non-negative")
    cap: int = 4096
    if size > 0 and size < cap:
      cap = size
    buf: byte[:] = new(cap)
    p: utf8ptr = pyiFgets(buf.view.at(0), cap, self._fp)
    if p is None:
      return ""
    return str.fromSpanBytes(p.view)

  def readLines(self, hint: int = int.Max) -> list[str]:
    if hint < 0:
      raise ValueError("hint must be non-negative")
    lines: list[str] = []
    rest: int = hint
    while True:
      line: str = self.readLine()
      if not line:
        break
      lines.append(line)
      if rest != int.Max:
        rest -= len(line)
        if rest <= 0:
          break
    return lines

  @overload
  def write(self, data: str) -> int:
    if self._fp is None or self._closed:
      return -1
    n: int = len(data)
    if n <= 0:
      return 0
    stack: byte[:] = new(4096)
    addr: uintptr = cast(stack.view.at(0))
    at: int = 0
    for i in range(n):
      if at >= 4096:
        if int(pyiFwrite(addr, 1, uint64(at), self._fp)) != at:
          return -1
        at = 0
      stack[at] = byte(int(data[i]) & 0xFF)
      at += 1
    if at > 0:
      if int(pyiFwrite(addr, 1, uint64(at), self._fp)) != at:
        return -1
    return n

  @overload
  def write(self, src: char[:], end: int = int.Max) -> int:
    if self._fp is None or self._closed:
      return -1
    if end > len(src):
      end = len(src)
    if end <= 0:
      return 0
    stack: byte[:] = new(4096)
    addr: uintptr = cast(stack.view.at(0))
    at: int = 0
    for i in range(end):
      if at >= 4096:
        if int(pyiFwrite(addr, 1, uint64(at), self._fp)) != at:
          return -1
        at = 0
      stack[at] = byte(int(src[i]) & 0xFF)
      at += 1
    if at > 0:
      if int(pyiFwrite(addr, 1, uint64(at), self._fp)) != at:
        return -1
    return end

  def writeLines(self, lines: list[str]) -> None:
    for line in lines:
      self.write(line)

  def flush(self) -> None:
    if self._fp is not None and not self._closed:
      pyiFflush(self._fp)

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> str:
    line: str = self.readLine()
    if not line:
      raise StopIteration
    return line

  def close(self) -> None:
    if self._fp is not None and not self._closed:
      pyiFflush(self._fp)
      if self._owns:
        pyiFclose(self._fp)
        self._fp = None
    self._closed = True

  def seek(self, pos: int, whence: int = 0) -> int:
    if self._fp is None or self._closed:
      return -1
    origin: int = PyiSeekSet
    if whence == 1:
      origin = PyiSeekCur
    elif whence == 2:
      origin = PyiSeekEnd
    if pyiFseek(self._fp, pos, origin) == 0:
      return 0
    return -1

  def tell(self) -> int:
    if self._fp is None or self._closed:
      return -1
    return int(pyiFtell(self._fp))

  @property
  @immutable
  def isAtty(self) -> bool:
    if self._fp is None or self._closed:
      return False
    return pyiIsatty(pyiFileno(self._fp)) != 0


@global_call("py_*")
def open(path: str, mode: str = "r", encoding: str = "utf-8") -> TextIOWrapper:
  """``open(path, mode)`` → ``TextIOWrapper``（``encoding`` 暂仅支持类 UTF-8 码点路径）。"""
  _ = encoding
  return new(path, mode)


@global_call("py_*")
def wrapFp(fp: uintptr, owns: bool = False) -> TextIOWrapper:
  """绑定已有 ``FILE*``（``fp`` 为指针位型）；``owns=False`` 时永不 ``fclose``。"""
  return new(fp, owns)


@global_call("py_*")
def wrapStd(fd: int) -> TextIOWrapper:
  """绑定标准流：``0``=stdin、``1``=stdout、``2``=stderr；始终 ``owns=False``。"""
  p: Pointer[PyiIobuf] = pyiAcrtIobFunc(uint(fd))
  h: uintptr = cast(p)
  return new(h, False)
