"""字节流读写（HTTP 报文传输层）。"""
from ..builtins import *
from ..io import CloseMixin
from ..text.bytes import bytes
from .socket import AsyncTcpSocket, TcpSocket


@immutable
def _append_bytes(dst: byte[:], at: int, src: byte[:], end: int) -> None:
  if end <= 0:
    return
  need: int = at + end
  n: int = len(dst)
  if need > n:
    dst.reshape(need, n)
  for i in range(end):
    dst[at + i] = src[i]


@immutable
def _append_bytes_from_bytes(dst: byte[:], at: int, src: bytes, end: int) -> None:
  if end <= 0:
    return
  need: int = at + end
  n: int = len(dst)
  if need > n:
    dst.reshape(need, n)
  for i in range(end):
    dst[at + i] = src[i]


@immutable
def _bytes_match_at(buf: byte[:], at: int, end: int, sep: bytes, sep_n: int) -> bool:
  if at + sep_n > end:
    return False
  for j in range(sep_n):
    if buf[at + j] != sep[j]:
      return False
  return True


@immutable
def _find_bytes_at(buf: byte[:], start: int, end: int, sep: bytes, sep_n: int) -> int:
  for i in range(start, end):
    if _bytes_match_at(buf, i, end, sep, sep_n):
      return i
  return -1


@immutable
def _bytes_range(buf: byte[:], start: int, n: int) -> bytes:
  out: byte[:] = new(n)
  for i in range(n):
    out[i] = buf[start + i]
  return bytes(out)


@copyable
class StreamReader(CloseMixin):
  """缓冲式读流；可绑定 ``TcpSocket`` 或纯内存（测试）。"""

  def __init__(self):
    self._sock: TcpSocket = new()
    self._pos: int = 0
    self._live: bool = False
    self._closed: bool = False
    self._buf: byte[:] = b""

  @staticmethod
  def from_socket(sock: TcpSocket) -> Self:
    r: Self = new()
    r._sock = sock
    r._live = True
    return r

  @overload
  def load_bytes(self, data: byte[:]) -> None:
    """把 ``byte[:]`` 载入内存读缓冲。"""
    n: int = len(data)
    self._buf.reshape(n, 0)
    for i in range(n):
      self._buf[i] = data[i]
    self._pos = 0
    self._live = False

  @overload
  def load_bytes(self, data: bytes) -> None:
    """``bytes`` 载入内存读缓冲。"""
    n: int = len(data)
    self._buf.reshape(n, 0)
    for i in range(n):
      self._buf[i] = data[i]
    self._pos = 0
    self._live = False

  @staticmethod
  def from_bytes(data: byte[:]) -> Self:
    r: Self = new()
    r.load_bytes(data)
    return r

  def close(self) -> None:
    if self._closed:
      return
    self._closed = True
    if self._live:
      self._sock.close()

  @immutable
  def _avail(self) -> int:
    return len(self._buf) - self._pos

  def _fill(self) -> bool:
    if not self._live or self._closed:
      return False
    chunk: byte[:] = new(4096)
    got: int = self._sock.recv(chunk, 4096)
    if got <= 0:
      return False
    at: int = len(self._buf)
    _append_bytes(self._buf, at, chunk, got)
    return True

  def readexactly(self, n: int) -> bytes:
    if n <= 0:
      empty: bytes = b""
      return empty
    while self._avail() < n:
      if not self._fill():
        raise RuntimeError("stream ended before readexactly")
    buf: byte[:] = new(n)
    for i in range(n):
      buf[i] = self._buf[self._pos + i]
    self._pos += n
    return bytes(buf)

  def readuntil(self, sep: bytes) -> bytes:
    """读到 ``sep`` 末尾（含 ``sep``）。"""
    sep_n: int = len(sep)
    if sep_n <= 0:
      empty: bytes = b""
      return empty
    while True:
      start: int = self._pos
      end: int = len(self._buf)
      found: int = _find_bytes_at(self._buf, start, end, sep, sep_n)
      if found >= 0:
        take: int = (found + sep_n) - start
        out: bytes = _bytes_range(self._buf, start, take)
        self._pos = found + sep_n
        return out
      if not self._fill():
        raise RuntimeError("stream ended before readuntil")


@copyable
class StreamWriter(CloseMixin):
  """缓冲式写流。"""

  def __init__(self):
    self._sock: TcpSocket = new()
    self._live: bool = False
    self._closed: bool = False
    self._buf: byte[:] = b""

  @staticmethod
  def from_socket(sock: TcpSocket) -> Self:
    w: Self = new()
    w._sock = sock
    w._live = True
    return w

  @staticmethod
  def from_buffer() -> Self:
    w: Self = new()
    w._live = False
    return w

  def write(self, data: bytes) -> int:
    if self._closed:
      return 0
    n: int = len(data)
    if n <= 0:
      return 0
    if self._live:
      chunk: byte[:] = new(n)
      for i in range(n):
        chunk[i] = data[i]
      sent: int = self._sock.send(chunk, n)
      return sent
    at: int = len(self._buf)
    _append_bytes_from_bytes(self._buf, at, data, n)
    return n

  def drain(self) -> None:
    pass

  def close(self) -> None:
    if self._closed:
      return
    self._closed = True
    if self._live:
      self._sock.close()

  @immutable
  def take_bytes(self) -> bytes:
    n: int = len(self._buf)
    return bytes(self._buf)


