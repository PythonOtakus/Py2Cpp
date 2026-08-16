"""同步 HTTP 服务器（``Server`` / ``ServerMixin``）。"""
from ..builtins import *
from .http import Request, Response, StatusCodeEnum
from .socket import AsyncTcpSocket, TcpSocket
from .stream import AsyncStreamReader, AsyncStreamWriter, StreamReader, StreamWriter


@annotation
@dataclass
class RouteGetMeta:
  """``GET`` 路由；``@RouteGetMeta("/path")``；``Self.getMethodAnnotation[RouteGetMeta](method).path``。"""

  path: str = ""


@annotation
@dataclass
class RoutePostMeta:
  """``POST`` 路由；``@RoutePostMeta("/path")``。"""

  path: str = ""


@copyable
class Server:
  """HTTP 服务器：单连接读请求、写响应；无路由时返回 404。"""

  def handleStreams(self, reader: StreamReader @ref, writer: StreamWriter @ref) -> None:
    req: Request = new.read(reader)
    resp: Response = new.textResponse("Not Found", StatusCodeEnum.NotFound)
    resp.write(writer)

  def handleConnection(self, sock: TcpSocket) -> None:
    reader: StreamReader = new.fromSocket(sock)
    writer: StreamWriter = new.fromSocket(sock)
    self.handleStreams(reader, writer)
    reader.close()
    writer.close()

  def run(self, host: str, port: int) -> None:
    """阻塞式服务循环：``accept`` → 处理单请求 → 关闭。"""
    listener: TcpSocket = new()
    listener.bind(host, port)
    listener.listen(128)
    while True:
      conn: TcpSocket = listener.accept()
      self.handleConnection(conn)


@mixin
class ServerMixin(Server):
  """带 ``@RouteGetMeta`` / ``@RoutePostMeta`` 的 HTTP 服务器；宿主 ``class App(ServerMixin): …``。"""

  def _matchRouteGet(self, req: Request) -> Response:
    resp: Response = new.textResponse("Not Found", StatusCodeEnum.NotFound)
    for method in Self.iterMethods[RouteGetMeta]():
      label: str = method
      routeMeta = Self.getMethodAnnotation[RouteGetMeta](method)
      if req.method == "GET":
        if req.path == label:
          resp = getattr(self, method)(req)
    return resp

  def _matchRoutePost(self, req: Request) -> Response:
    resp: Response = new.textResponse("Not Found", StatusCodeEnum.NotFound)
    for method in Self.iterMethods[RoutePostMeta]():
      label: str = method
      routeMeta = Self.getMethodAnnotation[RoutePostMeta](method)
      if req.method == "POST":
        if req.path == label:
          resp = getattr(self, method)(req)
    return resp

  def handleStreams(self, reader: StreamReader @ref, writer: StreamWriter @ref) -> None:
    req: Request = new.read(reader)
    resp: Response = self._matchRouteGet(req)
    if resp.status == int(StatusCodeEnum.NotFound):
      resp = self._matchRoutePost(req)
    resp.write(writer)


@copyable
class AsyncServer:
  """异步 HTTP 服务器：non-blocking accept/read/write，单连接单请求。"""

  _stopped: bool = False

  def stop(self) -> None:
    self._stopped = True

  async def handleStreamsAsync(
    self,
    reader: AsyncStreamReader @ref,
    writer: AsyncStreamWriter @ref,
  ) -> None:
    req: Request = await new.readAsync(reader)
    resp: Response = new.textResponse("Not Found", StatusCodeEnum.NotFound)
    await resp.writeAsync(writer)

  async def handleConnectionAsync(self, sock: AsyncTcpSocket) -> None:
    reader: AsyncStreamReader = new.fromSocket(sock)
    writer: AsyncStreamWriter = new.fromSocket(sock)
    await self.handleStreamsAsync(reader, writer)
    reader.close()
    writer.close()

  async def serveN(self, host: str, port: int, count: int) -> None:
    """接受并处理 ``count`` 个连接后返回，便于测试和嵌入式驱动。"""
    listener: AsyncTcpSocket = new()
    listener.bind(host, port)
    listener.listen(128)
    handled: int = 0
    while handled < count and not self._stopped:
      conn: AsyncTcpSocket = await listener.accept()
      await self.handleConnectionAsync(conn)
      handled += 1
    listener.close()

  async def serveForever(self, host: str, port: int) -> None:
    """异步服务循环：``accept`` → 处理单请求 → 关闭。"""
    listener: AsyncTcpSocket = new()
    listener.bind(host, port)
    listener.listen(128)
    while not self._stopped:
      conn: AsyncTcpSocket = await listener.accept()
      await self.handleConnectionAsync(conn)
    listener.close()


@mixin
class AsyncServerMixin(AsyncServer):
  """带 ``@RouteGetMeta`` / ``@RoutePostMeta`` 的异步 HTTP 服务器。"""

  def _matchRouteGet(self, req: Request) -> Response:
    resp: Response = new.textResponse("Not Found", StatusCodeEnum.NotFound)
    for method in Self.iterMethods[RouteGetMeta]():
      label: str = method
      routeMeta = Self.getMethodAnnotation[RouteGetMeta](method)
      if req.method == "GET":
        if req.path == label:
          resp = getattr(self, method)(req)
    return resp

  def _matchRoutePost(self, req: Request) -> Response:
    resp: Response = new.textResponse("Not Found", StatusCodeEnum.NotFound)
    for method in Self.iterMethods[RoutePostMeta]():
      label: str = method
      routeMeta = Self.getMethodAnnotation[RoutePostMeta](method)
      if req.method == "POST":
        if req.path == label:
          resp = getattr(self, method)(req)
    return resp

  async def handleStreamsAsync(
    self,
    reader: AsyncStreamReader @ref,
    writer: AsyncStreamWriter @ref,
  ) -> None:
    req: Request = await new.readAsync(reader)
    resp: Response = self._matchRouteGet(req)
    if resp.status == int(StatusCodeEnum.NotFound):
      resp = self._matchRoutePost(req)
    await resp.writeAsync(writer)

  async def handleConnectionAsync(self, sock: AsyncTcpSocket) -> None:
    reader: AsyncStreamReader = new.fromSocket(sock)
    writer: AsyncStreamWriter = new.fromSocket(sock)
    await self.handleStreamsAsync(reader, writer)
    reader.close()
    writer.close()

  async def serveN(self, host: str, port: int, count: int) -> None:
    """接受并处理 ``count`` 个连接后返回，保持 mixin 宿主 ``Self`` 上下文。"""
    listener: AsyncTcpSocket = new()
    listener.bind(host, port)
    listener.listen(128)
    handled: int = 0
    while handled < count and not self._stopped:
      conn: AsyncTcpSocket = await listener.accept()
      await self.handleConnectionAsync(conn)
      handled += 1
    listener.close()

  async def serveForever(self, host: str, port: int) -> None:
    """异步服务循环：``accept`` → 处理单请求 → 关闭，保持 mixin 宿主 ``Self`` 上下文。"""
    listener: AsyncTcpSocket = new()
    listener.bind(host, port)
    listener.listen(128)
    while not self._stopped:
      conn: AsyncTcpSocket = await listener.accept()
      await self.handleConnectionAsync(conn)
    listener.close()
