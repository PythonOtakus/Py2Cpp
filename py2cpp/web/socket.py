"""TCP 套接字（WinSock / BSD socket 叶子 ``@native``）。"""
from ..builtins import *
from ..core.exceptions import OSError
from ..concur.task import Task
from ..text.bytes import bytes


SOCKET_OK: int = 0
SOCKET_WOULD_BLOCK: int = -2


@native
@copyable
@native_name("Py*")
class TcpSocket:
  """IPv4 TCP 套接字。"""

  _state: uintptr = 0

  def __init__(self): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  def connect(self, host: str, port: int) -> None:
    """连接 ``host:port``。"""
    ...

  def bind(self, host: str, port: int) -> None:
    """绑定本地地址。"""
    ...

  def listen(self, backlog: int = 128) -> None:
    """开始监听（须先 ``bind``）。"""
    ...

  def accept(self) -> Self:
    """接受一个入站连接。"""
    ...

  def send(self, buf: byte[:], end: int) -> int:
    """发送 ``buf[:end]`` 字节，返回已发送数。"""
    ...

  def recv(self, buf: byte[:], cap: int) -> int:
    """读至多 ``cap`` 字节到 ``buf``，返回读到的字节数（``0`` 表示对端关闭）。"""
    ...

  def close(self) -> None:
    """关闭套接字。"""
    ...

  @immutable
  def is_closed(self) -> bool:
    """是否已关闭。"""
    ...

  def set_timeout(self, sec: float) -> None:
    """收发超时（秒）。"""
    ...

  def set_blocking(self, blocking: bool) -> None:
    """切换阻塞 / 非阻塞模式。"""
    ...

  def connect_ex(self, host: str, port: int) -> int:
    """非阻塞 connect；成功返回 ``SOCKET_OK``，进行中返回 ``SOCKET_WOULD_BLOCK``。"""
    ...

  def finish_connect(self) -> None:
    """等待写就绪后检查非阻塞 connect 的最终结果。"""
    ...

  def accept_nonblocking(self) -> Self:
    """非阻塞 accept；无连接时返回 closed socket。"""
    ...

  def send_range_nonblocking(self, buf: byte[:], start: int, end: int) -> int:
    """非阻塞发送 ``buf[start:end]``，would-block 返回 ``SOCKET_WOULD_BLOCK``。"""
    ...

  def recv_nonblocking(self, buf: byte[:], cap: int) -> int:
    """非阻塞接收，would-block 返回 ``SOCKET_WOULD_BLOCK``，``0`` 表示 EOF。"""
    ...

  @immutable
  def fileno(self) -> int64:
    """底层 socket/fd 句柄。"""
    ...

  @staticmethod
  @immutable
  def would_block(code: int) -> bool:
    """``connect_ex`` / 非阻塞收发返回码是否表示暂不可完成。"""
    ...


@copyable
class AsyncTcpSocket:
  """协作式异步 TCP socket；基于真实 non-blocking socket + ``Task`` IO readiness。"""

  _sock: TcpSocket = new()

  def __init__(self):
    self._sock = new()

  @staticmethod
  def from_socket(sock: TcpSocket) -> Self:
    out: Self = new()
    out._sock = sock
    out._sock.set_blocking(False)
    return out

  @immutable
  def is_closed(self) -> bool:
    return self._sock.is_closed()

  @immutable
  def fileno(self) -> int64:
    return self._sock.fileno()

  def close(self) -> None:
    self._sock.close()

  def bind(self, host: str, port: int) -> None:
    self._sock.bind(host, port)
    self._sock.set_blocking(False)

  def listen(self, backlog: int = 128) -> None:
    self._sock.listen(backlog)

  async def connect(self, host: str, port: int) -> None:
    self._sock.set_blocking(False)
    code: int = self._sock.connect_ex(host, port)
    if code == SOCKET_WOULD_BLOCK:
      await Task.wait_write(self._sock.fileno())
      self._sock.finish_connect()
      return
    if code != SOCKET_OK:
      raise OSError()

  async def accept(self) -> Self:
    while True:
      conn: TcpSocket = self._sock.accept_nonblocking()
      if not conn.is_closed():
        return new.from_socket(conn)
      await Task.wait_read(self._sock.fileno())

  async def recv(self, buf: byte[:], cap: int) -> int:
    while True:
      got: int = self._sock.recv_nonblocking(buf, cap)
      if got != SOCKET_WOULD_BLOCK:
        return got
      await Task.wait_read(self._sock.fileno())

  async def send_all(self, data: bytes) -> None:
    n: int = len(data)
    if n <= 0:
      return
    buf: byte[:] = new(n)
    for i in range(n):
      buf[i] = data[i]
    sent_total: int = 0
    while sent_total < n:
      sent: int = self._sock.send_range_nonblocking(buf, sent_total, n)
      if sent == SOCKET_WOULD_BLOCK:
        await Task.wait_write(self._sock.fileno())
      else:
        if sent <= 0:
          raise OSError()
        sent_total += sent
