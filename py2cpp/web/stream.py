"""字节流读写（HTTP 报文传输层）。"""
from ..builtins import *
from ..io import CloseMixin
from ..text.bytes import bytes
from .socket import AsyncTcpSocket, TcpSocket


@immutable
def _appendBytes(
  dst: byte[:],
  at: int,
  src: byte[:],
  end: int = int.Max,
) -> None:
  if end > len(src):
    end = len(src)
  if end <= 0:
    return
  need: int = at + end
  n: int = len(dst)
  if need > n:
    dst.reshape(need, n)
  for i in range(end):
    dst[at + i] = src[i]


@immutable
def _appendBytesFromBytes(
  dst: byte[:],
  at: int,
  src: bytes,
  end: int = int.Max,
) -> None:
  if end > len(src):
    end = len(src)
  if end <= 0:
    return
  need: int = at + end
  n: int = len(dst)
  if need > n:
    dst.reshape(need, n)
  for i in range(end):
    dst[at + i] = src[i]


@immutable
def _bytesMatchAt(buf: byte[:], at: int, end: int, sep: bytes, sepN: int) -> bool:
  if at + sepN > end:
    return False
  for j in range(sepN):
    if buf[at + j] != sep[j]:
      return False
  return True


@immutable
def _findBytesAt(buf: byte[:], start: int, end: int, sep: bytes, sepN: int) -> int:
  for i in range(start, end):
    if _bytesMatchAt(buf, i, end, sep, sepN):
      return i
  return -1


@immutable
def _bytesRange(buf: byte[:], start: int, n: int) -> bytes:
  out: byte[:] = new(n)
  for i in range(n):
    out[i] = buf[start + i]
  return bytes(out)


@refcount
class _StreamReaderState(
  friends=(StreamReader,),
):
  """``StreamReader`` 共享状态；复制 reader 时不复制底层 socket/缓冲。"""

  _sock: TcpSocket = new()
  _pos: int = 0
  _live: bool = False
  _closed: bool = False
  _buf: byte[:] = b""

  def loadArray(self, data: byte[:]) -> None:
    """把 ``byte[:]`` 载入内存读缓冲。"""
    n: int = len(data)
    self._buf.reshape(n, 0)
    for i in range(n):
      self._buf[i] = data[i]
    self._pos = 0
    self._live = False

  def loadBytesObj(self, data: bytes) -> None:
    """``bytes`` 载入内存读缓冲。"""
    n: int = len(data)
    self._buf.reshape(n, 0)
    for i in range(n):
      self._buf[i] = data[i]
    self._pos = 0
    self._live = False

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
    _appendBytes(self._buf, at, chunk, got)
    return True

  def readExactly(self, n: int) -> bytes:
    if n <= 0:
      empty: bytes = b""
      return empty
    while self._avail() < n:
      if not self._fill():
        raise RuntimeError("stream ended before readExactly")
    buf: byte[:] = new(n)
    for i in range(n):
      buf[i] = self._buf[self._pos + i]
    self._pos += n
    return bytes(buf)

  def readUntil(self, sep: bytes) -> bytes:
    """读到 ``sep`` 末尾（含 ``sep``）。"""
    sepN: int = len(sep)
    if sepN <= 0:
      empty: bytes = b""
      return empty
    while True:
      start: int = self._pos
      end: int = len(self._buf)
      found: int = _findBytesAt(self._buf, start, end, sep, sepN)
      if found >= 0:
        take: int = (found + sepN) - start
        out: bytes = _bytesRange(self._buf, start, take)
        self._pos = found + sepN
        return out
      if not self._fill():
        raise RuntimeError("stream ended before readUntil")


