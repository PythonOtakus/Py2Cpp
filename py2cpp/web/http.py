"""HTTP/1.1 报文解析与组包（纯 Python）。"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..serde.base64 import b64encode
from ..text.bytes import bytes
from .url import UrlData, _Crlf, _HeaderEnd, mergeQuery, parseAsciiInt
from .stream import AsyncStreamReader, AsyncStreamWriter, StreamReader, StreamWriter


@enum
class StatusCodeEnum:
  Continue = 100
  SwitchingProtocols = 101
  Processing = 102
  EarlyHints = 103
  Ok = 200
  Created = 201
  Accepted = 202
  NonAuthoritativeInformation = 203
  NoContent = 204
  ResetContent = 205
  PartialContent = 206
  MultiStatus = 207
  AlreadyReported = 208
  ImUsed = 226
  MultipleChoices = 300
  MovedPermanently = 301
  Found = 302
  SeeOther = 303
  NotModified = 304
  UseProxy = 305
  TemporaryRedirect = 307
  PermanentRedirect = 308
  BadRequest = 400
  Unauthorized = 401
  PaymentRequired = 402
  Forbidden = 403
  NotFound = 404
  MethodNotAllowed = 405
  NotAcceptable = 406
  ProxyAuthenticationRequired = 407
  RequestTimeout = 408
  Conflict = 409
  Gone = 410
  LengthRequired = 411
  PreconditionFailed = 412
  ContentTooLarge = 413
  UriTooLong = 414
  UnsupportedMediaType = 415
  RangeNotSatisfiable = 416
  ExpectationFailed = 417
  ImATeapot = 418
  MisdirectedRequest = 421
  UnprocessableContent = 422
  Locked = 423
  FailedDependency = 424
  TooEarly = 425
  UpgradeRequired = 426
  PreconditionRequired = 428
  TooManyRequests = 429
  RequestHeaderFieldsTooLarge = 431
  UnavailableForLegalReasons = 451
  InternalServerError = 500
  NotImplemented = 501
  BadGateway = 502
  ServiceUnavailable = 503
  GatewayTimeout = 504
  HttpVersionNotSupported = 505
  VariantAlsoNegotiates = 506
  InsufficientStorage = 507
  LoopDetected = 508
  NotExtended = 510
  NetworkAuthenticationRequired = 511


@immutable
def reasonPhrase(status: int) -> str:
  match status:
    case 100:
      return "Continue"
    case 101:
      return "Switching Protocols"
    case 102:
      return "Processing"
    case 103:
      return "Early Hints"
    case 200:
      return "Ok"
    case 201:
      return "Created"
    case 202:
      return "Accepted"
    case 203:
      return "Non-Authoritative Information"
    case 204:
      return "No Content"
    case 205:
      return "Reset Content"
    case 206:
      return "Partial Content"
    case 207:
      return "Multi-Status"
    case 208:
      return "Already Reported"
    case 226:
      return "IM Used"
    case 300:
      return "Multiple Choices"
    case 301:
      return "Moved Permanently"
    case 302:
      return "Found"
    case 303:
      return "See Other"
    case 304:
      return "Not Modified"
    case 305:
      return "Use Proxy"
    case 307:
      return "Temporary Redirect"
    case 308:
      return "Permanent Redirect"
    case 400:
      return "Bad Request"
    case 401:
      return "Unauthorized"
    case 402:
      return "Payment Required"
    case 403:
      return "Forbidden"
    case 404:
      return "Not Found"
    case 405:
      return "Method Not Allowed"
    case 406:
      return "Not Acceptable"
    case 407:
      return "Proxy Authentication Required"
    case 408:
      return "Request Timeout"
    case 409:
      return "Conflict"
    case 410:
      return "Gone"
    case 411:
      return "Length Required"
    case 412:
      return "Precondition Failed"
    case 413:
      return "Content Too Large"
    case 414:
      return "URI Too Long"
    case 415:
      return "Unsupported Media Type"
    case 416:
      return "Range Not Satisfiable"
    case 417:
      return "Expectation Failed"
    case 418:
      return "I'm a Teapot"
    case 421:
      return "Misdirected Request"
    case 422:
      return "Unprocessable Content"
    case 423:
      return "Locked"
    case 424:
      return "Failed Dependency"
    case 425:
      return "Too Early"
    case 426:
      return "Upgrade Required"
    case 428:
      return "Precondition Required"
    case 429:
      return "Too Many Requests"
    case 431:
      return "Request Header Fields Too Large"
    case 451:
      return "Unavailable For Legal Reasons"
    case 500:
      return "Internal Server Error"
    case 501:
      return "Not Implemented"
    case 502:
      return "Bad Gateway"
    case 503:
      return "Service Unavailable"
    case 504:
      return "Gateway Timeout"
    case 505:
      return "HTTP Version Not Supported"
    case 506:
      return "Variant Also Negotiates"
    case 507:
      return "Insufficient Storage"
    case 508:
      return "Loop Detected"
    case 510:
      return "Not Extended"
    case 511:
      return "Network Authentication Required"
    case _:
      return "Unknown"


@dataclass
class BasicAuth:
  """HTTP Basic 认证凭据（``requests`` 的 ``auth=(user, pass)`` 对应体）。"""

  user: str = ""
  password: str = ""


@immutable
def _cookieHeader(cookies: dict[str, str]) -> str:
  if not cookies:
    return ""
  out: str = ""
  for k in cookies:
    pair: str = f"{k}={cookies[k]}"
    if not out:
      out = pair
    else:
      out = f"{out}; {pair}"
  return out


@immutable
def _basicAuthHeader(auth: BasicAuth) -> str:
  if not auth.user:
    return ""
  cred: bytes = f"{auth.user}:{auth.password}".encode()
  token: str = b64encode(cred).decode()
  return f"Basic {token}"


@immutable
def parseAsciiHex(s: str) -> int:
  """解析 HTTP chunk-size 的十六进制前缀；遇到 ``;`` 扩展或空白停止。"""
  out: int = 0
  for i in range(len(s)):
    c: char = s[i]
    v: int = -1
    if int(c) >= ord("0") and int(c) <= ord("9"):
      v = int(c) - ord("0")
    elif int(c) >= ord("a") and int(c) <= ord("f"):
      v = int(c) - ord("a") + 10
    elif int(c) >= ord("A") and int(c) <= ord("F"):
      v = int(c) - ord("A") + 10
    else:
      return out
    out = out * 16 + v
  return out


@immutable
def _stripLineEnd(line: str) -> str:
  out: str = line
  if out.endsWith("\n"):
    out = out[:-1]
  if out.endsWith("\r"):
    out = out[:-1]
  return out


@immutable
def _headerIsChunked(headers: dict[str, str]) -> bool:
  val: str = ""
  if "Transfer-Encoding" in headers:
    val = headers["Transfer-Encoding"]
  elif "transfer-encoding" in headers:
    val = headers["transfer-encoding"]
  if not val:
    return False
  return "chunked" in val or "Chunked" in val or "CHUNKED" in val


@immutable
def _bytesFromBuf(buf: byte[:], n: int) -> bytes:
  out: byte[:] = new(n)
  for i in range(n):
    out[i] = buf[i]
  return bytes(out)


@immutable
def _appendOne(dst: byte[:] @ref, at: int, b: byte) -> int:
  need: int = at + 1
  n: int = len(dst)
  if need > n:
    dst.reshape(need, n)
  dst[at] = b
  return need


@copyable
class RequestOptions:
  """客户端出站请求选项（``headers`` / ``params`` / ``cookies`` / ``data`` / ``auth`` / ``timeout``）。"""

  headers: dict[str, str] = {}
  params: dict[str, str] = {}
  cookies: dict[str, str] = {}
  data: bytes = b""
  auth: BasicAuth = new()
  timeout: float = 0.0

  @immutable
  def _requestPath(self, url: UrlData) -> str:
    query: str = mergeQuery(url.query, self.params)
    if query:
      return f"{url.path}?{query}"
    return url.path

  def encode(self, method: str, url: UrlData) -> bytes:
    """组包 HTTP/1.1 请求字节（``ConnectionType: close``）。"""
    path: str = self._requestPath(url)
    body: bytes = self.data
    hdrs: dict[str, str] = {}
    for k in self.headers:
      hdrs[k] = self.headers[k]
    hdrs["Host"] = url.host
    if "ConnectionType" not in hdrs and "connection" not in hdrs:
      hdrs["ConnectionType"] = "close"
    cookieHdr: str = _cookieHeader(self.cookies)
    if cookieHdr:
      if "Cookie" not in hdrs and "cookie" not in hdrs:
        hdrs["Cookie"] = cookieHdr
    authHdr: str = _basicAuthHeader(self.auth)
    if authHdr:
      if "Authorization" not in hdrs and "authorization" not in hdrs:
        hdrs["Authorization"] = authHdr
    if body:
      if "Content-Length" not in hdrs and "content-length" not in hdrs:
        hdrs["Content-Length"] = f"{len(body)}"
    w: StreamWriter = new.fromBuffer()
    reqLine: str = f"{method} {path} HTTP/1.1\r\n"
    w.write(reqLine.encode())
    for k in _headerKeys(hdrs):
      line: str = f"{k}: {hdrs[k]}\r\n"
      w.write(line.encode())
    w.write(_Crlf)
    if body:
      w.write(body)
    return w.takeBytes()


@dataclass(eq=False, repr=False)
class Request:
  """入站 HTTP 请求。"""

  method: str = ""
  path: str = ""
  version: str = ""
  headers: dict[str, str] @optional = {}
  body: bytes @optional = b""

  @staticmethod
  def read(reader: StreamReader @ref) -> Self:
    """自流读取完整 HTTP 请求。"""
    block: bytes = reader.readUntil(_HeaderEnd)
    lines: list[bytes] = _headerLines(block)
    if not lines:
      raise ValueError("empty request")
    req: Self = new()
    first: bytes = lines[0]
    sp1: int = first.find(b" ")
    if sp1 < 0:
      raise ValueError("bad request line")
    sp2: int = first.find(b" ", sp1 + 1)
    if sp2 < 0:
      raise ValueError("bad request line")
    req.method = first[:sp1].decode()
    req.path = first[sp1 + 1 : sp2].decode()
    req.version = first[sp2 + 1 :].decode()
    for i in range(1, len(lines)):
      line: bytes = lines[i]
      if not line:
        break
      key: str = _headerKey(line)
      val: str = _headerValue(line)
      if key:
        req.headers[key] = val
    clen: int = 0
    if "Content-Length" in req.headers:
      clen = parseAsciiInt(req.headers["Content-Length"])
    elif "content-length" in req.headers:
      clen = parseAsciiInt(req.headers["content-length"])
    if clen > 0:
      req.body = reader.readExactly(clen)
    return req

  @staticmethod
  async def readAsync(reader: AsyncStreamReader @ref) -> Self:
    """异步自流读取完整 HTTP 请求。"""
    block: bytes = await reader.readUntil(_HeaderEnd)
    lines: list[bytes] = _headerLines(block)
    if not lines:
      raise ValueError("empty request")
    req: Self = new()
    first: bytes = lines[0]
    sp1: int = first.find(b" ")
    if sp1 < 0:
      raise ValueError("bad request line")
    sp2: int = first.find(b" ", sp1 + 1)
    if sp2 < 0:
      raise ValueError("bad request line")
    req.method = first[:sp1].decode()
    req.path = first[sp1 + 1 : sp2].decode()
    req.version = first[sp2 + 1 :].decode()
    for i in range(1, len(lines)):
      line: bytes = lines[i]
      if not line:
        break
      key: str = _headerKey(line)
      val: str = _headerValue(line)
      if key:
        req.headers[key] = val
    clen: int = 0
    if "Content-Length" in req.headers:
      clen = parseAsciiInt(req.headers["Content-Length"])
    elif "content-length" in req.headers:
      clen = parseAsciiInt(req.headers["content-length"])
    if clen > 0:
      req.body = await reader.readExactly(clen)
    return req

  @immutable
  def text(self) -> str:
    return self.body.decode()

  @immutable
  def host(self) -> str:
    if "Host" in self.headers:
      return self.headers["Host"]
    if "host" in self.headers:
      return self.headers["host"]
    return ""


@dataclass(eq=False, repr=False)
class Response:
  """出站 HTTP 响应。"""

  status: int = 0
  headers: dict[str, str] @optional = {}
  body: bytes @optional = b""

  @staticmethod
  def textResponse(text: str, status: StatusCodeEnum) -> Self:
    out: Self = new()
    out.status = int(status)
    out.headers = {}
    out.body = text.encode()
    out.headers["Content-Type"] = "text/plain; charset=utf-8"
    out.headers["Content-Length"] = f"{len(out.body)}"
    return out

  def write(self, writer: StreamWriter @ref) -> None:
    """写出 HTTP 响应（``ConnectionType: close``）。"""
    if "Content-Length" not in self.headers and "content-length" not in self.headers:
      self.headers["Content-Length"] = f"{len(self.body)}"
    if "ConnectionType" not in self.headers and "connection" not in self.headers:
      self.headers["ConnectionType"] = "close"
    statusLine: str = f"HTTP/1.1 {self.status} {reasonPhrase(self.status)}\r\n"
    writer.write(statusLine.encode())
    for k in _headerKeys(self.headers):
      hdr: str = f"{k}: {self.headers[k]}\r\n"
      writer.write(hdr.encode())
    writer.write(_Crlf)
    if self.body:
      writer.write(self.body)
    writer.drain()

  async def writeAsync(self, writer: AsyncStreamWriter @ref) -> None:
    """异步写出 HTTP 响应（``ConnectionType: close``）。"""
    if "Content-Length" not in self.headers and "content-length" not in self.headers:
      self.headers["Content-Length"] = f"{len(self.body)}"
    if "ConnectionType" not in self.headers and "connection" not in self.headers:
      self.headers["ConnectionType"] = "close"
    statusLine: str = f"HTTP/1.1 {self.status} {reasonPhrase(self.status)}\r\n"
    wrote: int = await writer.write(statusLine.encode())
    for k in _headerKeys(self.headers):
      hdr: str = f"{k}: {self.headers[k]}\r\n"
      wrote = await writer.write(hdr.encode())
    wrote = await writer.write(_Crlf)
    if self.body:
      wrote = await writer.write(self.body)
    await writer.drain()


@dataclass(eq=False, repr=False)
class ClientResponse:
  """客户端收到的 HTTP 响应。"""

  status: int = 0
  headers: dict[str, str] @optional = {}
  body: bytes @optional = b""

  @staticmethod
  def readHead(reader: StreamReader @ref) -> Self:
    block: bytes = reader.readUntil(_HeaderEnd)
    lines: list[bytes] = _headerLines(block)
    if not lines:
      raise ValueError("empty response")
    resp: Self = new()
    first: bytes = lines[0]
    sp1: int = first.find(b" ")
    if sp1 < 0:
      raise ValueError("bad status line")
    sp2: int = first.find(b" ", sp1 + 1)
    if sp2 < 0:
      raise ValueError("bad status line")
    statusPart: bytes = first[sp1 + 1 : sp2]
    resp.status = parseAsciiInt(statusPart.decode())
    for i in range(1, len(lines)):
      line: bytes = lines[i]
      if not line:
        break
      key: str = _headerKey(line)
      val: str = _headerValue(line)
      if key:
        resp.headers[key] = val
    return resp

  @staticmethod
  def read(reader: StreamReader @ref) -> Self:
    resp: Self = new.readHead(reader)
    clen: int = 0
    if "Content-Length" in resp.headers:
      clen = parseAsciiInt(resp.headers["Content-Length"])
    elif "content-length" in resp.headers:
      clen = parseAsciiInt(resp.headers["content-length"])
    if clen > 0:
      resp.body = reader.readExactly(clen)
    return resp

  @staticmethod
  async def readHeadAsync(reader: AsyncStreamReader @ref) -> Self:
    block: bytes = await reader.readUntil(_HeaderEnd)
    lines: list[bytes] = _headerLines(block)
    if not lines:
      raise ValueError("empty response")
    resp: Self = new()
    first: bytes = lines[0]
    sp1: int = first.find(b" ")
    if sp1 < 0:
      raise ValueError("bad status line")
    sp2: int = first.find(b" ", sp1 + 1)
    if sp2 < 0:
      raise ValueError("bad status line")
    statusPart: bytes = first[sp1 + 1 : sp2]
    resp.status = parseAsciiInt(statusPart.decode())
    for i in range(1, len(lines)):
      line: bytes = lines[i]
      if not line:
        break
      key: str = _headerKey(line)
      val: str = _headerValue(line)
      if key:
        resp.headers[key] = val
    return resp

  @staticmethod
  async def readAsync(reader: AsyncStreamReader @ref) -> Self:
    block: bytes = await reader.readUntil(_HeaderEnd)
    lines: list[bytes] = _headerLines(block)
    if not lines:
      raise ValueError("empty response")
    resp: Self = new()
    first: bytes = lines[0]
    sp1: int = first.find(b" ")
    if sp1 < 0:
      raise ValueError("bad status line")
    sp2: int = first.find(b" ", sp1 + 1)
    if sp2 < 0:
      raise ValueError("bad status line")
    statusPart: bytes = first[sp1 + 1 : sp2]
    resp.status = parseAsciiInt(statusPart.decode())
    for i in range(1, len(lines)):
      line: bytes = lines[i]
      if not line:
        break
      key: str = _headerKey(line)
      val: str = _headerValue(line)
      if key:
        resp.headers[key] = val
    clen: int = 0
    if "Content-Length" in resp.headers:
      clen = parseAsciiInt(resp.headers["Content-Length"])
    elif "content-length" in resp.headers:
      clen = parseAsciiInt(resp.headers["content-length"])
    if clen > 0:
      resp.body = await reader.readExactly(clen)
    return resp

  @immutable
  def text(self) -> str:
    return self.body.decode()


@refcount
class _ClientStreamResponseState(
  friends=(ClientStreamResponse,),
):
  """``ClientStreamResponse`` 共享状态；返回/复制响应对象时不复制底层流。"""

  status: int = 0
  headers: dict[str, str] = {}
  _reader: StreamReader = new()
  _chunked: bool = False
  _closed: bool = False
  _done: bool = False
  _chunk: bytes = b""
  _chunkPos: int = 0

  def __init__(self):
    self.status = 0
    self.headers = {}
    self._reader = StreamReader()
    self._chunked = False
    self._closed = False
    self._done = False
    self._chunk = b""
    self._chunkPos = 0


@copyable
class ClientStreamResponse:
  """客户端流式 HTTP 响应；响应头已读，body 保持从 socket 增量读取。"""

  _state: _ClientStreamResponseState = new()

  def __init__(self):
    self._state = new()

  @property
  def status(self) -> int:
    return self._state.status

  @property
  def headers(self) -> dict[str, str]:
    return self._state.headers

  @staticmethod
  def fromStreams(reader: StreamReader @ref, writer: StreamWriter @ref) -> Self:
    head: ClientResponse = new.readHead(reader)
    return new.fromHead(reader, writer, head)

  @staticmethod
  def fromHead(reader: StreamReader @ref, writer: StreamWriter @ref, head: ClientResponse) -> Self:
    out: Self = new()
    out._state.status = head.status
    out._state.headers = head.headers
    out._state._reader = reader
    out._state._chunked = _headerIsChunked(out._state.headers)
    return out

  def close(self) -> None:
    if self._state._closed:
      return
    self._state._closed = True
    self._state._reader.close()

  def _readNextChunk(self) -> bool:
    if self._state._done:
      return False
    lineB: bytes = self._state._reader.readUntil(_Crlf)
    line: str = _stripLineEnd(lineB.decode())
    size: int = parseAsciiHex(line)
    if size <= 0:
      self._state._done = True
      trailer: bytes = self._state._reader.readUntil(_Crlf)
      return False
    self._state._chunk = self._state._reader.readExactly(size)
    self._state._chunkPos = 0
    crlf: bytes = self._state._reader.readExactly(2)
    return True

  def _readChunkedLine(self) -> str:
    buf: byte[:] = b""
    at: int = 0
    while True:
      while self._state._chunkPos >= len(self._state._chunk):
        if not self._readNextChunk():
          return _bytesFromBuf(buf, at).decode()
      b: byte = self._state._chunk[self._state._chunkPos]
      self._state._chunkPos += 1
      if b == ord("\n"):
        return _bytesFromBuf(buf, at).decode()
      if b != ord("\r"):
        at = _appendOne(buf, at, b)

  def readLine(self) -> str:
    """读取 body 中下一行（不含行尾）；chunked 响应会先解码 chunk。"""
    if self._state._chunked:
      return self._readChunkedLine()
    lineB: bytes = self._state._reader.readUntil(b"\n")
    return _stripLineEnd(lineB.decode())

  def body(self) -> bytes:
    """读取当前已缓冲的剩余 body。

    HTTPS/WinHTTP 路径会先把 TLS body 完整读入内存；这里主要用于非 2xx
    响应的错误摘要。普通 socket 流式响应若还未缓冲 body，则返回空。
    """
    n: int = self._state._reader.available()
    if n <= 0:
      return b""
    return self._state._reader.readExactly(n)

  def text(self) -> str:
    return self.body().decode()


@copyable
class AsyncClientStreamResponse:
  """异步客户端流式 HTTP 响应；响应头已读，body 保持 non-blocking 增量读取。"""

  status: int = 0
  headers: dict[str, str] = {}
  _reader: AsyncStreamReader = new()
  _writer: AsyncStreamWriter = new()
  _chunked: bool = False
  _closed: bool = False
  _done: bool = False
  _chunk: bytes = b""
  _chunkPos: int = 0

  def __init__(self):
    self.status = 0
    self.headers = {}
    self._reader = new()
    self._writer = new()
    self._chunked = False
    self._closed = False
    self._done = False
    self._chunk = b""
    self._chunkPos = 0

  @staticmethod
  async def fromStreams(reader: AsyncStreamReader @ref, writer: AsyncStreamWriter @ref) -> Self:
    head: ClientResponse = await new.readHeadAsync(reader)
    return new.fromHead(reader, writer, head)

  @staticmethod
  def fromHead(reader: AsyncStreamReader @ref, writer: AsyncStreamWriter @ref, head: ClientResponse) -> Self:
    out: Self = new()
    out.status = head.status
    out.headers = head.headers
    out._reader = reader
    out._writer = writer
    out._chunked = _headerIsChunked(out.headers)
    return out

  def close(self) -> None:
    if self._closed:
      return
    self._closed = True
    self._reader.close()
    self._writer.close()

  async def _readNextChunk(self) -> bool:
    if self._done:
      return False
    lineB: bytes = await self._reader.readUntil(_Crlf)
    line: str = _stripLineEnd(lineB.decode())
    size: int = parseAsciiHex(line)
    if size <= 0:
      self._done = True
      trailer: bytes = await self._reader.readUntil(_Crlf)
      return False
    self._chunk = await self._reader.readExactly(size)
    self._chunkPos = 0
    crlf: bytes = await self._reader.readExactly(2)
    return True

  async def _readChunkedLine(self) -> str:
    buf: byte[:] = b""
    at: int = 0
    while True:
      while self._chunkPos >= len(self._chunk):
        more: bool = await self._readNextChunk()
        if not more:
          return _bytesFromBuf(buf, at).decode()
      b: byte = self._chunk[self._chunkPos]
      self._chunkPos += 1
      if b == ord("\n"):
        return _bytesFromBuf(buf, at).decode()
      if b != ord("\r"):
        at = _appendOne(buf, at, b)

  async def readLine(self) -> str:
    """异步读取 body 中下一行（不含行尾）；chunked 响应会先解码 chunk。"""
    if self._chunked:
      return await self._readChunkedLine()
    lineB: bytes = await self._reader.readUntil(b"\n")
    return _stripLineEnd(lineB.decode())


@immutable
def _headerKeys(headers: dict[str, str]) -> list[str]:
  out: list[str] = []
  for k in headers:
    out.append(k)
  return out


@immutable
def _headerKey(line: bytes) -> str:
  colon: int = line.find(b":")
  if colon < 0:
    return ""
  keyPart: bytes = line[:colon]
  return keyPart.decode()


@immutable
def _headerValue(line: bytes) -> str:
  colon: int = line.find(b":")
  if colon < 0:
    return ""
  val: bytes = line[colon + 1:]
  while val:
    if val[0] != ord(" "):
      break
    val = val[1:]
  return val.decode()


@immutable
def _headerLines(block: bytes) -> list[bytes]:
  """``block``（含末尾 ``\\r\\n\\r\\n``）→ 各行 ``bytes``（不含行尾）。"""
  out: list[bytes] = []
  n: int = len(block)
  buf: byte[:] = new(n)
  for bi in range(n):
    buf[bi] = block[bi]
  start: int = 0
  i: int = 0
  while i < n:
    if i + 1 < n and buf[i] == ord("\r") and buf[i + 1] == ord("\n"):
      ln: int = i - start
      lineBuf: byte[:] = new(ln)
      for j in range(ln):
        lineBuf[j] = buf[start + j]
      line: bytes = bytes(lineBuf)
      if not line:
        break
      out.append(line)
      i += 2
      start = i
      continue
    i += 1
  return out
