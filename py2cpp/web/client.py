"""同步 HTTP 客户端（``ClientSession``）。"""
from ..builtins import *
from .url import UrlData
from .http import ClientResponse, RequestOptions
from .socket import TcpSocket
from .stream import StreamReader, StreamWriter


@copyable
class ClientSession:
  """短连接 HTTP/1.1 客户端（每次请求新建 TCP 连接）。"""

  def __enter__(self) -> Self:
    return self

  def __exit__(self):
    pass

  def get(self, url: str, **options: RequestOptions) -> ClientResponse:
    return self.request("GET", url, **options)

  def post(self, url: str, **options: RequestOptions) -> ClientResponse:
    return self.request("POST", url, **options)

  def request(self, method: str, url: str, **options: RequestOptions) -> ClientResponse:
    pu = UrlData.parse(url)
    sock: TcpSocket = new()
    if options.timeout > 0.0:
      sock.set_timeout(options.timeout)
    sock.connect(pu.host, pu.port)
    writer: StreamWriter = new.from_socket(sock)
    reader: StreamReader = new.from_socket(sock)
    payload: bytes = options.encode(method, pu)
    writer.write(payload)
    writer.drain()
    resp: ClientResponse = new.read(reader)
    reader.close()
    writer.close()
    return resp
