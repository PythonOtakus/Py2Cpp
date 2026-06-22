"""str：不可变 Unicode 文本（``char[:]`` 码点）。

方法签名与语义对齐 Python 3.13 ``str`` 文档（``library/stdtypes.html#string-methods``）。
切片下标使用 ``slice[int, int]``（见 ``slice.py``）。
"""
from ..builtins import *
from .bytes import bytes
from ..util.dict import dict
from ..core.exceptions import IndexError, ValueError
from ..util.list import list
from ..util.memory import copy_buf
from ..util.array import array
from ..util.slice import slice
from ..util.span import span
from ..util.tuple import tuple
from .string_mixin import StringMixin

@native_name("PyStrIterator")
class str_iterator:
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


@native_name("PyStrReverseIterator")
class str_reverse_iterator:
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
@native_name("PyStr")
class str(StringMixin[char]):
  """不可变 Unicode 字符串。"""

  data: array[char, _SSO_CAP]

  _DELETE_CHAR: int @const = 0xFFFF

  _hash: int = 0
  _hash_ok: bool = False

  @immutable
  @staticmethod
  def repr_char(c: char) -> Self:
    """单码点 ``repr`` 片段（不含外层引号；供全局 ``::repr(char)``）。"""
    return Self._repr_codepoint(c)

  @staticmethod
  def _default_pad_char() -> char:
    return 32

  @staticmethod
  def _zfill_pad_char() -> char:
    return 48

  @staticmethod
  def _translate_buf_len(n: int) -> int:
    return n * 2

  @staticmethod
  def _translate_delete_marker() -> char:
    return Self._DELETE_CHAR

  @staticmethod
  def _append_byte(buf: byte[:], at: int, b: byte) -> int:
    buf[at] = b
    return at + 1

  @immutable
  @staticmethod
  def _is_alnum_char(c: char) -> bool:
    return Self._is_alpha_char(c) or Self._is_digit_char(c)

  @immutable
  @staticmethod
  def _is_alpha_char(c: char) -> bool:
    if c >= ord("A") and c <= ord("Z"):
      return True
    if c >= ord("a") and c <= ord("z"):
      return True
    return False

  @immutable
  @staticmethod
  def _is_ascii(c: char) -> bool:
    return c >= 0 and c < 128

  @immutable
  @staticmethod
  def _is_ascii_whitespace(c: char) -> bool:
    return c in "\t\n\v\f\r "

  @immutable
  @staticmethod
  def _is_cased(c: char) -> bool:
    if c >= ord("A") and c <= ord("Z"):
      return True
    if c >= ord("a") and c <= ord("z"):
      return True
    return False

  @immutable
  @staticmethod
  def _is_digit_char(c: char) -> bool:
    return c >= ord("0") and c <= ord("9")

  @immutable
  @staticmethod
  def _is_linebreak(c: char) -> bool:
    return c in "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"

  @immutable
  @staticmethod
  def _is_printable_char(c: char) -> bool:
    if c in " ":
      return True
    if c < ord(" "):
      return False
    if c in "\x7f":
      return False
    if c < 128:
      return True
    if Self._is_field_whitespace(c):
      return False
    return True

  @immutable
  @staticmethod
  def _is_field_whitespace(c: char) -> bool:
    if c in "\t\n\v\f\r \u0085\u00a0\u2028\u2029\u3000":
      return True
    if c >= 0x2000 and c <= 0x200A:
      return True
    return False

  @immutable
  @staticmethod
  def _is_cr_lf_pair(cr: char, lf: char) -> bool:
    return cr in "\r" and lf in "\n"

  @immutable
  @staticmethod
  def _repr_codepoint(c: char) -> Self:
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
  def _reverse_codes(codes: char[:]) -> char[:]:
    n: int = len(codes)
    buf: char[:] = new(n)
    for i in range(n):
      buf[i] = codes[n - 1 - i]
    return buf

  @immutable
  @staticmethod
  def _to_lower_char(c: char) -> char:
    if c >= ord("A") and c <= ord("Z"):
      return c + 32
    return c

  @immutable
  @staticmethod
  def _to_upper_char(c: char) -> char:
    if c >= ord("a") and c <= ord("z"):
      return c - 32
    return c

  @immutable
  @staticmethod
  def _utf8_byte_len(c: char) -> int:
    if c < 0x80:
      return 1
    if c < 0x800:
      return 2
    if c < 0x10000:
      return 3
    return 4

  @staticmethod
  def _write_utf8(buf: byte[:], at: int, c: char) -> int:
    if c < 0x80:
      return Self._append_byte(buf, at, c)
    if c < 0x800:
      at = Self._append_byte(buf, at, (c >> 6) | 0xC0)
      return Self._append_byte(buf, at, (c & 0x3F) | 0x80)
    if c < 0x10000:
      at = Self._append_byte(buf, at, (c >> 12) | 0xE0)
      at = Self._append_byte(buf, at, ((c >> 6) & 0x3F) | 0x80)
      return Self._append_byte(buf, at, (c & 0x3F) | 0x80)
    at = Self._append_byte(buf, at, (c >> 18) | 0xF0)
    at = Self._append_byte(buf, at, ((c >> 12) & 0x3F) | 0x80)
    at = Self._append_byte(buf, at, ((c >> 6) & 0x3F) | 0x80)
    return Self._append_byte(buf, at, (c & 0x3F) | 0x80)

  @overload
  def __init__(self, text: c_str = ""):
    n: int = len(text)
    self._hash = 0
    self._hash_ok = n == 0
    self.data: array[char, _SSO_CAP] = new(n)
    if n > 0:
      for i in range(n):
        self.data[i] = char(text[i])

  @overload
  def __init__(self, data: char[:]):
    self._hash = 0
    self._hash_ok = False
    n: int = len(data)
    self.data = new(n)
    for i in range(n):
      self.data[i] = data[i]
    data.reshape(0, 0)

  @overload
  def __init__(self, value: char):
    self._hash = 0
    self._hash_ok = False
    self.data = [value]

  def copy_to(self, buf: char[:], at: int = 0) -> int:
    """把本串码点写入 ``buf[at:]``，返回新尾下标。"""
    sn: int = len(self)
    if sn == 0:
      return at
    end: int = at + sn
    n: int = len(buf)
    if end > n:
      buf.reshape(end, n)
    for i in range(sn):
      buf[at + i] = self.data[i]
    return end

  def copy_slice_to(self, start: int, end: int, buf: char[:], at: int) -> int:
    """``self[start:end]`` 写入 ``buf[at:]``，返回新尾下标。"""
    n: int = end - start
    if n <= 0:
      return at
    need: int = at + n
    buf.reserve(need)
    seg: span[char] = self.data.view[start:end]
    for i in range(n):
      buf[at + i] = seg[i]
    return need

  @staticmethod
  @immutable
  def concat(parts: list[Self]) -> Self:
    return "".join(parts)

  def replace_slice(self, start: int, end: int, repl: Self) -> Self:
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
    new_len: int = start + rn + tail
    if new_len == 0:
      return ""
    if tail == 0 and rn == 0 and start == sn:
      return self
    buf: char[:] = new(new_len)
    at: int = 0
    if start > 0:
      head: span[char] = self.data.view[:start]
      for i in range(start):
        buf[at + i] = head[i]
      at = start
    if rn > 0:
      rview: span[char] = repl.data.view[:rn]
      for i in range(rn):
        buf[at + i] = rview[i]
      at += rn
    tail_n: int = sn - end
    if tail_n > 0:
      tview: span[char] = self.data.view[end:sn]
      for i in range(tail_n):
        buf[at + i] = tview[i]
      at += tail_n
    return Self.from_buf(buf, at)

  @staticmethod
  def from_buf_ref(buf: char[:], end: int) -> Self:
    """``buf[:end]`` → ``str``（纯 Python；``@native from_buf`` 的语义参照）。"""
    raw = str(buf)
    return raw[:end]

  @staticmethod
  @native
  def from_buf(buf: char[:], end: int) -> Self:
    """``buf[:end]`` → ``str``（encode ``finish`` 收尾）。"""
    ...

  @staticmethod
  @immutable
  def from_span(seg: span[char]) -> Self:
    """由 ``span[char]`` 拷贝构造（``copy_from_span`` 组合）。"""
    dst: Self = ""
    dst.copy_from_span(seg)
    return dst

  @overload
  def copy_from_span(self, seg: span[char]) -> None:
    """将 ``span[char]`` 写入已有 ``PyStr``（``copy_buf`` 叶子）。"""
    n: int = len(seg)
    if not n:
      self.data.reshape(0, 0)
      self._hash = 0
      self._hash_ok = True
      return
    if len(self.data) != n:
      self.data.reshape(n, 0)
    copy_buf(self.data.buf, seg.at(), n)
    self._hash = 0
    self._hash_ok = False

  @overload
  def copy_from_span(self, seg: span[byte]) -> None:
    """将 ``span[byte]`` 按 ``char`` 写入已有 ``PyStr``（C API / 单字节源）。"""
    n: int = len(seg)
    if not n:
      self.data.reshape(0, 0)
      self._hash = 0
      self._hash_ok = True
      return
    if len(self.data) != n:
      self.data.reshape(n, 0)
    for i in range(n):
      self.data[i] = char(seg[i])
    self._hash = 0
    self._hash_ok = False

  @immutable
  @overload
  def copy_to_span(self, dest: span[byte]) -> None:
    """把本串按单字节写入 ``dest`` 并以 ``\\0`` 收尾（``len(dest)`` 为容量上限；C API 缓冲）。"""
    cap: int = len(dest)
    if cap <= 0:
      return
    n: int = len(self)
    lim: int = n
    max_body: int = cap - 1
    if lim > max_body:
      lim = max_body
    for i in range(lim):
      dest[i] = byte(self[i])
    dest[lim] = byte(0)

  @immutable
  @overload
  def copy_to_span(self, dest: span[char]) -> None:
    """把码点写入 ``dest`` 并以 ``PyChar(0)`` 收尾（``len(dest)`` 为容量上限）。"""
    cap: int = len(dest)
    if cap <= 0:
      return
    n: int = len(self)
    lim: int = n
    max_body: int = cap - 1
    if lim > max_body:
      lim = max_body
    if lim > 0:
      copy_buf(dest.at(), self.data.buf, lim)
    dest[lim] = char(0)

  def adopt_span(self, seg: span[char]) -> None:
    """接管 ``span[char]`` 底层 ``char`` 缓冲（serde arena；勿与 ``reshape`` 混用）。"""
    self.data.adopt_span(seg)
    self._hash = 0
    self._hash_ok = False

  def __copy__(self, other: Self):
    n: int = len(other.data)
    if len(self.data) != n:
      self.data.reshape(n, 0)
    self.data.__copy__(other.data)
    self._hash = other._hash
    self._hash_ok = other._hash_ok

  @overload
  @native
  def __init__(self, value: int):
    ...

  @overload
  @native
  def __init__(self, value: int64):
    ...

  @overload
  @native
  def __init__(self, value: float):
    ...

  @overload
  @native
  def __init__(self, value: float64):
    ...

  @overload
  @native
  def __init__(self, value: bool):
    ...

  @immutable
  def __str__(self) -> Self:
    return self

  @immutable
  def __repr__(self) -> Self:
    out: Self = "'"
    n: int = len(self)
    for i in range(n):
      out += Self._repr_codepoint(self.data[i])
    return out + "'"

  @immutable
  def __format__(self, format_spec: Self) -> Self:
    return self

  def cache_hash(self, h: int) -> None:
    """由 ``JsonDecoder.load_key`` 等在已算好哈希时写入缓存（与 ``__hash__`` 算法一致）。"""
    self._hash = h
    self._hash_ok = True

  @immutable
  def _peek_hash(self) -> int:
    """只读哈希（``const`` 比较用）；已缓存则直接返回，否则现场计算不落盘。"""
    if self._hash_ok:
      return self._hash
    h: int = 0
    n: int = len(self.data)
    for i in range(n):
      h = h * 31 + self.data[i]
    return h

  def __hash__(self) -> int:
    """多项式哈希（惰性缓存），供 ``dict[str, …]`` 等。"""
    if self._hash_ok:
      return self._hash
    h: int = self._peek_hash()
    self._hash = h
    self._hash_ok = True
    return h

  @immutable
  def __eq__(self, other: Self) -> bool:
    na: int = len(self.data)
    nb: int = len(other.data)
    if na != nb:
      return False
    if na == 0:
      return True
    if self._hash_ok and other._hash_ok:
      if self._hash != other._hash:
        return False
    elif self._peek_hash() != other._peek_hash():
      return False
    return self._compare(other) == 0

  def __iter__(self) -> str_iterator:
    return new(self.data.view)

  def __reversed__(self) -> str_reverse_iterator:
    return new(self.data.view)

  @immutable
  def casefold(self) -> Self:
    return self.lower()

  @immutable
  def encode(self, encoding: c_str = "utf-8", errors: c_str = "strict") -> bytes:
    n: int = len(self)
    total: int = 0
    for i in range(n):
      total += Self._utf8_byte_len(self.data[i])
    if total == 0:
      empty: byte[:] = b""
      return bytes(empty)
    buf: byte[:] = new(total)
    at: int = 0
    for i in range(n):
      at = Self._write_utf8(buf, at, self.data[i])
    return bytes(buf)

  @immutable
  def isidentifier(self) -> bool:
    n: int = len(self)
    if n == 0:
      return False
    c0: char = self.data[0]
    if not (c0 in "_" or Self._is_alpha_char(c0)):
      return False
    for i in range(1, n):
      c: char = self.data[i]
      if not (c in "_" or Self._is_alnum_char(c)):
        return False
    return True

  @immutable
  def isnumeric(self) -> bool:
    return self.isdigit()

  @immutable
  def isprintable(self) -> bool:
    for i in range(len(self)):
      if not Self._is_printable_char(self.data[i]):
        return False
    return True

  @immutable
  def istitle(self) -> bool:
    return self.title() == self

  @native
  def format(self, *args) -> Self:
    ...

  @native
  def format_map(self, mapping) -> Self:
    ...
