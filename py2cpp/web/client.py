"""同步 HTTP 客户端（``ClientSession``）。"""
from ..builtins import *
from .url import UrlData, _HeaderEnd, parseAsciiInt
from .http import (
  AsyncClientStreamResponse,
  ClientResponse,
  ClientStreamResponse,
  RequestOptions,
  _headerKey,
  _headerLines,
  _headerValue,
)
from .socket import AsyncTcpSocket, TcpSocket
from .stream import AsyncStreamReader, AsyncStreamWriter, StreamReader, StreamWriter


@native
def _httpsRequest(method: str, url: UrlData, payload: bytes, timeout: float) -> ClientResponse: ...


@native
def _httpsStream(method: str, url: UrlData, payload: bytes, timeout: float) -> ClientStreamResponse: ...


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
    payload: bytes = options.encode(method, pu)
    if pu.scheme == "https":
      return _httpsRequest(method, pu, payload, options.timeout)
    sock: TcpSocket = new()
    if options.timeout > 0.0:
      sock.setTimeout(options.timeout)
    sock.connect(pu.host, pu.port)
    writer: StreamWriter = new.fromSocket(sock)
    reader: StreamReader = new.fromSocket(sock)
    writer.write(payload)
    writer.drain()
    resp: ClientResponse = new.read(reader)
    reader.close()
    writer.close()
    return resp

  def requestOptions(self, method: str, url: str, options: RequestOptions) -> ClientResponse:
    pu = UrlData.parse(url)
    payload: bytes = options.encode(method, pu)
    if pu.scheme == "https":
      return _httpsRequest(method, pu, payload, options.timeout)
    sock: TcpSocket = new()
    if options.timeout > 0.0:
      sock.setTimeout(options.timeout)
    sock.connect(pu.host, pu.port)
    writer: StreamWriter = new.fromSocket(sock)
    reader: StreamReader = new.fromSocket(sock)
    writer.write(payload)
    writer.drain()
    resp: ClientResponse = new.read(reader)
    reader.close()
    writer.close()
    return resp

  def streamOptions(self, method: str, url: str, options: RequestOptions) -> ClientStreamResponse:
    pu = UrlData.parse(url)
    payload: bytes = options.encode(method, pu)
    if pu.scheme == "https":
      return _httpsStream(method, pu, payload, options.timeout)
    sock: TcpSocket = new()
    if options.timeout > 0.0:
      sock.setTimeout(options.timeout)
    sock.connect(pu.host, pu.port)
    writer: StreamWriter = new.fromSocket(sock)
    reader: StreamReader = new.fromSocket(sock)
    writer.write(payload)
    writer.drain()
    return new.fromStreams(reader, writer)


@copyable
class AsyncClientSession:
  """短连接异步 HTTP/1.1 客户端；基于 non-blocking ``AsyncTcpSocket``。"""

  async def __aenter__(self) -> Self:
    return self

  async def __aexit__(self):
    return None

  async def requestOptions(self, method: str, url: str, options: RequestOptions) -> ClientResponse:
    pu = UrlData.parse(url)
    payload: bytes = options.encode(method, pu)
    if pu.scheme == "https":
      return _httpsRequest(method, pu, payload, options.timeout)
    sock: AsyncTcpSocket = new()
    await sock.connect(pu.host, pu.port)
    writer: AsyncStreamWriter = new.fromSocket(sock)
    reader: AsyncStreamReader = new.fromSocket(sock)
    wrote: int = await writer.write(payload)
    await writer.drain()
    resp: ClientResponse = await new.readAsync(reader)
    reader.close()
    writer.close()
    return resp

  async def streamOptions(self, method: str, url: str, options: RequestOptions) -> AsyncClientStreamResponse:
    pu = UrlData.parse(url)
    sock: AsyncTcpSocket = new()
    await sock.connect(pu.host, pu.port)
    writer: AsyncStreamWriter = new.fromSocket(sock)
    reader: AsyncStreamReader = new.fromSocket(sock)
    payload: bytes = options.encode(method, pu)
    wrote: int = await writer.write(payload)
    await writer.drain()
    block: bytes = await reader.readUntil(_HeaderEnd)
    lines: list[bytes] = _headerLines(block)
    head: ClientResponse = new()
    if lines:
      first: bytes = lines[0]
      sp1: int = first.find(b" ")
      sp2: int = first.find(b" ", sp1 + 1)
      statusPart: bytes = first[sp1 + 1 : sp2]
      head.status = parseAsciiInt(statusPart.decode())
      for i in range(1, len(lines)):
        line: bytes = lines[i]
        if not line:
          break
        key: str = _headerKey(line)
        val: str = _headerValue(line)
        if key:
          head.headers[key] = val
    return AsyncClientStreamResponse.fromHead(reader, writer, head)

  async def request(self, method: str, url: str, **options: RequestOptions) -> ClientResponse:
    pu = UrlData.parse(url)
    payload: bytes = options.encode(method, pu)
    if pu.scheme == "https":
      return _httpsRequest(method, pu, payload, options.timeout)
    sock: AsyncTcpSocket = new()
    await sock.connect(pu.host, pu.port)
    writer: AsyncStreamWriter = new.fromSocket(sock)
    reader: AsyncStreamReader = new.fromSocket(sock)
    wrote: int = await writer.write(payload)
    await writer.drain()
    resp: ClientResponse = await new.readAsync(reader)
    reader.close()
    writer.close()
    return resp

  async def get(self, url: str, **options: RequestOptions) -> ClientResponse:
    return await self.request("GET", url, **options)

  async def post(self, url: str, **options: RequestOptions) -> ClientResponse:
    return await self.request("POST", url, **options)
