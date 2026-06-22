"""TCP 套接字（WinSock / BSD socket 叶子 ``@native``）。"""
from ..builtins import *
from ..core.exceptions import OSError


@native
@copyable
@native_name("Py*")
class TcpSocket:
  """IPv4 TCP 套接字。"""

  _sock: uint64
  _closed: bool

  def __init__(self): ...

  def __del__(self): ...

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
