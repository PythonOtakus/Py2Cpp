"""HTTP URL 解析。"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..text.bytes import bytes


_Crlf: bytes = b"\r\n"
_HeaderEnd: bytes = b"\r\n\r\n"


@dataclass
class UrlData:
  scheme: str = "http"
  host: str = "127.0.0.1"
  port: int = 80
  path: str = "/"
  query: str = ""

  @staticmethod
  def defaultPort(scheme: str) -> int:
    if scheme == "https":
      return 443
    return 80

  @staticmethod
  def parse(url: str) -> Self:
    """解析 ``http://host[:port]/path[?query]``（``https`` 暂不支持，仅取 host/port/path）。"""
    out: Self = new()
    rest: str = url
    if rest.startsWith("http://"):
      out.scheme = "http"
      rest = rest[7:]
    elif rest.startsWith("https://"):
      out.scheme = "https"
      rest = rest[8:]
    else:
      raise ValueError("url must start with http:// or https://")
    slash: int = rest.find("/")
    authority: str = rest
    tail: str = "/"
    if slash >= 0:
      authority = rest[:slash]
      tail = rest[slash:]
    colon: int = authority.find(":")
    if colon >= 0:
      out.host = authority[:colon]
      portStr: str = authority[colon + 1:]
      out.port = parseAsciiInt(portStr)
    else:
      out.host = authority
      out.port = Self.defaultPort(out.scheme)
    qmark: int = tail.find("?")
    if qmark >= 0:
      out.path = tail[:qmark]
      out.query = tail[qmark + 1:]
    else:
      out.path = tail
    if not out.path:
      out.path = "/"
    return out


@immutable
def mergeQuery(existing: str, params: dict[str, str]) -> str:
  """合并 URL query 与 ``params``（追加，不做 percent-encoding）。"""
  out: str = existing
  for k in params:
    pair: str = f"{k}={params[k]}"
    if not out:
      out = pair
    else:
      out = f"{out}&{pair}"
  return out


@immutable
def parseAsciiInt(s: str) -> int:
  """十进制 ASCII 串 → ``int``（``int(str)`` 译期替代）。"""
  n: int = 0
  for i in range(len(s)):
    ch: char = s[i]
    d: int = int(ch) - ord("0")
    if d < 0 or d > 9:
      continue
    n = n * 10 + d
  return n

