"""同步 HTTP 客户端（``ClientSession``）。"""
from ..builtins import *
from .url import UrlData
from .http import ClientResponse, RequestOptions
from .socket import AsyncTcpSocket, TcpSocket
from .stream import AsyncStreamReader, AsyncStreamWriter, StreamReader, StreamWriter


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


@copyable
class AsyncClientSession:
  """短连接异步 HTTP/1.1 客户端；基于 non-blocking ``AsyncTcpSocket``。"""

  async def __aenter__(self) -> Self:
    return self

  async def __aexit__(self):
    return None

  async def _request_impl(self, method: str, url: str, options: RequestOptions) -> ClientResponse:
    pu = UrlData.parse(url)
    sock: AsyncTcpSocket = new()
    await sock.connect(pu.host, pu.port)
    writer: AsyncStreamWriter = new.from_socket(sock)
    reader: AsyncStreamReader = new.from_socket(sock)
    payload: bytes = options.encode(method, pu)
    wrote: int = await writer.write(payload)
    await writer.drain()
    resp: ClientResponse = await new.read_async(reader)
    reader.close()
    writer.close()
    return resp

  async def request(self, method: str, url: str, **options: RequestOptions) -> ClientResponse:
    return await self._request_impl(method, url, options)

  async def get(self, url: str, **options: RequestOptions) -> ClientResponse:
    return await self._request_impl("GET", url, options)

  async def post(self, url: str, **options: RequestOptions) -> ClientResponse:
    return await self._request_impl("POST", url, options)
