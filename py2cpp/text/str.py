"""str：不可变 Unicode 文本（``char[:]`` 码点）。

方法签名与语义对齐 Python 3.13 ``str`` 文档（``library/stdtypes.html#string-methods``）。
切片下标使用 ``slice[int, int]``（见 ``slice.py``）。
"""
from ..builtins import *
from .bytes import bytes
from ..util.dict import dict
from ..core.exceptions import IndexError, ValueError
from ..util.list import list
from ..util.memory import copyArray
from ..util.array import array
from ..util.slice import slice
from ..util.span import span
from ..util.tuple import tuple
from ffi.crt.stdio import pyiSnprintf, pyiSscanf
from .mixins import StringMixin

class StrIterator:
  def __init__(self, view: span[char]):
    self._view: span[char] = view
    self._index: int = 0

  def __iter__(self):
    return self

  def __next__(self) -> char:
    if self._index >= len(self._view):
      raise StopIteration
    c: char = self._view[self._index]
    self._index += 1
    return c


class StrReverseIterator:
  def __init__(self, view: span[char]):
    self._view: span[char] = view
    self._index: int = len(view) - 1

  def __iter__(self):
    return self

  def __next__(self) -> char:
    if self._index < 0:
      raise StopIteration
    c: char = self._view[self._index]
    self._index -= 1
    return c

