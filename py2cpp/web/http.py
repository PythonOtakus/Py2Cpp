"""HTTP/1.1 报文解析与组包（纯 Python）。"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..serde.base64 import b64encode
from ..text.bytes import bytes
from .url import UrlData, _CRLF, _HEADER_END, merge_query, parse_ascii_int
from .stream import AsyncStreamReader, AsyncStreamWriter, StreamReader, StreamWriter


@enum
class StatusCode:
  CONTINUE = 100
  SWITCHING_PROTOCOLS = 101
  PROCESSING = 102
  EARLY_HINTS = 103
  OK = 200
  CREATED = 201
  ACCEPTED = 202
  NON_AUTHORITATIVE_INFORMATION = 203
  NO_CONTENT = 204
  RESET_CONTENT = 205
  PARTIAL_CONTENT = 206
  MULTI_STATUS = 207
  ALREADY_REPORTED = 208
  IM_USED = 226
  MULTIPLE_CHOICES = 300
  MOVED_PERMANENTLY = 301
  FOUND = 302
  SEE_OTHER = 303
  NOT_MODIFIED = 304
  USE_PROXY = 305
  TEMPORARY_REDIRECT = 307
  PERMANENT_REDIRECT = 308
  BAD_REQUEST = 400
  UNAUTHORIZED = 401
  PAYMENT_REQUIRED = 402
  FORBIDDEN = 403
  NOT_FOUND = 404
  METHOD_NOT_ALLOWED = 405
  NOT_ACCEPTABLE = 406
  PROXY_AUTHENTICATION_REQUIRED = 407
  REQUEST_TIMEOUT = 408
  CONFLICT = 409
  GONE = 410
  LENGTH_REQUIRED = 411
  PRECONDITION_FAILED = 412
  CONTENT_TOO_LARGE = 413
  URI_TOO_LONG = 414
  UNSUPPORTED_MEDIA_TYPE = 415
  RANGE_NOT_SATISFIABLE = 416
  EXPECTATION_FAILED = 417
  IM_A_TEAPOT = 418
  MISDIRECTED_REQUEST = 421
  UNPROCESSABLE_CONTENT = 422
  LOCKED = 423
  FAILED_DEPENDENCY = 424
  TOO_EARLY = 425
  UPGRADE_REQUIRED = 426
  PRECONDITION_REQUIRED = 428
  TOO_MANY_REQUESTS = 429
  REQUEST_HEADER_FIELDS_TOO_LARGE = 431
  UNAVAILABLE_FOR_LEGAL_REASONS = 451
  INTERNAL_SERVER_ERROR = 500
  NOT_IMPLEMENTED = 501
  BAD_GATEWAY = 502
  SERVICE_UNAVAILABLE = 503
  GATEWAY_TIMEOUT = 504
  HTTP_VERSION_NOT_SUPPORTED = 505
  VARIANT_ALSO_NEGOTIATES = 506
  INSUFFICIENT_STORAGE = 507
  LOOP_DETECTED = 508
  NOT_EXTENDED = 510
  NETWORK_AUTHENTICATION_REQUIRED = 511


@immutable
def reason_phrase(status: int) -> str:
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
      return "OK"
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
def _cookie_header(cookies: dict[str, str]) -> str:
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
def _basic_auth_header(auth: BasicAuth) -> str:
  if not auth.user:
    return ""
  cred: bytes = f"{auth.user}:{auth.password}".encode()
  token: str = b64encode(cred).decode()
  return f"Basic {token}"


@immutable
def parse_ascii_hex(s: str) -> int:
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
def _strip_line_end(line: str) -> str:
  out: str = line
  if out.endswith("\n"):
    out = out[:-1]
  if out.endswith("\r"):
    out = out[:-1]
  return out


@immutable
def _header_is_chunked(headers: dict[str, str]) -> bool:
  val: str = ""
  if "Transfer-Encoding" in headers:
    val = headers["Transfer-Encoding"]
  elif "transfer-encoding" in headers:
    val = headers["transfer-encoding"]
  if not val:
    return False
  return "chunked" in val or "Chunked" in val or "CHUNKED" in val


@immutable
def _bytes_from_buf(buf: byte[:], n: int) -> bytes:
  out: byte[:] = new(n)
  for i in range(n):
    out[i] = buf[i]
  return bytes(out)


@immutable
def _append_one(dst: byte[:] @ref, at: int, b: byte) -> int:
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
  def _request_path(self, url: UrlData) -> str:
    query: str = merge_query(url.query, self.params)
    if query:
      return f"{url.path}?{query}"
    return url.path

  def encode(self, method: str, url: UrlData) -> bytes:
    """组包 HTTP/1.1 请求字节（``Connection: close``）。"""
    path: str = self._request_path(url)
    body: bytes = self.data
    hdrs: dict[str, str] = {}
    for k in self.headers:
      hdrs[k] = self.headers[k]
    hdrs["Host"] = url.host
    if "Connection" not in hdrs and "connection" not in hdrs:
      hdrs["Connection"] = "close"
    cookie_hdr: str = _cookie_header(self.cookies)
    if cookie_hdr:
      if "Cookie" not in hdrs and "cookie" not in hdrs:
        hdrs["Cookie"] = cookie_hdr
    auth_hdr: str = _basic_auth_header(self.auth)
    if auth_hdr:
      if "Authorization" not in hdrs and "authorization" not in hdrs:
        hdrs["Authorization"] = auth_hdr
    if body:
      if "Content-Length" not in hdrs and "content-length" not in hdrs:
        hdrs["Content-Length"] = f"{len(body)}"
    w: StreamWriter = new.from_buffer()
    req_line: str = f"{method} {path} HTTP/1.1\r\n"
    w.write(req_line.encode())
    for k in _header_keys(hdrs):
      line: str = f"{k}: {hdrs[k]}\r\n"
      w.write(line.encode())
    w.write(_CRLF)
    if body:
      w.write(body)
    return w.take_bytes()


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
    block: bytes = reader.readuntil(_HEADER_END)
    lines: list[bytes] = _header_lines(block)
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
      key: str = _header_key(line)
      val: str = _header_value(line)
      if key:
        req.headers[key] = val
    clen: int = 0
    if "Content-Length" in req.headers:
      clen = parse_ascii_int(req.headers["Content-Length"])
    elif "content-length" in req.headers:
      clen = parse_ascii_int(req.headers["content-length"])
    if clen > 0:
      req.body = reader.readexactly(clen)
    return req

  @staticmethod
  async def read_async(reader: AsyncStreamReader @ref) -> Self:
    """异步自流读取完整 HTTP 请求。"""
    block: bytes = await reader.readuntil(_HEADER_END)
    lines: list[bytes] = _header_lines(block)
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
      key: str = _header_key(line)
      val: str = _header_value(line)
      if key:
        req.headers[key] = val
    clen: int = 0
    if "Content-Length" in req.headers:
      clen = parse_ascii_int(req.headers["Content-Length"])
    elif "content-length" in req.headers:
      clen = parse_ascii_int(req.headers["content-length"])
    if clen > 0:
      req.body = await reader.readexactly(clen)
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
  def text_response(text: str, status: StatusCode) -> Self:
    out: Self = new()
    out.status = int(status)
    out.headers = {}
    out.body = text.encode()
    out.headers["Content-Type"] = "text/plain; charset=utf-8"
    out.headers["Content-Length"] = f"{len(out.body)}"
    return out

  def write(self, writer: StreamWriter @ref) -> None:
    """写出 HTTP 响应（``Connection: close``）。"""
    if "Content-Length" not in self.headers and "content-length" not in self.headers:
      self.headers["Content-Length"] = f"{len(self.body)}"
    if "Connection" not in self.headers and "connection" not in self.headers:
      self.headers["Connection"] = "close"
    status_line: str = f"HTTP/1.1 {self.status} {reason_phrase(self.status)}\r\n"
    writer.write(status_line.encode())
    for k in _header_keys(self.headers):
      hdr: str = f"{k}: {self.headers[k]}\r\n"
      writer.write(hdr.encode())
    writer.write(_CRLF)
    if self.body:
      writer.write(self.body)
    writer.drain()

  async def write_async(self, writer: AsyncStreamWriter @ref) -> None:
    """异步写出 HTTP 响应（``Connection: close``）。"""
    if "Content-Length" not in self.headers and "content-length" not in self.headers:
      self.headers["Content-Length"] = f"{len(self.body)}"
    if "Connection" not in self.headers and "connection" not in self.headers:
      self.headers["Connection"] = "close"
    status_line: str = f"HTTP/1.1 {self.status} {reason_phrase(self.status)}\r\n"
    wrote: int = await writer.write(status_line.encode())
    for k in _header_keys(self.headers):
      hdr: str = f"{k}: {self.headers[k]}\r\n"
      wrote = await writer.write(hdr.encode())
    wrote = await writer.write(_CRLF)
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
  def read_head(reader: StreamReader @ref) -> Self:
    block: bytes = reader.readuntil(_HEADER_END)
    lines: list[bytes] = _header_lines(block)
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
    status_part: bytes = first[sp1 + 1 : sp2]
    resp.status = parse_ascii_int(status_part.decode())
    for i in range(1, len(lines)):
      line: bytes = lines[i]
      if not line:
        break
      key: str = _header_key(line)
      val: str = _header_value(line)
      if key:
        resp.headers[key] = val
    return resp

  @staticmethod
  def read(reader: StreamReader @ref) -> Self:
    resp: Self = new.read_head(reader)
    clen: int = 0
    if "Content-Length" in resp.headers:
      clen = parse_ascii_int(resp.headers["Content-Length"])
    elif "content-length" in resp.headers:
      clen = parse_ascii_int(resp.headers["content-length"])
    if clen > 0:
      resp.body = reader.readexactly(clen)
    return resp

  @staticmethod
  async def read_head_async(reader: AsyncStreamReader @ref) -> Self:
    block: bytes = await reader.readuntil(_HEADER_END)
    lines: list[bytes] = _header_lines(block)
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
    status_part: bytes = first[sp1 + 1 : sp2]
    resp.status = parse_ascii_int(status_part.decode())
    for i in range(1, len(lines)):
      line: bytes = lines[i]
      if not line:
        break
      key: str = _header_key(line)
      val: str = _header_value(line)
      if key:
        resp.headers[key] = val
    return resp

  @staticmethod
  async def read_async(reader: AsyncStreamReader @ref) -> Self:
    block: bytes = await reader.readuntil(_HEADER_END)
    lines: list[bytes] = _header_lines(block)
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
    status_part: bytes = first[sp1 + 1 : sp2]
    resp.status = parse_ascii_int(status_part.decode())
    for i in range(1, len(lines)):
      line: bytes = lines[i]
      if not line:
        break
      key: str = _header_key(line)
      val: str = _header_value(line)
      if key:
        resp.headers[key] = val
    clen: int = 0
    if "Content-Length" in resp.headers:
      clen = parse_ascii_int(resp.headers["Content-Length"])
    elif "content-length" in resp.headers:
      clen = parse_ascii_int(resp.headers["content-length"])
    if clen > 0:
      resp.body = await reader.readexactly(clen)
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
  _chunk_pos: int = 0

  def __init__(self):
    self.status = 0
    self.headers = {}
    self._reader = StreamReader()
    self._chunked = False
    self._closed = False
    self._done = False
    self._chunk = b""
    self._chunk_pos = 0


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
  def from_streams(reader: StreamReader @ref, writer: StreamWriter @ref) -> Self:
    head: ClientResponse = new.read_head(reader)
    return new.from_head(reader, writer, head)

  @staticmethod
  def from_head(reader: StreamReader @ref, writer: StreamWriter @ref, head: ClientResponse) -> Self:
    out: Self = new()
    out._state.status = head.status
    out._state.headers = head.headers
    out._state._reader = reader
    out._state._chunked = _header_is_chunked(out._state.headers)
    return out

  def close(self) -> None:
    if self._state._closed:
      return
    self._state._closed = True
    self._state._reader.close()

  def _read_next_chunk(self) -> bool:
    if self._state._done:
      return False
    line_b: bytes = self._state._reader.readuntil(_CRLF)
    line: str = _strip_line_end(line_b.decode())
    size: int = parse_ascii_hex(line)
    if size <= 0:
      self._state._done = True
      trailer: bytes = self._state._reader.readuntil(_CRLF)
      return False
    self._state._chunk = self._state._reader.readexactly(size)
    self._state._chunk_pos = 0
    crlf: bytes = self._state._reader.readexactly(2)
    return True

  def _read_chunked_line(self) -> str:
    buf: byte[:] = b""
    at: int = 0
    while True:
      while self._state._chunk_pos >= len(self._state._chunk):
        if not self._read_next_chunk():
          return _bytes_from_buf(buf, at).decode()
      b: byte = self._state._chunk[self._state._chunk_pos]
      self._state._chunk_pos += 1
      if b == ord("\n"):
        return _bytes_from_buf(buf, at).decode()
      if b != ord("\r"):
        at = _append_one(buf, at, b)

  def readline(self) -> str:
    """读取 body 中下一行（不含行尾）；chunked 响应会先解码 chunk。"""
    if self._state._chunked:
      return self._read_chunked_line()
    line_b: bytes = self._state._reader.readuntil(b"\n")
    return _strip_line_end(line_b.decode())


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
  _chunk_pos: int = 0

  def __init__(self):
    self.status = 0
    self.headers = {}
    self._reader = new()
    self._writer = new()
    self._chunked = False
    self._closed = False
    self._done = False
    self._chunk = b""
    self._chunk_pos = 0

  @staticmethod
  async def from_streams(reader: AsyncStreamReader @ref, writer: AsyncStreamWriter @ref) -> Self:
    head: ClientResponse = await new.read_head_async(reader)
    return new.from_head(reader, writer, head)

  @staticmethod
  def from_head(reader: AsyncStreamReader @ref, writer: AsyncStreamWriter @ref, head: ClientResponse) -> Self:
    out: Self = new()
    out.status = head.status
    out.headers = head.headers
    out._reader = reader
    out._writer = writer
    out._chunked = _header_is_chunked(out.headers)
    return out

  def close(self) -> None:
    if self._closed:
      return
    self._closed = True
    self._reader.close()
    self._writer.close()

  async def _read_next_chunk(self) -> bool:
    if self._done:
      return False
    line_b: bytes = await self._reader.readuntil(_CRLF)
    line: str = _strip_line_end(line_b.decode())
    size: int = parse_ascii_hex(line)
    if size <= 0:
      self._done = True
      trailer: bytes = await self._reader.readuntil(_CRLF)
      return False
    self._chunk = await self._reader.readexactly(size)
    self._chunk_pos = 0
    crlf: bytes = await self._reader.readexactly(2)
    return True

  async def _read_chunked_line(self) -> str:
    buf: byte[:] = b""
    at: int = 0
    while True:
      while self._chunk_pos >= len(self._chunk):
        more: bool = await self._read_next_chunk()
        if not more:
          return _bytes_from_buf(buf, at).decode()
      b: byte = self._chunk[self._chunk_pos]
      self._chunk_pos += 1
      if b == ord("\n"):
        return _bytes_from_buf(buf, at).decode()
      if b != ord("\r"):
        at = _append_one(buf, at, b)

  async def readline(self) -> str:
    """异步读取 body 中下一行（不含行尾）；chunked 响应会先解码 chunk。"""
    if self._chunked:
      return await self._read_chunked_line()
    line_b: bytes = await self._reader.readuntil(b"\n")
    return _strip_line_end(line_b.decode())


@immutable
def _header_keys(headers: dict[str, str]) -> list[str]:
  out: list[str] = []
  for k in headers:
    out.append(k)
  return out


@immutable
def _header_key(line: bytes) -> str:
  colon: int = line.find(b":")
  if colon < 0:
    return ""
  key_part: bytes = line[:colon]
  return key_part.decode()


@immutable
def _header_value(line: bytes) -> str:
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
def _header_lines(block: bytes) -> list[bytes]:
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
      line_buf: byte[:] = new(ln)
      for j in range(ln):
        line_buf[j] = buf[start + j]
      line: bytes = bytes(line_buf)
      if not line:
        break
      out.append(line)
      i += 2
      start = i
      continue
    i += 1
  return out
