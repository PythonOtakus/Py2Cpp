"""TCP 套接字（WinSock / BSD socket 叶子 ``@native``）。"""
from ..builtins import *
from ..core.exceptions import OSError
from ..concur.task import Task
from ..text.bytes import bytes


SocketOk: int = 0
SocketWouldBlock: int = -2


@native
@copyable
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
  def isClosed(self) -> bool:
    """是否已关闭。"""
    ...

  def setTimeout(self, sec: float) -> None:
    """收发超时（秒）。"""
    ...

  def setBlocking(self, blocking: bool) -> None:
    """切换阻塞 / 非阻塞模式。"""
    ...

  def connectEx(self, host: str, port: int) -> int:
    """非阻塞 connect；成功返回 ``SocketOk``，进行中返回 ``SocketWouldBlock``。"""
    ...

  def finishConnect(self) -> None:
    """等待写就绪后检查非阻塞 connect 的最终结果。"""
    ...

  def acceptNonblocking(self) -> Self:
    """非阻塞 accept；无连接时返回 closed socket。"""
    ...

  def sendRangeNonblocking(self, buf: byte[:], start: int, end: int) -> int:
    """非阻塞发送 ``buf[start:end]``，would-block 返回 ``SocketWouldBlock``。"""
    ...

  def recvNonblocking(self, buf: byte[:], cap: int) -> int:
    """非阻塞接收，would-block 返回 ``SocketWouldBlock``，``0`` 表示 EOF。"""
    ...

  @immutable
  def fileno(self) -> int64:
    """底层 socket/fd 句柄。"""
    ...

  @staticmethod
  @immutable
  def wouldBlock(code: int) -> bool:
    """``connectEx`` / 非阻塞收发返回码是否表示暂不可完成。"""
    ...


@copyable
class AsyncTcpSocket:
  """协作式异步 TCP socket；基于真实 non-blocking socket + ``Task`` IO readiness。"""

  _sock: TcpSocket = new()

  def __init__(self):
    self._sock = new()

  @staticmethod
  def fromSocket(sock: TcpSocket) -> Self:
    out: Self = new()
    out._sock = sock
    out._sock.setBlocking(False)
    return out

  @immutable
  def isClosed(self) -> bool:
    return self._sock.isClosed()

  @immutable
  def fileno(self) -> int64:
    return self._sock.fileno()

  def close(self) -> None:
    self._sock.close()

  def bind(self, host: str, port: int) -> None:
    self._sock.bind(host, port)
    self._sock.setBlocking(False)

  def listen(self, backlog: int = 128) -> None:
    self._sock.listen(backlog)

  async def connect(self, host: str, port: int) -> None:
    self._sock.setBlocking(False)
    code: int = self._sock.connectEx(host, port)
    if code == SocketWouldBlock:
      await Task.waitWrite(self._sock.fileno())
      self._sock.finishConnect()
      return
    if code != SocketOk:
      raise OSError()

  async def accept(self) -> Self:
    while True:
      conn: TcpSocket = self._sock.acceptNonblocking()
      if not conn.isClosed():
        return new.fromSocket(conn)
      await Task.waitRead(self._sock.fileno())

  async def recv(self, buf: byte[:], cap: int) -> int:
    while True:
      got: int = self._sock.recvNonblocking(buf, cap)
      if got != SocketWouldBlock:
        return got
      await Task.waitRead(self._sock.fileno())

  async def sendAll(self, data: bytes) -> None:
    n: int = len(data)
    if n <= 0:
      return
    buf: byte[:] = new(n)
    for i in range(n):
      buf[i] = data[i]
    sentTotal: int = 0
    while sentTotal < n:
      sent: int = self._sock.sendRangeNonblocking(buf, sentTotal, n)
      if sent == SocketWouldBlock:
        await Task.waitWrite(self._sock.fileno())
      else:
        if sent <= 0:
          raise OSError()
        sentTotal += sent