@copyable
class StreamReader(CloseMixin):
  """缓冲式读流；可绑定 ``TcpSocket`` 或纯内存（测试）。"""

  _state: _StreamReaderState = new()

  @staticmethod
  def fromSocket(sock: TcpSocket) -> Self:
    r: Self = new()
    r._state._sock = sock
    r._state._live = True
    return r

  @overload
  def loadBytes(self, data: byte[:]) -> None:
    """把 ``byte[:]`` 载入内存读缓冲。"""
    self._state.loadArray(data)

  @overload
  def loadBytes(self, data: bytes) -> None:
    """``bytes`` 载入内存读缓冲。"""
    self._state.loadBytesObj(data)

  @staticmethod
  def fromBytes(data: byte[:]) -> Self:
    r: Self = new()
    r.loadBytes(data)
    return r

  def close(self) -> None:
    self._state.close()

  @immutable
  def _avail(self) -> int:
    return self._state._avail()

  @immutable
  def available(self) -> int:
    """当前缓冲区内可立即读取的字节数。"""
    return self._state._avail()

  def _fill(self) -> bool:
    return self._state._fill()

  def readExactly(self, n: int) -> bytes:
    return self._state.readExactly(n)

  def readUntil(self, sep: bytes) -> bytes:
    """读到 ``sep`` 末尾（含 ``sep``）。"""
    return self._state.readUntil(sep)


@copyable
class StreamWriter(CloseMixin):
  """缓冲式写流。"""

  _sock: TcpSocket = new()
  _live: bool = False
  _closed: bool = False
  _buf: byte[:] = b""

  @staticmethod
  def fromSocket(sock: TcpSocket) -> Self:
    w: Self = new()
    w._sock = sock
    w._live = True
    return w

  @staticmethod
  def fromBuffer() -> Self:
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
    _appendBytesFromBytes(self._buf, at, data, n)
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
  def takeBytes(self) -> bytes:
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
    _appendBytes(self._buf, at, chunk, got)
    return True

  async def readExactly(self, n: int) -> bytes:
    if n <= 0:
      empty: bytes = b""
      return empty
    while self._avail() < n:
      filled: bool = await self._fill()
      if not filled:
        raise RuntimeError("stream ended before readExactly")
    buf: byte[:] = new(n)
    for i in range(n):
      buf[i] = self._buf[self._pos + i]
    self._pos += n
    return bytes(buf)

  async def readUntil(self, sep: bytes) -> bytes:
    """异步读到 ``sep`` 末尾（含 ``sep``）。"""
    sepN: int = len(sep)
    if sepN <= 0:
      empty: bytes = b""
      return empty
    while True:
      start: int = self._pos
      end: int = len(self._buf)
      found: int = _findBytesAt(self._buf, start, end, sep, sepN)
      if found >= 0:
        take: int = (found + sepN) - start
        out: bytes = _bytesRange(self._buf, start, take)
        self._pos = found + sepN
        return out
      filled: bool = await self._fill()
      if not filled:
        raise RuntimeError("stream ended before readUntil")


@copyable
class AsyncStreamReader:
  """异步缓冲式读流；绑定 ``AsyncTcpSocket``。"""

  _state: _AsyncStreamReaderState = new()

  @staticmethod
  def fromSocket(sock: AsyncTcpSocket) -> Self:
    r: Self = new()
    r._state._sock = sock
    r._state._live = True
    return r

  def close(self) -> None:
    self._state.close()

  def readExactly(self, n: int):
    return self._state.readExactly(n)

  def readUntil(self, sep: bytes):
    """异步读到 ``sep`` 末尾（含 ``sep``）。"""
    return self._state.readUntil(sep)


@refcount
class _AsyncStreamWriterState(
  friends=(AsyncStreamWriter,),
):
  """``AsyncStreamWriter`` 共享状态；coroutine 复制 writer 时仍共享缓冲。"""

  _sock: AsyncTcpSocket = new()
  _live: bool = False
  _closed: bool = False
  _buf: byte[:] = b""

  async def write(self, data: bytes) -> int:
    if self._closed:
      return 0
    n: int = len(data)
    if n <= 0:
      return 0
    if self._live:
      await self._sock.sendAll(data)
      return n
    at: int = len(self._buf)
    _appendBytesFromBytes(self._buf, at, data, n)
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
  def takeBytes(self) -> bytes:
    n: int = len(self._buf)
    return bytes(self._buf)


@copyable
class AsyncStreamWriter:
  """异步缓冲式写流；绑定 ``AsyncTcpSocket``。"""

  _state: _AsyncStreamWriterState = new()

  @staticmethod
  def fromSocket(sock: AsyncTcpSocket) -> Self:
    w: Self = new()
    w._state._sock = sock
    w._state._live = True
    return w

  @staticmethod
  def fromBuffer() -> Self:
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
  def takeBytes(self) -> bytes:
    return self._state.takeBytes()
