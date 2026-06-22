"""字节流读写（HTTP 报文传输层）。"""
from ..builtins import *
from ..io import CloseMixin
from ..text.bytes import bytes
from .socket import TcpSocket


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


@copyable
class StreamReader(CloseMixin):
  """缓冲式读流；可绑定 ``TcpSocket`` 或纯内存（测试）。"""

  def __init__(self):
    self._sock: TcpSocket = new()
    self._pos: int = 0
    self._live: bool = False
    self._closed: bool = False
    empty: bytes = b""
    self._buf: byte[:] = empty.data

  @staticmethod
  def from_socket(sock: TcpSocket) -> Self:
    r: Self = new()
    r._sock = sock
    r._live = True
    return r

  def load_bytes(self, data: byte[:]) -> None:
    """把 ``byte[:]`` 载入内存读缓冲。"""
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
    out: bytes = new(n)
    for i in range(n):
      out.data[i] = self._buf[self._pos + i]
    self._pos += n
    return out

  def readuntil(self, sep: bytes) -> bytes:
    """读到 ``sep`` 末尾（含 ``sep``）。"""
    sep_n: int = len(sep.data)
    if sep_n <= 0:
      empty: bytes = b""
      return empty
    while True:
      start: int = self._pos
      end: int = len(self._buf)
      for i in range(start, end):
        matched: bool = True
        for j in range(sep_n):
          if i + j >= end or self._buf[i + j] != sep.data[j]:
            matched = False
            break
        if matched:
          take: int = (i + sep_n) - start
          out: bytes = new(take)
          for k in range(take):
            out.data[k] = self._buf[start + k]
          self._pos = i + sep_n
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
    empty: bytes = b""
    self._buf: byte[:] = empty.data

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
      sent: int = self._sock.send(data.data, n)
      return sent
    at: int = len(self._buf)
    _append_bytes(self._buf, at, data.data, n)
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
    out: bytes = new(n)
    for i in range(n):
      out.data[i] = self._buf[i]
    return out
