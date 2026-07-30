"""同步 HTTP 客户端（``ClientSession``）。"""
from ..builtins import *
from .url import UrlData, _HEADER_END, parse_ascii_int
from .http import (
  AsyncClientStreamResponse,
  ClientResponse,
  ClientStreamResponse,
  RequestOptions,
  _header_key,
  _header_lines,
  _header_value,
)
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

  def request_options(self, method: str, url: str, options: RequestOptions) -> ClientResponse:
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

  def stream_options(self, method: str, url: str, options: RequestOptions) -> ClientStreamResponse:
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
    return new.from_streams(reader, writer)


@copyable
class AsyncClientSession:
  """短连接异步 HTTP/1.1 客户端；基于 non-blocking ``AsyncTcpSocket``。"""

  async def __aenter__(self) -> Self:
    return self

  async def __aexit__(self):
    return None

  async def request_options(self, method: str, url: str, options: RequestOptions) -> ClientResponse:
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

  async def stream_options(self, method: str, url: str, options: RequestOptions) -> AsyncClientStreamResponse:
    pu = UrlData.parse(url)
    sock: AsyncTcpSocket = new()
    await sock.connect(pu.host, pu.port)
    writer: AsyncStreamWriter = new.from_socket(sock)
    reader: AsyncStreamReader = new.from_socket(sock)
    payload: bytes = options.encode(method, pu)
    wrote: int = await writer.write(payload)
    await writer.drain()
    block: bytes = await reader.readuntil(_HEADER_END)
    lines: list[bytes] = _header_lines(block)
    head: ClientResponse = new()
    if lines:
      first: bytes = lines[0]
      sp1: int = first.find(b" ")
      sp2: int = first.find(b" ", sp1 + 1)
      status_part: bytes = first[sp1 + 1 : sp2]
      head.status = parse_ascii_int(status_part.decode())
      for i in range(1, len(lines)):
        line: bytes = lines[i]
        if not line:
          break
        key: str = _header_key(line)
        val: str = _header_value(line)
        if key:
          head.headers[key] = val
    return AsyncClientStreamResponse.from_head(reader, writer, head)

  async def request(self, method: str, url: str, **options: RequestOptions) -> ClientResponse:
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

  async def get(self, url: str, **options: RequestOptions) -> ClientResponse:
    return await self.request("GET", url, **options)

  async def post(self, url: str, **options: RequestOptions) -> ClientResponse:
    return await self.request("POST", url, **options)
