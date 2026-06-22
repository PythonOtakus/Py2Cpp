"""Base64 编解码（对齐 Python 3.13 ``base64`` 的 RFC 4648 子集）。

参考 CPython 3.13 ``Lib/base64.py``（``b64encode`` / ``b64decode`` 等）；
核心算法纯 Python；url-safe 字母表用 ``_urlsafe_b64swap`` / ``_urlsafe_b64swap_back``。

``standard_b64encode`` / ``standard_b64decode`` / ``decodebytes`` 与 ``b64*`` 等价，调用方直写 ``b64encode``/``b64decode``。
``altchars`` / ``validate`` 暂不在公开签名中（译器默认实参 ``b\"\"`` 会破坏 C++ 形参列表）；url-safe 用 ``urlsafe_*``。
解码错误抛 ``ValueError``（对齐 ``binascii.Error`` 消息）。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..text.bytes import bytes


MAXLINESIZE: int = 76
MAXBINSIZE: int = (MAXLINESIZE // 4) * 3


@immutable
def _b64_encode_char(v: int) -> byte:
  if v < 26:
    return ord("A") + v
  if v < 52:
    return ord("a") + (v - 26)
  if v < 62:
    return ord("0") + (v - 52)
  if v == 62:
    return ord("+")
  return ord("/")


@immutable
def _b64_decode_char(b: byte) -> int:
  if b >= ord("A") and b <= ord("Z"):
    return b - ord("A")
  if b >= ord("a") and b <= ord("z"):
    return b - ord("a") + 26
  if b >= ord("0") and b <= ord("9"):
    return b - ord("0") + 52
  if b == ord("+"):
    return 62
  if b == ord("/"):
    return 63
  return -1


@immutable
def _bytes_from_decode_data(s: bytes) -> byte[:]:
  return s.data


@immutable
def _bytes_from_decode_text(s: str) -> byte[:]:
  encoded: bytes = s.encode()
  return encoded.data


@immutable
def _append_bytes(dst: byte[:], at: int, src: byte[:], end: int) -> int:
  if end <= 0:
    return at
  need: int = at + end
  n: int = len(dst)
  if need > n:
    dst.reshape(need, n)
  for i in range(end):
    dst[at + i] = src[i]
  return need


@immutable
def _is_b64_whitespace(b: byte) -> bool:
  return b in " \t\n\r\v\f"


@immutable
def _byte_u(b: byte) -> int:
  return b & 0xFF


@immutable
def _b64encode_raw(data: byte[:]) -> bytes:
  n: int = len(data)
  if not n:
    empty: bytes = b""
    return empty
  out_len: int = ((n + 2) // 3) * 4
  buf: byte[:] = new(out_len)
  at: int = 0
  for i in range(0, n, 3):
    u0: int = _byte_u(data[i])
    u1: int = 0
    u2: int = 0
    if i + 1 < n:
      u1 = _byte_u(data[i + 1])
    if i + 2 < n:
      u2 = _byte_u(data[i + 2])
    n0: int = u0 >> 2
    n1: int = ((u0 & 3) << 4) | (u1 >> 4)
    n2: int = ((u1 & 15) << 2) | (u2 >> 6)
    n3: int = u2 & 63
    buf[at] = _b64_encode_char(n0)
    buf[at + 1] = _b64_encode_char(n1)
    if i + 2 < n:
      buf[at + 2] = _b64_encode_char(n2)
      buf[at + 3] = _b64_encode_char(n3)
    elif i + 1 < n:
      buf[at + 2] = _b64_encode_char(n2)
      buf[at + 3] = ord("=")
    else:
      buf[at + 2] = ord("=")
      buf[at + 3] = ord("=")
    at += 4
  return bytes(buf)


@immutable
def _filter_b64_payload(raw: byte[:]) -> byte[:]:
  n: int = len(raw)
  buf: byte[:] = new(n)
  at: int = 0
  for i in range(n):
    b: byte = raw[i]
    if _is_b64_whitespace(b):
      continue
    if b == ord("="):
      buf[at] = b
      at += 1
      continue
    if _b64_decode_char(b) >= 0:
      buf[at] = b
      at += 1
      continue
  trimmed: byte[:] = new(at)
  for j in range(at):
    trimmed[j] = buf[j]
  return trimmed


@immutable
def _b64decode_raw(payload: byte[:]) -> bytes:
  n: int = len(payload)
  if not n:
    empty: bytes = b""
    return empty
  if (n % 4) != 0:
    raise ValueError("Incorrect padding")
  out_len: int = (n // 4) * 3
  if n >= 1 and payload[n - 1] == ord("="):
    out_len -= 1
  if n >= 2 and payload[n - 2] == ord("="):
    out_len -= 1
  buf: byte[:] = new(out_len)
  at: int = 0
  for i in range(0, n, 4):
    c0: byte = payload[i]
    c1: byte = payload[i + 1]
    c2: byte = payload[i + 2]
    c3: byte = payload[i + 3]
    v0: int = _b64_decode_char(c0)
    v1: int = _b64_decode_char(c1)
    v2: int = _b64_decode_char(c2)
    v3: int = _b64_decode_char(c3)
    if v0 < 0 or v1 < 0:
      raise ValueError("Incorrect padding")
    b0: byte = (v0 << 2) | (v1 >> 4)
    buf[at] = b0
    at += 1
    if c2 == ord("="):
      break
    if v2 < 0:
      raise ValueError("Incorrect padding")
    b1: byte = ((v1 & 15) << 4) | (v2 >> 2)
    buf[at] = b1
    at += 1
    if c3 == ord("="):
      break
    if v3 < 0:
      raise ValueError("Incorrect padding")
    b2: byte = ((v2 & 3) << 6) | v3
    buf[at] = b2
    at += 1
  return bytes(buf)


@immutable
def _b64decode_view(raw: byte[:]) -> bytes:
  payload: byte[:] = _filter_b64_payload(raw)
  return _b64decode_raw(payload)


def b64encode(s: bytes) -> bytes:
  """``bytes`` → Base64 ``bytes``。"""
  return _b64encode_raw(s.data)


@overload
def b64decode(s: str) -> bytes:
  return _b64decode_view(_bytes_from_decode_text(s))


@overload
def b64decode(s: bytes) -> bytes:
  """Base64 ``bytes`` / ASCII ``str`` → 原始 ``bytes``。"""
  return _b64decode_view(_bytes_from_decode_data(s))


@immutable
def _urlsafe_b64swap(out: bytes) -> bytes:
  n: int = len(out)
  buf: byte[:] = new(n)
  for i in range(n):
    b: byte = out.data[i]
    if b == ord("+"):
      buf[i] = ord("-")
    elif b == ord("/"):
      buf[i] = ord("_")
    else:
      buf[i] = b
  return bytes(buf)


@immutable
def _urlsafe_b64swap_back(raw: byte[:]) -> byte[:]:
  n: int = len(raw)
  buf: byte[:] = new(n)
  for i in range(n):
    b: byte = raw[i]
    if b == ord("-"):
      buf[i] = ord("+")
    elif b == ord("_"):
      buf[i] = ord("/")
    else:
      buf[i] = b
  return buf


def urlsafe_b64encode(s: bytes) -> bytes:
  return _urlsafe_b64swap(b64encode(s))


@overload
def urlsafe_b64decode(s: str) -> bytes:
  swapped: byte[:] = _urlsafe_b64swap_back(_bytes_from_decode_text(s))
  return _b64decode_view(swapped)


@overload
def urlsafe_b64decode(s: bytes) -> bytes:
  swapped: byte[:] = _urlsafe_b64swap_back(_bytes_from_decode_data(s))
  return _b64decode_view(swapped)


def encodebytes(s: bytes) -> bytes:
  """多行 MIME Base64（每段 ``MAXBINSIZE`` 字节 + 换行）。"""
  n: int = len(s)
  if not n:
    empty: bytes = b""
    return empty
  empty_buf: bytes = b""
  out: byte[:] = empty_buf.data
  at: int = 0
  nl: bytes = b"\n"
  for i in range(0, n, MAXBINSIZE):
    end: int = i + MAXBINSIZE
    if end > n:
      end = n
    chunk: bytes = s[i:end]
    line: bytes = b64encode(chunk)
    at = _append_bytes(out, at, line.data, len(line))
    at = _append_bytes(out, at, nl.data, 1)
  trimmed: byte[:] = new(at)
  for j in range(at):
    trimmed[j] = out[j]
  return bytes(trimmed)
