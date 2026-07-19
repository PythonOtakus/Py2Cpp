"""bytes：不可变字节序列（``str.encode`` 等）。"""
from ..builtins import *
from .str import str
from ..util.dict import dict
from .mixins import StringMixin


@copyable
@native_name("PyBytes")
class bytes(StringMixin[byte]):
  """不可变字节序列（UTF-8 编码结果等）。"""

  _DELETE_BYTE: int @const = 0xFF

  @overload
  def __init__(self):
    self._data: byte[:] = b""

  @overload
  def __init__(self, data: byte[:]):
    self._data = data

  @overload
  def __init__(self, size: int):
    if size <= 0:
      self._data: byte[:] = b""
      return
    self._data: byte[:] = new(size)
    for i in range(size):
      self._data[i] = 0

  @overload
  def __init__(self, value: byte):
    self._data: byte[:] = new(1)
    self._data[0] = value

  def __copy__(self, other: Self):
    n: int = len(other._data)
    if len(self._data) != n:
      self._data.reshape(n, 0)
    self._data.__copy__(other._data)

  @immutable
  @staticmethod
  def _is_field_whitespace(b: byte) -> bool:
    return b in " \t\n\r\v\f"

  @immutable
  @staticmethod
  def _is_linebreak(b: byte) -> bool:
    return b in "\n\r\v\f"

  @immutable
  @staticmethod
  def _is_cr_lf_pair(cr: byte, lf: byte) -> bool:
    return cr == ord("\r") and lf == ord("\n")

  @staticmethod
  def _default_pad_char() -> byte:
    return 32

  @staticmethod
  def _zfill_pad_char() -> byte:
    return 48

  @immutable
  @staticmethod
  def _is_alnum_char(b: byte) -> bool:
    return Self._is_alpha_char(b) or Self._is_digit_char(b)

  @immutable
  @staticmethod
  def _is_alpha_char(b: byte) -> bool:
    if b >= ord("A") and b <= ord("Z"):
      return True
    if b >= ord("a") and b <= ord("z"):
      return True
    return False

  @immutable
  @staticmethod
  def _is_ascii(b: byte) -> bool:
    return b < 128

  @immutable
  @staticmethod
  def _is_cased(b: byte) -> bool:
    if b >= ord("A") and b <= ord("Z"):
      return True
    if b >= ord("a") and b <= ord("z"):
      return True
    return False

  @immutable
  @staticmethod
  def _is_digit_char(b: byte) -> bool:
    return b >= ord("0") and b <= ord("9")

  @immutable
  @staticmethod
  def _to_lower_char(b: byte) -> byte:
    if b >= ord("A") and b <= ord("Z"):
      return b + 32
    return b

  @immutable
  @staticmethod
  def _to_upper_char(b: byte) -> byte:
    if b >= ord("a") and b <= ord("z"):
      return b - 32
    return b

  @staticmethod
  def _translate_buf_len(n: int) -> int:
    return n

  @staticmethod
  def _translate_delete_marker() -> byte:
    return Self._DELETE_BYTE

  @immutable
  def decode(self, encoding: c_str = "utf-8", errors: c_str = "strict") -> str:
    n: int = len(self)
    if n == 0:
      return ""
    buf: char[:] = new(n)
    at: int = 0
    i: int = 0
    while i < n:
      b0: byte = self._data[i]
      if b0 < 0x80:
        buf[at] = b0
        at += 1
        i += 1
      elif b0 < 0xE0:
        if i + 1 >= n:
          break
        b1: byte = self._data[i + 1]
        buf[at] = ((b0 & 0x1F) << 6) | (b1 & 0x3F)
        at += 1
        i += 2
      elif b0 < 0xF0:
        if i + 2 >= n:
          break
        b1 = self._data[i + 1]
        b2: byte = self._data[i + 2]
        buf[at] = ((b0 & 0x0F) << 12) | ((b1 & 0x3F) << 6) | (b2 & 0x3F)
        at += 1
        i += 3
      else:
        if i + 3 >= n:
          break
        b1 = self._data[i + 1]
        b2 = self._data[i + 2]
        b3: byte = self._data[i + 3]
        cp: int = (
          ((b0 & 0x07) << 18)
          | ((b1 & 0x3F) << 12)
          | ((b2 & 0x3F) << 6)
          | (b3 & 0x3F)
        )
        buf[at] = cp
        at += 1
        i += 4
    if at == n:
      return str(buf)
    trimmed: char[:] = new(at)
    for k in range(at):
      trimmed[k] = buf[k]
    return str(trimmed)

  @immutable
  def __str__(self) -> str:
    return repr(self)

  @immutable
  def __repr__(self) -> str:
    out: str = "b'"
    n: int = len(self._data)
    for i in range(n):
      b: byte = self._data[i]
      if b == ord("'"):
        out += "\\'"
      elif b == ord("\\"):
        out += "\\\\"
      elif b >= ord(" ") and b <= ord("~"):
        ch: char = b
        buf: char[:] = [ch]
        out += str(buf)
      else:
        out += "."
    return out + "'"
