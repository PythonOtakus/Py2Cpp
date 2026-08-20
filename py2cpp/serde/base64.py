"""Base64 编解码（对齐 Python 3.13 ``base64`` 的 RFC 4648 子集）。

参考 CPython 3.13 ``Lib/base64.py``（``b64encode`` / ``b64decode`` 等）；
核心算法纯 Python；url-safe 字母表用 ``_urlsafeB64swap`` / ``_urlsafeB64swapBack``。

``standard_b64encode`` / ``standard_b64decode`` / ``decodeBytes`` 与 ``b64*`` 等价，调用方直写 ``b64encode``/``b64decode``。
``altchars`` / ``validate`` 暂不在公开签名中（译器默认实参 ``b\"\"`` 会破坏 C++ 形参列表）；url-safe 用 ``urlsafe_*``。
解码错误抛 ``ValueError``（对齐 ``binascii.Error`` 消息）。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..text.bytes import bytes


MaxLineSize: int = 76
MaxBinSize: int = (MaxLineSize // 4) * 3


@immutable
def _b64EncodeChar(v: int) -> byte:
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
def _b64DecodeChar(b: byte) -> int:
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
def _bytesFromDecodeData(s: bytes) -> byte[:]:
  n: int = len(s)
  buf: byte[:] = new(n)
  for i in range(n):
    buf[i] = s[i]
  return buf


@immutable
def _bytesFromDecodeText(s: str) -> byte[:]:
  encoded: bytes = s.encode()
  return _bytesFromDecodeData(encoded)


@immutable
def _appendBytes(
  dst: byte[:],
  at: int,
  src: byte[:],
  end: int = int.Max,
) -> int:
  if end > len(src):
    end = len(src)
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
def _isB64Whitespace(b: byte) -> bool:
  return b in " \t\n\r\v\f"


@immutable
def _byteU(b: byte) -> int:
  return b & 0xFF


@immutable
def _b64encodeRaw(data: byte[:]) -> bytes:
  n: int = len(data)
  if not n:
    empty: bytes = b""
    return empty
  outLen: int = ((n + 2) // 3) * 4
  buf: byte[:] = new(outLen)
  at: int = 0
  for i in range(0, n, 3):
    u0: int = _byteU(data[i])
    u1: int = 0
    u2: int = 0
    if i + 1 < n:
      u1 = _byteU(data[i + 1])
    if i + 2 < n:
      u2 = _byteU(data[i + 2])
    n0: int = u0 >> 2
    n1: int = ((u0 & 3) << 4) | (u1 >> 4)
    n2: int = ((u1 & 15) << 2) | (u2 >> 6)
    n3: int = u2 & 63
    buf[at] = _b64EncodeChar(n0)
    buf[at + 1] = _b64EncodeChar(n1)
    if i + 2 < n:
      buf[at + 2] = _b64EncodeChar(n2)
      buf[at + 3] = _b64EncodeChar(n3)
    elif i + 1 < n:
      buf[at + 2] = _b64EncodeChar(n2)
      buf[at + 3] = ord("=")
    else:
      buf[at + 2] = ord("=")
      buf[at + 3] = ord("=")
    at += 4
  return bytes(buf)


@immutable
def _filterB64Payload(raw: byte[:]) -> byte[:]:
  n: int = len(raw)
  buf: byte[:] = new(n)
  at: int = 0
  for i in range(n):
    b: byte = raw[i]
    if _isB64Whitespace(b):
      continue
    if b == ord("="):
      buf[at] = b
      at += 1
      continue
    if _b64DecodeChar(b) >= 0:
      buf[at] = b
      at += 1
      continue
  trimmed: byte[:] = new(at)
  for j in range(at):
    trimmed[j] = buf[j]
  return trimmed


@immutable
def _b64decodeRaw(payload: byte[:]) -> bytes:
  n: int = len(payload)
  if not n:
    empty: bytes = b""
    return empty
  if (n % 4) != 0:
    raise ValueError("Incorrect padding")
  outLen: int = (n // 4) * 3
  if n >= 1 and payload[n - 1] == ord("="):
    outLen -= 1
  if n >= 2 and payload[n - 2] == ord("="):
    outLen -= 1
  buf: byte[:] = new(outLen)
  at: int = 0
  for i in range(0, n, 4):
    c0: byte = payload[i]
    c1: byte = payload[i + 1]
    c2: byte = payload[i + 2]
    c3: byte = payload[i + 3]
    v0: int = _b64DecodeChar(c0)
    v1: int = _b64DecodeChar(c1)
    v2: int = _b64DecodeChar(c2)
    v3: int = _b64DecodeChar(c3)
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
def _b64decodeView(raw: byte[:]) -> bytes:
  payload: byte[:] = _filterB64Payload(raw)
  return _b64decodeRaw(payload)


def b64encode(s: bytes) -> bytes:
  """``bytes`` → Base64 ``bytes``。"""
  return _b64encodeRaw(_bytesFromDecodeData(s))


@overload
def b64decode(s: str) -> bytes:
  return _b64decodeView(_bytesFromDecodeText(s))


@overload
def b64decode(s: bytes) -> bytes:
  """Base64 ``bytes`` / ASCII ``str`` → 原始 ``bytes``。"""
  return _b64decodeView(_bytesFromDecodeData(s))


@immutable
def _urlsafeB64swap(out: bytes) -> bytes:
  n: int = len(out)
  buf: byte[:] = new(n)
  for i in range(n):
    b: byte = out[i]
    if b == ord("+"):
      buf[i] = ord("-")
    elif b == ord("/"):
      buf[i] = ord("_")
    else:
      buf[i] = b
  return bytes(buf)


@immutable
def _urlsafeB64swapBack(raw: byte[:]) -> byte[:]:
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


def urlsafeB64encode(s: bytes) -> bytes:
  return _urlsafeB64swap(b64encode(s))


@overload
def urlsafeB64decode(s: str) -> bytes:
  swapped: byte[:] = _urlsafeB64swapBack(_bytesFromDecodeText(s))
  return _b64decodeView(swapped)


@overload
def urlsafeB64decode(s: bytes) -> bytes:
  swapped: byte[:] = _urlsafeB64swapBack(_bytesFromDecodeData(s))
  return _b64decodeView(swapped)


def encodeBytes(s: bytes) -> bytes:
  """多行 MIME Base64（每段 ``MaxBinSize`` 字节 + 换行）。"""
  n: int = len(s)
  if not n:
    empty: bytes = b""
    return empty
  out: byte[:] = new(0)
  at: int = 0
  nl: bytes = b"\n"
  for i in range(0, n, MaxBinSize):
    end: int = i + MaxBinSize
    if end > n:
      end = n
    chunk: bytes = s[i:end]
    line: bytes = b64encode(chunk)
    lineArray: byte[:] = _bytesFromDecodeData(line)
    nlArray: byte[:] = _bytesFromDecodeData(nl)
    at = _appendBytes(out, at, lineArray, len(line))
    at = _appendBytes(out, at, nlArray, 1)
  trimmed: byte[:] = new(at)
  for j in range(at):
    trimmed[j] = out[j]
  return bytes(trimmed)