@copyable
class str(StringMixin[char]):
  """不可变 Unicode 字符串。"""

  _data: array[char, _SsoCap]

  _DeleteChar: int @const = 0xFFFF

  _hash: int
  _hashOk: bool

  def _didChangeData(self) -> None:
    self._hash = 0
    self._hashOk = not self._data

  @immutable
  @staticmethod
  def reprChar(c: char) -> Self:
    """单码点 ``repr`` 片段（不含外层引号；供全局 ``::repr(char)``）。"""
    return Self._reprCodepoint(c)

  @staticmethod
  def _defaultPadChar() -> char:
    return 32

  @staticmethod
  def _zfillPadChar() -> char:
    return 48

  @staticmethod
  def _translateArrayLen(n: int) -> int:
    return n * 2

  @staticmethod
  def _translateDeleteMarker() -> char:
    return Self._DeleteChar

  @staticmethod
  def _appendByte(buf: span[byte], at: int, b: byte) -> int:
    buf[at] = b
    return at + 1

  @immutable
  @staticmethod
  def _isAlnumChar(c: char) -> bool:
    return Self._isAlphaChar(c) or Self._isDigitChar(c)

  @immutable
  @staticmethod
  def _isAlphaChar(c: char) -> bool:
    if c >= ord("A") and c <= ord("Z"):
      return True
    if c >= ord("a") and c <= ord("z"):
      return True
    return False

  @immutable
  @staticmethod
  def _isAscii(c: char) -> bool:
    return c >= 0 and c < 128

  @immutable
  @staticmethod
  def _isAsciiWhitespace(c: char) -> bool:
    return c in "\t\n\v\f\r "

  @immutable
  @staticmethod
  def _isCased(c: char) -> bool:
    if c >= ord("A") and c <= ord("Z"):
      return True
    if c >= ord("a") and c <= ord("z"):
      return True
    return False

  @immutable
  @staticmethod
  def _isDigitChar(c: char) -> bool:
    return c >= ord("0") and c <= ord("9")

  @immutable
  @staticmethod
  def _isLinebreak(c: char) -> bool:
    return c in "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"

  @immutable
  @staticmethod
  def _isPrintableChar(c: char) -> bool:
    if c in " ":
      return True
    if c < ord(" "):
      return False
    if c in "\x7f":
      return False
    if c < 128:
      return True
    if Self._isFieldWhitespace(c):
      return False
    return True

  @immutable
  @staticmethod
  def _isFieldWhitespace(c: char) -> bool:
    if c in "\t\n\v\f\r \u0085\u00a0\u2028\u2029\u3000":
      return True
    if c >= 0x2000 and c <= 0x200A:
      return True
    return False

  @immutable
  @staticmethod
  def _isCrLfPair(cr: char, lf: char) -> bool:
    return cr in "\r" and lf in "\n"

  @immutable
  @staticmethod
  def _reprCodepoint(c: char) -> Self:
    hit: Self = {
      ord("'"): "\\'",
      ord("\\"): "\\\\",
      ord("\n"): "\\n",
      ord("\r"): "\\r",
      ord("\t"): "\\t",
    }.get(c, "")
    if hit:
      return hit
    if c >= ord(" ") and c <= ord("~"):
      return new(c)
    out: Self = "\\x"
    hi: int = (c // 16) % 16
    lo: int = c % 16
    if hi < 10:
      out += Self(48 + hi)
    else:
      out += Self(87 + hi)
    if lo < 10:
      return out + Self(48 + lo)
    return out + Self(87 + lo)

  @immutable
  @staticmethod
  def _reverseCodes(codes: char[:]) -> char[:]:
    n: int = len(codes)
    buf: char[:] = new(n)
    for i in range(n):
      buf[i] = codes[n - 1 - i]
    return buf

  @immutable
  @staticmethod
  def _toLowerChar(c: char) -> char:
    if c >= ord("A") and c <= ord("Z"):
      return c + 32
    return c

  @immutable
  @staticmethod
  def _toUpperChar(c: char) -> char:
    if c >= ord("a") and c <= ord("z"):
      return c - 32
    return c

  @immutable
  @staticmethod
  def _utf8ByteLen(c: char) -> int:
    if c < 0x80:
      return 1
    if c < 0x800:
      return 2
    if c < 0x10000:
      return 3
    return 4

  @staticmethod
  def _writeUtf8(buf: span[byte], at: int, c: char) -> int:
    if c < 0x80:
      return Self._appendByte(buf, at, c)
    if c < 0x800:
      at = Self._appendByte(buf, at, (c >> 6) | 0xC0)
      return Self._appendByte(buf, at, (c & 0x3F) | 0x80)
    if c < 0x10000:
      at = Self._appendByte(buf, at, (c >> 12) | 0xE0)
      at = Self._appendByte(buf, at, ((c >> 6) & 0x3F) | 0x80)
      return Self._appendByte(buf, at, (c & 0x3F) | 0x80)
    at = Self._appendByte(buf, at, (c >> 18) | 0xF0)
    at = Self._appendByte(buf, at, ((c >> 12) & 0x3F) | 0x80)
    at = Self._appendByte(buf, at, ((c >> 6) & 0x3F) | 0x80)
    return Self._appendByte(buf, at, (c & 0x3F) | 0x80)

  @staticmethod
  def _writeUtf16(buf: span[uint16], at: int, c: char) -> int:
    if c >= 0xD800 and c <= 0xDFFF:
      raise ValueError("invalid Unicode surrogate")
    if c > 0x10FFFF:
      raise ValueError("invalid Unicode code point")
    if c < 0x10000:
      buf[at] = uint16(c)
      return at + 1
    value: int = c - 0x10000
    buf[at] = uint16(0xD800 + (value >> 10))
    buf[at + 1] = uint16(0xDC00 + (value & 0x3FF))
    return at + 2

  @immutable
  @staticmethod
  def _isUtf8Continuation(value: int) -> bool:
    return value >= 0x80 and value <= 0xBF

  @overload
  def __init__(self, text: utf8ptr = ""):
    # 空 C 串不可再走 fromUtf8→fromSpanUtf8→`return ""`→本构造，否则栈溢出
    view: span[byte] = text.view
    if not view:
      self._hash = 0
      self._hashOk = True
      self._data = new(0)
      return
    decoded: Self = Self.fromSpanUtf8(view)
    self._hash = 0
    self._hashOk = not decoded
    self._data: array[char, _SsoCap] = decoded._data

  @overload
  def __init__(self, text: utf16ptr):
    view: span[uint16] = text.view
    if not view:
      self._hash = 0
      self._hashOk = True
      self._data = new(0)
      return
    decoded: Self = Self.fromSpanUtf16(view)
    self._hash = 0
    self._hashOk = not decoded
    self._data = decoded._data

  @overload
  def __init__(self, data: char[:]):
    self._hash = 0
    self._hashOk = False
    n: int = len(data)
    self._data = new(n)
    for i in range(n):
      self._data[i] = data[i]
    data.reshape(0, 0)

  @overload
  def __init__(self, value: char):
    self._hash = 0
    self._hashOk = False
    self._data = [value]

  @staticmethod
  @immutable
  def fromArrayBytes(buf: byte[:], end: int = int.Max) -> Self:
    """将单字节 ``buf[:end]`` 拷贝构造为 ``str``。"""
    return Self.fromSpanBytes(buf.view[:end])

  @staticmethod
  @immutable
  def fromArrayUtf8(buf: byte[:], end: int = int.Max) -> Self:
    """Construct from strict UTF-8 bytes in buf[:end]."""
    return Self.fromSpanUtf8(buf.view[:end])

  @staticmethod
  @immutable
  def fromArrayUtf16(buf: uint16[:], end: int = int.Max) -> Self:
    """Construct from strict UTF-16 code units in buf[:end]."""
    return Self.fromSpanUtf16(buf.view[:end])

  @staticmethod
  @immutable
  def fromSpanBytes(seg: span[byte]) -> Self:
    """Expand each raw byte in seg to a Unicode code point."""
    buf0: char[:] = new(0)
    dst: Self = new(buf0)
    dst.copyFromSpanBytes(seg)
    return dst

  @staticmethod
  @immutable
  def fromSpanUtf8(seg: span[byte]) -> Self:
    """Copy from a strict UTF-8 byte sequence."""
    n: int = len(seg)
    if n == 0:
      buf0: char[:] = new(0)
      return new(buf0)
    buf: char[:] = new(n)
    at: int = 0
    i: int = 0
    while i < n:
      # MSVC 上 PyByte 为有符号 char：须 & 0xFF 再判 UTF-8 前导字节
      b0 = int(seg[i]) & 0xFF
      if b0 < 0x80:
        buf[at] = char(b0)
        at += 1
        i += 1
        continue
      need: int = 0
      cp: int = 0
      if b0 >= 0xC2 and b0 <= 0xDF:
        need = 1
        cp = b0 & 0x1F
      elif b0 >= 0xE0 and b0 <= 0xEF:
        need = 2
        cp = b0 & 0x0F
      elif b0 >= 0xF0 and b0 <= 0xF4:
        need = 3
        cp = b0 & 0x07
      else:
        raise ValueError("invalid UTF-8 leading byte")
      if i + need >= n:
        raise ValueError("truncated UTF-8 sequence")
      b1 = int(seg[i + 1]) & 0xFF
      if not Self._isUtf8Continuation(b1):
        raise ValueError("invalid UTF-8 continuation byte")
      if (b0 == 0xE0 and b1 < 0xA0) or (b0 == 0xED and b1 >= 0xA0):
        raise ValueError("invalid UTF-8 code point")
      if (b0 == 0xF0 and b1 < 0x90) or (b0 == 0xF4 and b1 > 0x8F):
        raise ValueError("invalid UTF-8 code point")
      cp = (cp << 6) | (b1 & 0x3F)
      for j in range(2, need + 1):
        b = int(seg[i + j]) & 0xFF
        if not Self._isUtf8Continuation(b):
          raise ValueError("invalid UTF-8 continuation byte")
        cp = (cp << 6) | (b & 0x3F)
      buf[at] = char(cp)
      at += 1
      i += need + 1
    if at == n:
      return Self.fromSpan(buf.view)
    out: char[:] = new(at)
    for j in range(at):
      out[j] = buf[j]
    return Self.fromSpan(out.view)

  @staticmethod
  @immutable
  def fromUtf8(text: utf8ptr) -> Self:
    """Copy from a NUL-terminated UTF-8 C string."""
    return Self.fromSpanUtf8(text.view)
  @staticmethod
  @immutable
  def fromUtf8Writer(
    write: Callable[[utf8ptr, uint], uint],
    maxCapacity: int = int.Max,
    initCapacity: int = 256,
  ) -> Self:
    """Build from a UTF-8 C writer returning length or required capacity."""
    if maxCapacity <= 0:
      raise ValueError("maxCapacity must be positive")
    if initCapacity <= 0:
      raise ValueError("initCapacity must be positive")
    capacity: int = initCapacity
    if capacity > maxCapacity:
      raise ValueError("initCapacity exceeds maxCapacity")
    while True:
      data: byte[:] = new(capacity)
      written: uint = write(cast[utf8ptr](data.view.at()), uint(capacity))
      if written < capacity:
        return Self.fromSpanUtf8(data.view[:int(written)])
      capacity = int(written) + 1
      if capacity > maxCapacity:
        raise ValueError("C string output exceeds maxCapacity")

  @staticmethod
  @immutable
  def fromSpanUtf16(seg: span[uint16]) -> Self:
    """Copy from a strict UTF-16 code-unit sequence."""
    n: int = len(seg)
    if n == 0:
      buf0: char[:] = new(0)
      return new(buf0)
    buf: char[:] = new(n)
    at: int = 0
    i: int = 0
    while i < n:
      unit = int(seg[i])
      if unit >= 0xD800 and unit <= 0xDBFF:
        if i + 1 >= n:
          raise ValueError("truncated UTF-16 surrogate pair")
        low = int(seg[i + 1])
        if low < 0xDC00 or low > 0xDFFF:
          raise ValueError("invalid UTF-16 surrogate pair")
        buf[at] = char(0x10000 + ((unit - 0xD800) << 10) + (low - 0xDC00))
        at += 1
        i += 2
        continue
      if unit >= 0xDC00 and unit <= 0xDFFF:
        raise ValueError("invalid UTF-16 surrogate")
      buf[at] = char(unit)
      at += 1
      i += 1
    if at == n:
      return Self.fromSpan(buf.view)
    out: char[:] = new(at)
    for j in range(at):
      out[j] = buf[j]
    return Self.fromSpan(out.view)

  @staticmethod
  @immutable
  def fromUtf16(text: utf16ptr) -> Self:
    """Copy from a NUL-terminated Windows UTF-16 C string."""
    return Self.fromSpanUtf16(text.view)

  def copyFromSpanBytes(self, seg: span[byte]) -> None:
    """将 ``span[byte]`` 按 ``char`` 写入已有 ``PyStr``（C API / 单字节源）。"""
    n: int = len(seg)
    if not n:
      self._data.reshape(0, 0)
      self._hash = 0
      self._hashOk = True
      return
    if len(self._data) != n:
      self._data.reshape(n, 0)
    for i in range(n):
      self._data[i] = char(int(seg[i]) & 0xFF)
    self._hash = 0
    self._hashOk = False

  def copyFromSpanUtf8(self, seg: span[byte]) -> None:
    """Strictly decode UTF-8 seg into this string."""
    text: Self = Self.fromSpanUtf8(seg)
    self.copyFromSpan(text.view)

  def copyFromSpanUtf16(self, seg: span[uint16]) -> None:
    """Strictly decode UTF-16 seg into this string."""
    text: Self = Self.fromSpanUtf16(seg)
    self.copyFromSpan(text.view)

  @immutable
  def copyToSpanUtf8(self, dest: span[byte]) -> None:
    """Encode as UTF-8 into dest and append a NUL terminator."""
    cap: int = len(dest)
    if cap <= 0:
      return
    at: int = 0
    for i in range(len(self)):
      c: char = self[i]
      if c == 0:
        raise ValueError("C string cannot contain NUL")
      width: int = Self._utf8ByteLen(c)
      if at + width >= cap:
        break
      at = Self._writeUtf8(dest, at, c)
    dest[at] = byte(0)

  @immutable
  def copyToSpanUtf16(self, dest: span[uint16]) -> None:
    """Encode as UTF-16 into dest and append a NUL terminator."""
    cap: int = len(dest)
    if cap <= 0:
      return
    at: int = 0
    for i in range(len(self)):
      c: char = self[i]
      if c == 0:
        raise ValueError("C string cannot contain NUL")
      width: int = 1
      if c > 0xFFFF:
        width = 2
      if at + width >= cap:
        break
      at = Self._writeUtf16(dest, at, c)
    dest[at] = uint16(0)

  @immutable
  def toArrayUtf8(self) -> byte[:]:
    """Return a UTF-8, NUL-terminated owned byte array."""
    total: int = 0
    for i in range(len(self)):
      c: char = self[i]
      if c == 0:
        raise ValueError("C string cannot contain NUL")
      total += Self._utf8ByteLen(c)
    data: byte[:] = new(total + 1)
    self.copyToSpanUtf8(data.view)
    return data

  @immutable
  def toArrayUtf16(self) -> uint16[:]:
    """Return a Windows UTF-16, NUL-terminated owned array."""
    total: int = 0
    for i in range(len(self)):
      c: char = self[i]
      if c == 0:
        raise ValueError("C string cannot contain NUL")
      if c >= 0xD800 and c <= 0xDFFF:
        raise ValueError("invalid Unicode surrogate")
      if c > 0x10FFFF:
        raise ValueError("invalid Unicode code point")
      total += 1
      if c > 0xFFFF:
        total += 1
    data: uint16[:] = new(total + 1)
    self.copyToSpanUtf16(data.view)
    return data

  @context
  def useUtf8(self) -> utf8ptr:
    """在 ``with self.useUtf8() as p`` 中借出本串的 NUL 终止 ``utf8ptr``。"""
    _cstrData: byte[:] = self.toArrayUtf8()
    yield cast(_cstrData.view.at())

  @context
  def useUtf16(self) -> utf16ptr:
    """Borrow a UTF-16 utf16ptr for one context scope."""
    data: uint16[:] = self.toArrayUtf16()
    yield cast(data.view.at())

  def __copy__(self, other: Self):
    n: int = len(other._data)
    if len(self._data) != n:
      self._data.reshape(n, 0)
    self._data.__copy__(other._data)
    self._hash = other._hash
    self._hashOk = other._hashOk

  @overload
  def __init__(self, value: int):
    # 仅拷贝 snprintf 写入长度；勿用整段 buf（否则嵌入 NUL，PrintfArg 抛 ValueError）
    buf: byte[:] = new(32)
    ptr: utf8ptr = cast(buf.view.at())
    n: int = pyiSnprintf(ptr, len(buf), "%d", value)
    if n < 0:
      n = 0
    elif n >= len(buf):
      n = len(buf) - 1
    self.copyFromSpanBytes(buf.view[:n])

  @overload
  def __init__(self, value: int64):
    buf: byte[:] = new(32)
    ptr: utf8ptr = cast(buf.view.at())
    n: int = pyiSnprintf(ptr, len(buf), "%lld", value)
    if n < 0:
      n = 0
    elif n >= len(buf):
      n = len(buf) - 1
    self.copyFromSpanBytes(buf.view[:n])

  @overload
  def __init__(self, value: float):
    buf: byte[:] = new(64)
    ptr: utf8ptr = cast(buf.view.at())
    n: int = pyiSnprintf(ptr, len(buf), "%g", value)
    if n < 0:
      n = 0
    elif n >= len(buf):
      n = len(buf) - 1
    self.copyFromSpanBytes(buf.view[:n])

  @overload
  def __init__(self, value: float64):
    buf: byte[:] = new(64)
    ptr: utf8ptr = cast(buf.view.at())
    n: int = pyiSnprintf(ptr, len(buf), "%g", value)
    if n < 0:
      n = 0
    elif n >= len(buf):
      n = len(buf) - 1
    self.copyFromSpanBytes(buf.view[:n])

  @overload
  @native
  def __init__(self, value: bool):
    ...

  @immutable
  def __int__(self) -> int:
    value: int = 0
    with self.useUtf8() as ptr:
      if pyiSscanf(ptr, "%d", id(value)) != 1:
        raise ValueError
    return value

  @immutable
  def __float__(self) -> float:
    value: float = 0.0
    with self.useUtf8() as ptr:
      if pyiSscanf(ptr, "%lf", id(value)) != 1:
        raise ValueError
    return value
  def __str__(self) -> Self:
    return self

  @immutable
  def __repr__(self) -> Self:
    out: Self = "'"
    n: int = len(self)
    for i in range(n):
      out += Self._reprCodepoint(self._data[i])
    return out + "'"

  @immutable
  def __format__(self, formatSpec: Self) -> Self:
    return self

  def cacheHash(self, h: int) -> None:
    """由 ``JsonDecoder.loadKey`` 等在已算好哈希时写入缓存（与 ``__hash__`` 算法一致）。"""
    self._hash = h
    self._hashOk = True

  @immutable
  def _peekHash(self) -> int:
    """只读哈希（``const`` 比较用）；已缓存则直接返回，否则现场计算不落盘。"""
    if self._hashOk:
      return self._hash
    h: int = 0
    n: int = len(self._data)
    for i in range(n):
      h = h * 31 + self._data[i]
    return h

  def __hash__(self) -> int:
    """多项式哈希（惰性缓存），供 ``dict[str, …]`` 等。"""
    if self._hashOk:
      return self._hash
    h: int = self._peekHash()
    self._hash = h
    self._hashOk = True
    return h

  @immutable
  def __eq__(self, other: Self) -> bool:
    na: int = len(self._data)
    nb: int = len(other._data)
    if na != nb:
      return False
    if na == 0:
      return True
    if self._hashOk and other._hashOk:
      if self._hash != other._hash:
        return False
    elif self._peekHash() != other._peekHash():
      return False
    return self._compare(other) == 0

  def __iter__(self) -> StrIterator:
    return new(self.view)

  def __reversed__(self) -> StrReverseIterator:
    return new(self.view)

  @immutable
  def casefold(self) -> Self:
    return self.lower()

  @immutable
  def encode(self, encoding: utf8ptr = "utf-8", errors: utf8ptr = "strict") -> bytes:
    n: int = len(self)
    total: int = 0
    for i in range(n):
      total += Self._utf8ByteLen(self._data[i])
    if total == 0:
      empty: byte[:] = b""
      return bytes(empty)
    buf: byte[:] = new(total)
    at: int = 0
    for i in range(n):
      at = Self._writeUtf8(buf.view, at, self._data[i])
    return bytes(buf)

  @immutable
  def isIdentifier(self) -> bool:
    n: int = len(self)
    if n == 0:
      return False
    c0: char = self._data[0]
    if not (c0 in "_" or Self._isAlphaChar(c0)):
      return False
    for i in range(1, n):
      c: char = self._data[i]
      if not (c in "_" or Self._isAlnumChar(c)):
        return False
    return True

  @immutable
  def isNumeric(self) -> bool:
    return self.isDigit()

  @immutable
  def isPrintable(self) -> bool:
    for i in range(len(self)):
      if not Self._isPrintableChar(self._data[i]):
        return False
    return True

  @immutable
  def isTitle(self) -> bool:
    return self.title() == self

  @native
  def format(self, *args) -> Self:
    ...

  @native
  def formatMap(self, mapping) -> Self:
    ...
