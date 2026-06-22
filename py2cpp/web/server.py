"""同步 HTTP 服务器（``Server`` / ``ServerMixin``）。"""
from ..builtins import *
from .http import Request, Response, StatusCode
from .socket import TcpSocket
from .stream import StreamReader, StreamWriter


@annotation
@dataclass
class RouteGetMeta:
  """``GET`` 路由；``@RouteGetMeta("/path")``；``Self.get_method_annotation[RouteGetMeta](method).path``。"""

  path: str = ""


@annotation
@dataclass
class RoutePostMeta:
  """``POST`` 路由；``@RoutePostMeta("/path")``。"""

  path: str = ""


@copyable
class Server:
  """HTTP 服务器：单连接读请求、写响应；无路由时返回 404。"""

  def handle_streams(self, reader: StreamReader @ref, writer: StreamWriter @ref) -> None:
    req: Request = new.read(reader)
    resp: Response = new.text_response("Not Found", StatusCode.NOT_FOUND)
    resp.write(writer)

  def handle_connection(self, sock: TcpSocket) -> None:
    reader: StreamReader = new.from_socket(sock)
    writer: StreamWriter = new.from_socket(sock)
    self.handle_streams(reader, writer)
    reader.close()
    writer.close()

  def run(self, host: str, port: int) -> None:
    """阻塞式服务循环：``accept`` → 处理单请求 → 关闭。"""
    listener: TcpSocket = new()
    listener.bind(host, port)
    listener.listen(128)
    while True:
      conn: TcpSocket = listener.accept()
      self.handle_connection(conn)


@mixin
class ServerMixin(Server):
  """带 ``@RouteGetMeta`` / ``@RoutePostMeta`` 的 HTTP 服务器；宿主 ``class App(ServerMixin): …``。"""

  def _match_route_get(self, req: Request) -> Response:
    resp: Response = new.text_response("Not Found", StatusCode.NOT_FOUND)
    for method in Self.iter_methods[RouteGetMeta]():
      label: str = method
      route_meta = Self.get_method_annotation[RouteGetMeta](method)
      if req.method == "GET":
        if req.path == label:
          resp = getattr(self, method)(req)
    return resp

  def _match_route_post(self, req: Request) -> Response:
    resp: Response = new.text_response("Not Found", StatusCode.NOT_FOUND)
    for method in Self.iter_methods[RoutePostMeta]():
      label: str = method
      route_meta = Self.get_method_annotation[RoutePostMeta](method)
      if req.method == "POST":
        if req.path == label:
          resp = getattr(self, method)(req)
    return resp

  def handle_streams(self, reader: StreamReader @ref, writer: StreamWriter @ref) -> None:
    req: Request = new.read(reader)
    resp: Response = self._match_route_get(req)
    if resp.status == int(StatusCode.NOT_FOUND):
      resp = self._match_route_post(req)
    resp.write(writer)