@refcount
class _AsyncStreamReaderState(
  friends=(AsyncStreamReader,),
):
  """``AsyncStreamReader`` 共享状态；coroutine 复制 reader 时仍共享缓冲。"""

  _sock: AsyncTcpSocket = new()
  _pos: int = 0
  _live: bool = False
  _closed: bool = False
  _buf: byte[:] = b""

  def __init__(self):
    self._sock = AsyncTcpSocket()
    self._pos = 0
    self._live = False
    self._closed = False
    self._buf = b""

  def close(self) -> None:
    if self._closed:
      return
    self._closed = True
    if self._live:
      self._sock.close()

  @immutable
  def _avail(self) -> int:
    return len(self._buf) - self._pos

  async def _fill(self) -> bool:
    if not self._live or self._closed:
      return False
    chunk: byte[:] = new(4096)
    got: int = await self._sock.recv(chunk, 4096)
    if got <= 0:
      return False
    at: int = len(self._buf)
    _append_bytes(self._buf, at, chunk, got)
    return True

  async def readexactly(self, n: int) -> bytes:
    if n <= 0:
      empty: bytes = b""
      return empty
    while self._avail() < n:
      filled: bool = await self._fill()
      if not filled:
        raise RuntimeError("stream ended before readexactly")
    buf: byte[:] = new(n)
    for i in range(n):
      buf[i] = self._buf[self._pos + i]
    self._pos += n
    return bytes(buf)

  async def readuntil(self, sep: bytes) -> bytes:
    """异步读到 ``sep`` 末尾（含 ``sep``）。"""
    sep_n: int = len(sep)
    if sep_n <= 0:
      empty: bytes = b""
      return empty
    while True:
      start: int = self._pos
      end: int = len(self._buf)
      found: int = _find_bytes_at(self._buf, start, end, sep, sep_n)
      if found >= 0:
        take: int = (found + sep_n) - start
        out: bytes = _bytes_range(self._buf, start, take)
        self._pos = found + sep_n
        return out
      filled: bool = await self._fill()
      if not filled:
        raise RuntimeError("stream ended before readuntil")


@copyable
class AsyncStreamReader:
  """异步缓冲式读流；绑定 ``AsyncTcpSocket``。"""

  _state: _AsyncStreamReaderState = new()

  def __init__(self):
    self._state = new()

  @staticmethod
  def from_socket(sock: AsyncTcpSocket) -> Self:
    r: Self = new()
    r._state._sock = sock
    r._state._live = True
    return r

  def close(self) -> None:
    self._state.close()

  def readexactly(self, n: int):
    return self._state.readexactly(n)

  def readuntil(self, sep: bytes):
    """异步读到 ``sep`` 末尾（含 ``sep``）。"""
    return self._state.readuntil(sep)


@refcount
class _AsyncStreamWriterState(
  friends=(AsyncStreamWriter,),
):
  """``AsyncStreamWriter`` 共享状态；coroutine 复制 writer 时仍共享缓冲。"""

  _sock: AsyncTcpSocket = new()
  _live: bool = False
  _closed: bool = False
  _buf: byte[:] = b""

  def __init__(self):
    self._sock = AsyncTcpSocket()
    self._live = False
    self._closed = False
    self._buf = b""

  async def write(self, data: bytes) -> int:
    if self._closed:
      return 0
    n: int = len(data)
    if n <= 0:
      return 0
    if self._live:
      await self._sock.send_all(data)
      return n
    at: int = len(self._buf)
    _append_bytes_from_bytes(self._buf, at, data, n)
    return n

  async def drain(self) -> None:
    return None

  def close(self) -> None:
    if self._closed:
      return
    self._closed = True
    if self._live:
      self._sock.close()

  @immutable
  def take_bytes(self) -> bytes:
    n: int = len(self._buf)
    return bytes(self._buf)


@copyable
class AsyncStreamWriter:
  """异步缓冲式写流；绑定 ``AsyncTcpSocket``。"""

  _state: _AsyncStreamWriterState = new()

  def __init__(self):
    self._state = new()

  @staticmethod
  def from_socket(sock: AsyncTcpSocket) -> Self:
    w: Self = new()
    w._state._sock = sock
    w._state._live = True
    return w

  @staticmethod
  def from_buffer() -> Self:
    w: Self = new()
    w._state._live = False
    return w

  def write(self, data: bytes):
    return self._state.write(data)

  def drain(self):
    return self._state.drain()

  def close(self) -> None:
    self._state.close()

  @immutable
  def take_bytes(self) -> bytes:
    return self._state.take_bytes()
