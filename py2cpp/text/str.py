"""str：不可变 Unicode 文本（``char[:]`` 码点）。

方法签名与语义对齐 Python 3.13 ``str`` 文档（``library/stdtypes.html#string-methods``）。
切片下标使用 ``slice[int, int]``（见 ``slice.py``）。
"""
from ..builtins import *
from .bytes import bytes
from ..util.dict import dict
from ..core.exceptions import IndexError, ValueError
from ..util.list import list
from ..util.memory import copyBuf
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

  _hash: int = 0
  _hashOk: bool = False

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
  def _translateBufLen(n: int) -> int:
    return n * 2

  @staticmethod
  def _translateDeleteMarker() -> char:
    return Self._DeleteChar

  @staticmethod
  def _appendByte(buf: byte[:], at: int, b: byte) -> int:
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
  def _writeUtf8(buf: byte[:], at: int, c: char) -> int:
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

  @overload
  def __init__(self, text: CStr = ""):
    n: int = len(text)
    self._hash = 0
    self._hashOk = n == 0
    self._data: array[char, _SsoCap] = new(n)
    if n > 0:
      for i in range(n):
        self._data[i] = char(text[i])

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

  def copyTo(self, buf: char[:], at: int = 0) -> int:
    """把本串码点写入 ``buf[at:]``，返回新尾下标。"""
    sn: int = len(self)
    if sn == 0:
      return at
    end: int = at + sn
    n: int = len(buf)
    if end > n:
      buf.reshape(end, n)
    for i in range(sn):
      buf[at + i] = self._data[i]
    return end

  def copySliceTo(self, start: int, end: int, buf: char[:], at: int) -> int:
    """``self[start:end]`` 写入 ``buf[at:]``，返回新尾下标。"""
    n: int = end - start
    if n <= 0:
      return at
    need: int = at + n
    buf.reserve(need)
    seg: span[char] = self._data.view[start:end]
    for i in range(n):
      buf[at + i] = seg[i]
    return need

  @staticmethod
  @immutable
  def concat(parts: list[Self]) -> Self:
    return "".join(parts)

  def replaceSlice(self, start: int, end: int, repl: Self) -> Self:
    """单次分配 ``char[:]`` 拼接 ``self[:start] + repl + self[end:]``。"""
    sn: int = len(self)
    if start < 0:
      start = 0
    if end < start:
      end = start
    if start > sn:
      start = sn
    if end > sn:
      end = sn
    rn: int = len(repl)
    if start == 0 and end == sn:
      return repl
    tail: int = sn - end
    newLen: int = start + rn + tail
    if newLen == 0:
      return ""
    if tail == 0 and rn == 0 and start == sn:
      return self
    buf: char[:] = new(newLen)
    at: int = 0
    if start > 0:
      head: span[char] = self._data.view[:start]
      for i in range(start):
        buf[at + i] = head[i]
      at = start
    if rn > 0:
      rview: span[char] = repl.view[:rn]
      for i in range(rn):
        buf[at + i] = rview[i]
      at += rn
    tailN: int = sn - end
    if tailN > 0:
      tview: span[char] = self._data.view[end:sn]
      for i in range(tailN):
        buf[at + i] = tview[i]
      at += tailN
    return Self.fromBuf(buf, at)

  @staticmethod
  def fromBufRef(buf: char[:], end: int) -> Self:
    """``buf[:end]`` → ``str``（纯 Python；``@native fromBuf`` 的语义参照）。"""
    raw = str(buf)
    return raw[:end]

  @staticmethod
  @native
  def fromBuf(buf: char[:], end: int) -> Self:
    """``buf[:end]`` → ``str``（encode ``finish`` 收尾）。"""
    ...

  @staticmethod
  @immutable
  def fromSpan(seg: span[char]) -> Self:
    """由 ``span[char]`` 拷贝构造（``copyFromSpan`` 组合）。"""
    dst: Self = ""
    dst.copyFromSpan(seg)
    return dst

  @overload
  def copyFromSpan(self, seg: span[char]) -> None:
    """将 ``span[char]`` 写入已有 ``PyStr``（``copyBuf`` 叶子）。"""
    n: int = len(seg)
    if not n:
      self._data.reshape(0, 0)
      self._hash = 0
      self._hashOk = True
      return
    if len(self._data) != n:
      self._data.reshape(n, 0)
    self._data.copyPtrFrom(0, seg.at(), n)
    self._hash = 0
    self._hashOk = False

  @overload
  def copyFromSpan(self, seg: span[byte]) -> None:
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
      self._data[i] = char(seg[i])
    self._hash = 0
    self._hashOk = False

  @immutable
  @overload
  def copyToSpan(self, dest: span[byte]) -> None:
    """把本串按单字节写入 ``dest`` 并以 ``\\0`` 收尾（``len(dest)`` 为容量上限；C API 缓冲）。"""
    cap: int = len(dest)
    if cap <= 0:
      return
    n: int = len(self)
    lim: int = n
    maxBody: int = cap - 1
    if lim > maxBody:
      lim = maxBody
    for i in range(lim):
      dest[i] = byte(self[i])
    dest[lim] = byte(0)

  @immutable
  @overload
  def copyToSpan(self, dest: span[char]) -> None:
    """把码点写入 ``dest`` 并以 ``PyChar(0)`` 收尾（``len(dest)`` 为容量上限）。"""
    cap: int = len(dest)
    if cap <= 0:
      return
    n: int = len(self)
    lim: int = n
    maxBody: int = cap - 1
    if lim > maxBody:
      lim = maxBody
    if lim > 0:
      self._data.copyPtrTo(0, dest.at(), lim)
    dest[lim] = char(0)

  def adoptSpan(self, seg: span[char]) -> None:
    """接管 ``span[char]`` 底层 ``char`` 缓冲（serde Arena；勿与 ``reshape`` 混用）。"""
    self._data.adoptSpan(seg)
    self._hash = 0
    self._hashOk = False

  def __copy__(self, other: Self):
    n: int = len(other._data)
    if len(self._data) != n:
      self._data.reshape(n, 0)
    self._data.__copy__(other._data)
    self._hash = other._hash
    self._hashOk = other._hashOk

  @overload
  def __init__(self, value: int):
    buf: byte[:] = new(32)
    ptr: CStr = cast(buf.view.at())
    pyiSnprintf(ptr, len(buf), "%d", value)
    self.copyFromSpan(buf.view)

  @overload
  def __init__(self, value: int64):
    buf: byte[:] = new(32)
    ptr: CStr = cast(buf.view.at())
    pyiSnprintf(ptr, len(buf), "%lld", value)
    self.copyFromSpan(buf.view)

  @overload
  def __init__(self, value: float):
    buf: byte[:] = new(64)
    ptr: CStr = cast(buf.view.at())
    pyiSnprintf(ptr, len(buf), "%g", value)
    self.copyFromSpan(buf.view)

  @overload
  def __init__(self, value: float64):
    buf: byte[:] = new(64)
    ptr: CStr = cast(buf.view.at())
    pyiSnprintf(ptr, len(buf), "%g", value)
    self.copyFromSpan(buf.view)

  @overload
  @native
  def __init__(self, value: bool):
    ...

  @immutable
  def __int__(self) -> int:
    buf: byte[:] = new(len(self) + 1)
    self.copyToSpan(buf.view)
    ptr: CStr = cast(buf.view.at())
    value: int = 0
    if pyiSscanf(ptr, "%d", id(value)) != 1:
      raise ValueError
    return value

  @immutable
  def __float__(self) -> float:
    buf: byte[:] = new(len(self) + 1)
    self.copyToSpan(buf.view)
    ptr: CStr = cast(buf.view.at())
    value: float = 0.0
    if pyiSscanf(ptr, "%lf", id(value)) != 1:
      raise ValueError
    return value
  @immutable
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

  @property
  @immutable
  def view(self) -> span[char]:
    """只读码点视图（``serde`` 等）。"""
    return self._data.view

  def __iter__(self) -> StrIterator:
    return new(self.view)

  def __reversed__(self) -> StrReverseIterator:
    return new(self.view)

  @immutable
  def casefold(self) -> Self:
    return self.lower()

  @immutable
  def encode(self, encoding: CStr = "utf-8", errors: CStr = "strict") -> bytes:
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
      at = Self._writeUtf8(buf, at, self._data[i])
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
