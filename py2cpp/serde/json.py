"""JSON 同质子集 + ``JsonEncoder`` / ``JsonDecoder``（``@serializable`` 默认后端）。

单文件：encode/decode 快路径为类方法；``load_u64_le`` 等叶子见 ``util/memory``，``span``→``str`` 用 ``str.from_span``。
"""
from __future__ import annotations

from ..builtins import *
from ..util.dict import dict
from ..util.list import list
from ..util.arena import Arena
from ..util.memory import (
  copy_buf,
  copy_buf_ref,
  load_u64_le,
)
from ..util.span import span
from ..core.exceptions import OSError, ValueError
from ..io.file import replace
from ..numeric.varint import varint
from ..io import StringIO, TextIOWrapper
from ..io.protocols import TextReader, TextWriter
from ..text import str


_EMPTY: str = ""
_JSON_KEY_TAG: str = "tag"
_JSON_KEY_PAYLOAD: str = "payload"

_ADD8: uint64 = 0x4646464646464646
_SUB8: uint64 = 0x3030303030303030
_MASK8: uint64 = 0x8080808080808080


class JSONDecodeError(ValueError):
  """JSON 解析失败。"""

  pass


@dataclass(eq=False)
class JsonEncoder:
  """JSON ``Encoder`` 实现；union 变体为 ``{"tag":…,"payload":{…}}``。

  默认在内部 ``char[:]`` 缓冲累积；``take()`` 移动取出 ``str``（``Json.dumps`` 快路径），
  ``finish()`` 经 ``str.from_buf`` 拷贝返回；``flush_to`` 直写 ``TextWriter``（``Json.dump``）。
  """

  sep: str = ""
  depth: int = 0
  indent: int = 0
  _buf: char[:] @optional = ""
  _at: int = 0

  def __repr__(self) -> str:
    return f"JsonEncoder(_at={self._at}, indent={self.indent})"

  def _pretty(self) -> bool:
    return self.indent > 0

  def _ensure(self, end: int) -> None:
    n: int = len(self._buf)
    if end <= n:
      return
    self._buf.reshape(end, n)

  def grow_buf(self, end: int) -> None:
    """预扩容内部 ``char[:]`` 缓冲（``end`` 为目标 ``_at`` 上界）。"""
    self._ensure(end)

  def push(self, piece: str) -> None:
    """追加 JSON 片段到内部 ``char[:]`` 缓冲。"""
    if not piece:
      return
    end: int = self._at + len(piece)
    self._ensure(end)
    self._at = piece.copy_to(self._buf, self._at)

  def _strip_trailing_comma(self) -> None:
    if self._at > 0 and self._buf[self._at - 1] == ord(","):
      self._at -= 1

  def _newline_indent(self) -> str:
    if not self._pretty():
      return ""
    n: int = self.depth * self.indent
    pad_parts: list[str] = []
    for _ in range(n):
      pad_parts.append(" ")
    return "\n" + str.concat(pad_parts)

  def _comma_sep(self) -> str:
    if not self._pretty():
      return ","
    return "," + self._newline_indent()

  def comma_sep(self) -> str:
    return self._comma_sep()

  @staticmethod
  @immutable
  def encode_str(s: str) -> str:
    parts: list[str] = ['"']
    n: int = len(s)
    for i in range(n):
      if s[i] in '"':
        parts.append('\\"')
      elif s[i] in "\\":
        parts.append("\\\\")
      elif s[i] in "\n":
        parts.append("\\n")
      elif s[i] in "\r":
        parts.append("\\r")
      elif s[i] in "\t":
        parts.append("\\t")
      elif s[i] < ord(" "):
        parts.append("?")
      else:
        parts.append(s[i : i + 1])
    parts.append('"')
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encode_bool(obj: bool) -> str:
    if obj:
      return "true"
    return "false"

  @staticmethod
  @immutable
  def _encode_float(obj: float) -> str:
    return str(obj)

  @staticmethod
  @immutable
  def _encode_int(obj: int) -> str:
    if obj == 0:
      return "0"
    neg: bool = obj < 0
    n: int = obj
    if neg:
      n = -n
    digits: list[int] = []
    while n > 0:
      digits.append(n % 10)
      n //= 10
    buf: char[:] = new(len(digits) + 1)
    at: int = 0
    if neg:
      buf[at] = ord("-")
      at += 1
    for i in range(len(digits) - 1, -1, -1):
      buf[at] = ord("0") + digits[i]
      at += 1
    return str(buf)[:at]

  @staticmethod
  @immutable
  def _encode_list_int(obj: list[int]) -> str:
    parts: list[str] = ["["]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      parts.append(Self._encode_int(obj[i]))
    parts.append("]")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encode_list_varint(obj: list[varint]) -> str:
    parts: list[str] = ["["]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      parts.append(str(obj[i]))
    parts.append("]")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encode_list_float(obj: list[float]) -> str:
    parts: list[str] = ["["]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      parts.append(Self._encode_float(obj[i]))
    parts.append("]")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encode_list_str(obj: list[str]) -> str:
    parts: list[str] = ["["]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      parts.append(Self.encode_str(obj[i]))
    parts.append("]")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encode_dict_str_int(obj: dict[str, int]) -> str:
    parts: list[str] = ["{"]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      k: str = obj.key_at(i)
      parts.append(Self.encode_str(k))
      parts.append(":")
      parts.append(Self._encode_int(obj.value_at(i)))
    parts.append("}")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encode_dict_str_varint(obj: dict[str, varint]) -> str:
    parts: list[str] = ["{"]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      k: str = obj.key_at(i)
      parts.append(Self.encode_str(k))
      parts.append(":")
      parts.append(str(obj.value_at(i)))
    parts.append("}")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encode_dict_str_float(obj: dict[str, float]) -> str:
    parts: list[str] = ["{"]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      k: str = obj.key_at(i)
      parts.append(Self.encode_str(k))
      parts.append(":")
      parts.append(Self._encode_float(obj.value_at(i)))
    parts.append("}")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encode_dict_str_str(obj: dict[str, str]) -> str:
    parts: list[str] = ["{"]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      k: str = obj.key_at(i)
      parts.append(Self.encode_str(k))
      parts.append(":")
      parts.append(Self.encode_str(obj.value_at(i)))
    parts.append("}")
    return str.concat(parts)

  def begin_object(self) -> None:
    if not self._pretty():
      if self.depth == 0:
        if self._at == 0:
          self._ensure(1)
          self._buf[self._at] = ord("{")
          self._at += 1
        else:
          if self.sep:
            self.push(self.sep)
          self._ensure(self._at + 1)
          self._buf[self._at] = ord("{")
          self._at += 1
          self.sep = ""
      else:
        if self.sep:
          self.push(self.sep)
        self._ensure(self._at + 1)
        self._buf[self._at] = ord("{")
        self._at += 1
        self.sep = ""
      self.depth += 1
      return
    if self.depth == 0:
      if self._at == 0:
        self.push("{")
      else:
        self.push(self.sep)
        self.push("{")
        self.sep = ""
    else:
      self.push(self.sep)
      self.push("{")
      self.sep = ""
    self.depth += 1
    if self._pretty():
      self.sep = self._newline_indent()

  def end_object(self) -> None:
    self.depth -= 1
    if not self._pretty():
      if self.depth > 0:
        self._strip_trailing_comma()
      self._ensure(self._at + 1)
      self._buf[self._at] = ord("}")
      self._at += 1
      if self.depth > 0:
        self.sep = ","
      return
    if self._pretty():
      self.push(self._newline_indent())
    elif self.depth > 0:
      self._strip_trailing_comma()
    self.push("}")
    if self.depth > 0:
      self.sep = self._comma_sep()

  def begin_array(self) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      self._ensure(self._at + 1)
      self._buf[self._at] = ord("[")
      self._at += 1
      self.sep = ""
      self.depth += 1
      return
    self.push(self.sep)
    self.push("[")
    self.sep = ""
    self.depth += 1
    if self._pretty():
      self.sep = self._newline_indent()

  def end_array(self) -> None:
    self.depth -= 1
    if not self._pretty():
      if self.depth > 0:
        self._strip_trailing_comma()
      self._ensure(self._at + 1)
      self._buf[self._at] = ord("]")
      self._at += 1
      self.sep = ","
      return
    if self._pretty():
      self.push(self._newline_indent())
    elif self.depth > 0:
      self._strip_trailing_comma()
    self.push("]")
    self.sep = self._comma_sep()

  def dump_key(self, name: str) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      end: int = self._at + len(name) * 2 + 3
      self._ensure(end)
      self._at = Self.append_quoted_at(self._buf, self._at, name)
      self._buf[self._at] = ord(":")
      self._at += 1
      self.sep = ""
      return
    colon: str = ": "
    self.push(self.sep)
    self.push(Self.encode_str(name))
    self.push(colon)
    self.sep = ""

  def dump_int(self, value: int) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      self._ensure(self._at + 24)
      self._at = Self.append_int_at(self._buf, self._at, value)
      self.sep = ","
      return
    self.push(self.sep)
    self.push(Self._encode_int(value))
    self.sep = self._comma_sep()

  def dump_varint(self, value: varint) -> None:
    if self.sep:
      self.push(self.sep)
    self.push(str(value))
    self.sep = "," if not self._pretty() else self._comma_sep()

  def dump_float(self, value: float) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      self.push(str(value))
      self.sep = ","
      return
    self.push(self.sep)
    self.push(Self._encode_float(value))
    self.sep = self._comma_sep()

  def dump_bool(self, value: bool) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      self._ensure(self._at + 5)
      if value:
        self._buf[self._at] = ord("t")
        self._at += 1
        self._buf[self._at] = ord("r")
        self._at += 1
        self._buf[self._at] = ord("u")
        self._at += 1
        self._buf[self._at] = ord("e")
        self._at += 1
      else:
        self._buf[self._at] = ord("f")
        self._at += 1
        self._buf[self._at] = ord("a")
        self._at += 1
        self._buf[self._at] = ord("l")
        self._at += 1
        self._buf[self._at] = ord("s")
        self._at += 1
        self._buf[self._at] = ord("e")
        self._at += 1
      self.sep = ","
      return
    self.push(self.sep)
    self.push(Self._encode_bool(value))
    self.sep = self._comma_sep()

  def dump_str(self, value: str) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      end: int = self._at + len(value) * 2 + 3
      self._ensure(end)
      self._at = Self.append_quoted_at(self._buf, self._at, value)
      self.sep = ","
      return
    self.push(self.sep)
    self.push(Self.encode_str(value))
    self.sep = self._comma_sep()

  def dump_field_int(self, key: str, value: int) -> None:
    if self._pretty():
      self.dump_key(key)
      self.dump_int(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.append_quoted_at(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    self._at = Self.append_int_at(self._buf, self._at, value)
    self.sep = ","

  def dump_field_varint(self, key: str, value: varint) -> None:
    if self._pretty():
      self.dump_key(key)
      self.dump_varint(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.append_quoted_at(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    self._at = str(value).copy_to(self._buf, self._at)
    self.sep = ","

  def dump_field_str(self, key: str, value: str) -> None:
    if self._pretty():
      self.dump_key(key)
      self.dump_str(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.append_quoted_at(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    self._at = Self.append_quoted_at(self._buf, self._at, value)
    self.sep = ","

  def dump_field_bool(self, key: str, value: bool) -> None:
    if self._pretty():
      self.dump_key(key)
      self.dump_bool(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.append_quoted_at(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    self._ensure(self._at + 5)
    if value:
      self._buf[self._at] = ord("t")
      self._at += 1
      self._buf[self._at] = ord("r")
      self._at += 1
      self._buf[self._at] = ord("u")
      self._at += 1
      self._buf[self._at] = ord("e")
      self._at += 1
    else:
      self._buf[self._at] = ord("f")
      self._at += 1
      self._buf[self._at] = ord("a")
      self._at += 1
      self._buf[self._at] = ord("l")
      self._at += 1
      self._buf[self._at] = ord("s")
      self._at += 1
      self._buf[self._at] = ord("e")
      self._at += 1
    self.sep = ","

  def dump_field_list_int(self, key: str, value: list[int]) -> None:
    if self._pretty():
      self.dump_key(key)
      self.dump_list_int(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.append_quoted_at(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.append_list_at(self._buf, self._at, value)
    self.sep = ","

  def dump_field_list_str(self, key: str, value: list[str]) -> None:
    if self._pretty():
      self.dump_key(key)
      self.dump_list_str(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.append_quoted_at(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.append_list_at(self._buf, self._at, value)
    self.sep = ","

  def dump_field_list_float(self, key: str, value: list[float]) -> None:
    if self._pretty():
      self.dump_key(key)
      self.dump_list_float(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.append_quoted_at(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.append_list_at(self._buf, self._at, value)
    self.sep = ","

  def dump_field_list_varint(self, key: str, value: list[varint]) -> None:
    if self._pretty():
      self.dump_key(key)
      self.dump_list_varint(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.append_quoted_at(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.append_list_varint_at(self._buf, self._at, value)
    self.sep = ","

  def dump_list_int(self, value: list[int]) -> None:
    if self.sep:
      self.push(self.sep)
    if self._pretty():
      self.push(Self._encode_list_int(value))
      self.sep = self._comma_sep()
      return
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.append_list_at(self._buf, self._at, value)
    self.sep = ","

  def dump_list_float(self, value: list[float]) -> None:
    if self.sep:
      self.push(self.sep)
    if self._pretty():
      self.push(Self._encode_list_float(value))
      self.sep = self._comma_sep()
      return
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.append_list_at(self._buf, self._at, value)
    self.sep = ","

  def dump_list_varint(self, value: list[varint]) -> None:
    if self.sep:
      self.push(self.sep)
    if self._pretty():
      self.push(Self._encode_list_varint(value))
      self.sep = self._comma_sep()
      return
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.append_list_varint_at(self._buf, self._at, value)
    self.sep = ","

  def dump_list_str(self, value: list[str]) -> None:
    if self.sep:
      self.push(self.sep)
    if self._pretty():
      self.push(Self._encode_list_str(value))
      self.sep = self._comma_sep()
      return
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.append_list_at(self._buf, self._at, value)
    self.sep = ","

  def dump_dict_str_int(self, value: dict[str, int]) -> None:
    self.push(self.sep)
    if self._pretty():
      self.push(Self._encode_dict_str_int(value))
    else:
      self.push(Self.fast_encode(value))
    self.sep = self._comma_sep()

  def dump_dict_str_varint(self, value: dict[str, varint]) -> None:
    self.push(self.sep)
    if self._pretty():
      self.push(Self._encode_dict_str_varint(value))
    else:
      self.push(Self.fast_encode(value))
    self.sep = self._comma_sep()

  def dump_dict_str_str(self, value: dict[str, str]) -> None:
    self.push(self.sep)
    if self._pretty():
      self.push(Self._encode_dict_str_str(value))
    else:
      self.push(Self.fast_encode(value))
    self.sep = self._comma_sep()

  def dump_dict_str_float(self, value: dict[str, float]) -> None:
    self.push(self.sep)
    if self._pretty():
      self.push(Self._encode_dict_str_float(value))
    else:
      self.push(Self.fast_encode(value))
    self.sep = self._comma_sep()

  def begin_variant(self, tag: str) -> None:
    self.begin_object()
    self.dump_field_str(_JSON_KEY_TAG, tag)
    self.dump_key(_JSON_KEY_PAYLOAD)
    self.begin_object()

  def end_variant(self) -> None:
    self.end_object()
    self.end_object()

  def finish(self) -> str:
    if self._at == 0:
      return ""
    return str.from_buf(self._buf, self._at)

  def take(self) -> str:
    """移动取出内部 ``char[:]`` 为 ``str``（``finish`` 的无拷贝路径）。"""
    if self._at == 0:
      return ""
    n: int = len(self._buf)
    if self._at < n:
      self._buf.reshape(self._at, n)
    self._at = 0
    return str(self._buf)

  @overload
  def flush_to(self, fp: StringIO) -> None:
    if self._at == 0:
      return
    fp.write(self._buf, self._at)

  @overload
  def flush_to(self, fp: TextIOWrapper) -> None:
    if self._at == 0:
      return
    fp.write(self._buf, self._at)

  @staticmethod
  def append_int_at(buf: char[:], at: int, obj: int) -> int:
    """十进制 ``int`` → ``buf[at:]``，返回新尾下标（JSON 紧凑路径语义）。"""
    if obj == 0:
      buf.reserve(at + 1)
      buf[at] = ord("0")
      return at + 1
    neg: bool = obj < 0
    n: int = obj
    if neg:
      n = -n
    digits: list[int] = []
    while n > 0:
      digits.append(n % 10)
      n //= 10
    dn: int = len(digits)
    extra: int = 1 if neg else 0
    buf.reserve(at + dn + extra)
    wi: int = at
    if neg:
      buf[wi] = ord("-")
      wi += 1
    for i in range(dn - 1, -1, -1):
      buf[wi] = ord("0") + digits[i]
      wi += 1
    return wi


  @staticmethod
  def append_quoted_at(buf: char[:], at: int, s: str) -> int:
    """JSON 引号字符串 → ``buf[at:]``（紧凑 encode 子集）。"""
    sn: int = len(s)
    est: int = at + (sn * 2) + 2
    buf.reserve(est)
    buf[at] = ord('"')
    at += 1
    for i in range(sn):
      c: char = s[i]
      if c in '"':
        buf.reserve(at + 2)
        buf[at] = ord("\\")
        at += 1
        buf[at] = ord('"')
        at += 1
      elif c in "\\":
        buf.reserve(at + 2)
        buf[at] = ord("\\")
        at += 1
        buf[at] = ord("\\")
        at += 1
      elif c in "\n":
        buf.reserve(at + 2)
        buf[at] = ord("\\")
        at += 1
        buf[at] = ord("n")
        at += 1
      elif c in "\r":
        buf.reserve(at + 2)
        buf[at] = ord("\\")
        at += 1
        buf[at] = ord("r")
        at += 1
      elif c in "\t":
        buf.reserve(at + 2)
        buf[at] = ord("\\")
        at += 1
        buf[at] = ord("t")
        at += 1
      elif c < ord(" "):
        buf.reserve(at + 1)
        buf[at] = ord("?")
        at += 1
      else:
        buf.reserve(at + 1)
        buf[at] = c
        at += 1
    buf.reserve(at + 1)
    buf[at] = ord('"')
    at += 1
    return at


  @staticmethod
  def append_varint_at(buf: char[:], at: int, obj: varint) -> int:
    """``varint`` 十进制文本 → ``buf[at:]``（``str(obj)`` 语义）。"""
    return str(obj).copy_to(buf, at)


  @staticmethod
  def append_float_at(buf: char[:], at: int, obj: float) -> int:
    """``float`` 文本 → ``buf[at:]``（``str(obj)`` 语义）。"""
    return str(obj).copy_to(buf, at)


  @staticmethod
  def append_list_int_at(buf: char[:], at: int, obj: list[int]) -> int:
    """JSON ``list[int]`` → ``buf[at:]``，返回新尾下标。"""
    cnt: int = len(obj)
    buf.reserve(at + (cnt * 12) + 2)
    buf[at] = ord("[")
    at += 1
    for i in range(cnt):
      if i > 0:
        buf[at] = ord(",")
        at += 1
      at = Self.append_int_at(buf, at, obj[i])
    buf[at] = ord("]")
    at += 1
    return at


  @staticmethod
  def append_list_str_at(buf: char[:], at: int, obj: list[str]) -> int:
    """JSON ``list[str]`` → ``buf[at:]``，返回新尾下标。"""
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      est += (len(obj[i]) * 2) + 3
    buf.reserve(est)
    buf[at] = ord("[")
    at += 1
    for i in range(cnt):
      if i > 0:
        buf[at] = ord(",")
        at += 1
      at = Self.append_quoted_at(buf, at, obj[i])
    buf[at] = ord("]")
    at += 1
    return at


  @staticmethod
  def append_list_float_at(buf: char[:], at: int, obj: list[float]) -> int:
    """JSON ``list[float]`` → ``buf[at:]``，返回新尾下标。"""
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      est += len(str(obj[i])) + 1
    buf.reserve(est)
    buf[at] = ord("[")
    at += 1
    for i in range(cnt):
      if i > 0:
        buf[at] = ord(",")
        at += 1
      at = Self.append_float_at(buf, at, obj[i])
    buf[at] = ord("]")
    at += 1
    return at


  @staticmethod
  def append_list_varint_at(buf: char[:], at: int, obj: list[varint]) -> int:
    """JSON ``list[varint]`` → ``buf[at:]``，返回新尾下标。"""
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      est += len(str(obj[i])) + 1
    buf.reserve(est)
    buf[at] = ord("[")
    at += 1
    for i in range(cnt):
      if i > 0:
        buf[at] = ord(",")
        at += 1
      at = Self.append_varint_at(buf, at, obj[i])
    buf[at] = ord("]")
    at += 1
    return at


  @staticmethod
  @overload
  @staticmethod
  def append_list_at(buf: char[:], at: int, obj: list[int]) -> int:
    return Self.append_list_int_at(buf, at, obj)


  @staticmethod
  @overload
  @staticmethod
  def append_list_at(buf: char[:], at: int, obj: list[str]) -> int:
    return Self.append_list_str_at(buf, at, obj)


  @staticmethod
  @overload
  @staticmethod
  def append_list_at(buf: char[:], at: int, obj: list[float]) -> int:
    return Self.append_list_float_at(buf, at, obj)


  @staticmethod
  def _append_dict_str_int_at(buf: char[:], at: int, obj: dict[str, int]) -> int:
    cnt: int = len(obj)
    buf.reserve(at + (cnt * 32) + 2)
    buf[at] = ord("{")
    at += 1
    first: bool = True
    for i in range(cnt):
      if not first:
        buf[at] = ord(",")
        at += 1
      first = False
      k: str = obj.key_at(i)
      at = Self.append_quoted_at(buf, at, k)
      buf[at] = ord(":")
      at += 1
      at = Self.append_int_at(buf, at, obj.value_at(i))
    buf[at] = ord("}")
    at += 1
    return at


  @staticmethod
  def _append_dict_str_str_at(buf: char[:], at: int, obj: dict[str, str]) -> int:
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      k: str = obj.key_at(i)
      v: str = obj.value_at(i)
      est += (len(k) * 2) + (len(v) * 2) + 5
    buf.reserve(est)
    buf[at] = ord("{")
    at += 1
    first: bool = True
    for i in range(cnt):
      if not first:
        buf[at] = ord(",")
        at += 1
      first = False
      k: str = obj.key_at(i)
      at = Self.append_quoted_at(buf, at, k)
      buf[at] = ord(":")
      at += 1
      at = Self.append_quoted_at(buf, at, obj.value_at(i))
    buf[at] = ord("}")
    at += 1
    return at


  @staticmethod
  def _append_dict_str_varint_at(buf: char[:], at: int, obj: dict[str, varint]) -> int:
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      k: str = obj.key_at(i)
      est += (len(k) * 2) + len(str(obj.value_at(i))) + 5
    buf.reserve(est)
    buf[at] = ord("{")
    at += 1
    first: bool = True
    for i in range(cnt):
      if not first:
        buf[at] = ord(",")
        at += 1
      first = False
      k: str = obj.key_at(i)
      at = Self.append_quoted_at(buf, at, k)
      buf[at] = ord(":")
      at += 1
      at = Self.append_varint_at(buf, at, obj.value_at(i))
    buf[at] = ord("}")
    at += 1
    return at


  @staticmethod
  def _append_dict_str_float_at(buf: char[:], at: int, obj: dict[str, float]) -> int:
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      k: str = obj.key_at(i)
      est += (len(k) * 2) + len(str(obj.value_at(i))) + 5
    buf.reserve(est)
    buf[at] = ord("{")
    at += 1
    first: bool = True
    for i in range(cnt):
      if not first:
        buf[at] = ord(",")
        at += 1
      first = False
      k: str = obj.key_at(i)
      at = Self.append_quoted_at(buf, at, k)
      buf[at] = ord(":")
      at += 1
      at = Self.append_float_at(buf, at, obj.value_at(i))
    buf[at] = ord("}")
    at += 1
    return at
  @staticmethod
  @overload
  @staticmethod
  def fast_encode(obj: list[int]) -> str:
    cnt: int = len(obj)
    buf: char[:] = new((cnt * 12) + 2)
    at: int = Self.append_list_int_at(buf, 0, obj)
    return str.from_buf(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fast_encode(obj: list[str]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      est += (len(obj[i]) * 2) + 3
    buf: char[:] = new(est)
    at: int = Self.append_list_str_at(buf, 0, obj)
    return str.from_buf(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fast_encode(obj: list[float]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      est += len(str(obj[i])) + 1
    buf: char[:] = new(est)
    at: int = Self.append_list_float_at(buf, 0, obj)
    return str.from_buf(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fast_encode(obj: list[varint]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      est += len(str(obj[i])) + 1
    buf: char[:] = new(est)
    at: int = Self.append_list_varint_at(buf, 0, obj)
    return str.from_buf(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fast_encode(obj: dict[str, int]) -> str:
    cnt: int = len(obj)
    buf: char[:] = new((cnt * 32) + 2)
    at: int = Self._append_dict_str_int_at(buf, 0, obj)
    return str.from_buf(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fast_encode(obj: dict[str, str]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      k: str = obj.key_at(i)
      v: str = obj.value_at(i)
      est += (len(k) * 2) + (len(v) * 2) + 5
    buf: char[:] = new(est)
    at: int = Self._append_dict_str_str_at(buf, 0, obj)
    return str.from_buf(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fast_encode(obj: dict[str, varint]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      k: str = obj.key_at(i)
      est += (len(k) * 2) + len(str(obj.value_at(i))) + 5
    buf: char[:] = new(est)
    at: int = Self._append_dict_str_varint_at(buf, 0, obj)
    return str.from_buf(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fast_encode(obj: dict[str, float]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      k: str = obj.key_at(i)
      est += (len(k) * 2) + len(str(obj.value_at(i))) + 5
    buf: char[:] = new(est)
    at: int = Self._append_dict_str_float_at(buf, 0, obj)
    return str.from_buf(buf, at)


@copyable
@dataclass(eq=False, repr=False)
class JsonDecoder:
  """JSON ``Decoder`` 实现；游标保存在 ``pos``。"""

  s: str = ""
  pos: int = 0
  ascii_bind_done: bool = False
  ascii_ok: bool = False
  ascii_len: int = 0
  ascii_bytes: Pointer[char] = None
  ascii_bytes_owned: bool = False
  str_arena: Arena = new()
  str_arena_active: bool = False

  def __repr__(self) -> str:
    return f"JsonDecoder(s={self.s!r}, pos={self.pos})"

  def __copy__(self, other: Self):
    self.s = other.s
    self.pos = other.pos
    self.ascii_bind_done = False
    self.ascii_ok = False
    self.ascii_len = 0
    self.ascii_bytes = None
    self.ascii_bytes_owned = False
    self.str_arena.reset()
    self.str_arena_active = False

  @staticmethod
  @immutable
  def _is_ws_byte(c: int) -> bool:
    return c in {9, 10, 13, 32}

  @staticmethod
  @immutable
  def _chunk_byte(chunk: uint64, k: int) -> int:
    sh: uint64 = k * 8
    return int((chunk >> sh) & 0xFF)

  @staticmethod
  @immutable
  def _chunk_all_ws(chunk: uint64) -> bool:
    for k in range(8):
      if not Self._is_ws_byte(Self._chunk_byte(chunk, k)):
        return False
    return True

  @staticmethod
  @immutable
  def _swar_is8digits(chunk: uint64) -> bool:
    t: uint64 = ((chunk + _ADD8) | (chunk - _SUB8)) & _MASK8
    return not t

  @staticmethod
  @immutable
  def _swar_parse8(chunk: uint64) -> int:
    mask: uint64 = 0x000000FF000000FF
    mul1: uint64 = 0x000F424000000064
    mul2: uint64 = 0x0000271000000001
    a: uint64 = (chunk & mask) * mul1
    b: uint64 = ((chunk >> 8) & mask) * mul1
    a = (a + b) >> 32
    a = (a & mask) * mul2
    b = ((a >> 16) & mask) * mul2
    return int((a + b) >> 32)

  def fail(self, msg: str) -> int:
    raise JSONDecodeError()

  def try_bind_ascii(self) -> None:
    """尝试绑定 ASCII 字节视图（纯 Python；``ord`` / ``src_char`` 译后内联）。"""
    if self.ascii_bind_done:
      return
    self.ascii_bind_done = True
    n: int = self.src_len()
    if n <= 0:
      return
    for i in range(n):
      c: char = self.src_char(i)
      if int(c) < 0 or int(c) > 127:
        self.ascii_ok = False
        return
    self.ascii_bytes = self.s.view.at(0)
    self.ascii_bytes_owned = False
    self.ascii_len = n
    self.ascii_ok = True

  def release_ascii(self) -> None:
    """释放 ASCII 视图标志。"""
    self.ascii_ok = False
    self.ascii_bind_done = False
    self.ascii_len = 0
    self.ascii_bytes = None
    self.ascii_bytes_owned = False

  def skip_ws(self) -> None:
    """跳过 JSON 空白（``_skip_ws`` 公开入口）。"""
    self._skip_ws()

  def _skip_ws(self) -> None:
    src: span[char] = self.src_view()
    n: int = len(src)
    for j in range(self.pos, n):
      if src[j] not in "\t\n\r ":
        self.pos = j
        return
    self.pos = n

  def expect_char(self, ch: str) -> None:
    if self.pos >= len(self.s) or self.s[self.pos] not in ch:
      self.fail("unexpected char")
    self.pos += 1

  def _parse_string_value(self, out: list[str] @ref) -> None:
    self._skip_ws()
    if self.pos >= len(self.s) or self.s[self.pos] not in '"':
      self.fail("expected string")
    self.pos += 1
    parts: list[str] = []
    while self.pos < len(self.s):
      if self.s[self.pos] in '"':
        out.append(_EMPTY.join(parts))
        self.pos += 1
        return
      if self.s[self.pos] in "\\":
        self.pos += 1
        if self.pos >= len(self.s):
          self.fail("bad escape")
        esc: char = self.s[self.pos]
        match esc:
          case '"':
            parts.append('"')
          case '\\':
            parts.append("\\")
          case 'n':
            parts.append("\n")
          case 'r':
            parts.append("\r")
          case 't':
            parts.append("\t")
          case _:
            self.fail("bad escape")
        self.pos += 1
        continue
      parts.append(self.s[self.pos : self.pos + 1])
      self.pos += 1
    self.fail("unterminated string")

  def _scan_json_number(self, start_out: list[int] @ref, end_out: list[int] @ref) -> None:
    """写入数字 token 的 ``[start, end)``（``end`` 为首个非数字字符下标）。"""
    self._skip_ws()
    i: int = self.pos
    if i >= len(self.s):
      self.fail("expected number")
    start: int = i
    if self.s[i] in "-":
      i += 1
    if i >= len(self.s):
      self.fail("expected digit")
    if self.s[i] not in "0123456789":
      self.fail("expected digit")
    for j in range(i, len(self.s)):
      if self.s[j] not in "0123456789":
        break
      i = j + 1
    if i < len(self.s) and self.s[i] in ".":
      i += 1
      if i >= len(self.s):
        self.fail("expected digit")
      if self.s[i] not in "0123456789":
        self.fail("expected digit")
      for j in range(i, len(self.s)):
        if self.s[j] not in "0123456789":
          break
        i = j + 1
    if i < len(self.s) and self.s[i] in "eE":
      i += 1
      if i < len(self.s) and self.s[i] in "+-":
        i += 1
      if i >= len(self.s):
        self.fail("expected digit")
      if self.s[i] not in "0123456789":
        self.fail("expected digit")
      for j in range(i, len(self.s)):
        if self.s[j] not in "0123456789":
          break
        i = j + 1
    start_out.append(start)
    end_out.append(i)
    self.pos = i

  def _parse_int_value(self, out: list[int] @ref) -> None:
    start_out: list[int] = []
    end_out: list[int] = []
    self._scan_json_number(start_out, end_out)
    start: int = start_out[0]
    end: int = end_out[0]
    for j in range(start, end):
      if self.s[j] in ".eE":
        self.fail("expected int")
    tok: str = self.s[start:end]
    out.append(int(tok))

  def _parse_varint_value(self, out: list[varint] @ref) -> None:
    start_out: list[int] = []
    end_out: list[int] = []
    self._scan_json_number(start_out, end_out)
    start: int = start_out[0]
    end: int = end_out[0]
    for j in range(start, end):
      if self.s[j] in ".eE":
        self.fail("expected int")
    tok: str = self.s[start:end]
    out.append(varint(tok))

  def _parse_float_value(self, out: list[float] @ref) -> None:
    start_out: list[int] = []
    end_out: list[int] = []
    self._scan_json_number(start_out, end_out)
    start: int = start_out[0]
    end: int = end_out[0]
    tok: str = self.s[start:end]
    out.append(float(tok))

  def _skip_number_value(self) -> None:
    _buf: list[float] = []
    self._parse_float_value(_buf)

  def _parse_bool_value(self, out: list[bool] @ref) -> None:
    self._skip_ws()
    if self.pos + 4 <= len(self.s) and self.s[self.pos : self.pos + 4] == "true":
      out.append(True)
      self.pos += 4
      return
    if self.pos + 5 <= len(self.s) and self.s[self.pos : self.pos + 5] == "false":
      out.append(False)
      self.pos += 5
      return
    self.fail("expected bool")

  def _skip_string_value(self) -> None:
    """跳过 JSON 字符串字面量（不构造 ``str``，``skip_value`` / 数组导航热路径）。"""
    if self.pos >= len(self.s) or self.s[self.pos] not in '"':
      self.fail("expected string")
    self.pos += 1
    n: int = len(self.s)
    while self.pos < n:
      c: char = self.s[self.pos]
      if c in '"':
        self.pos += 1
        return
      if c in "\\":
        self.pos += 2
        continue
      self.pos += 1
    self.fail("unterminated string")

  def _skip_value(self) -> None:
    if self.try_skip_value_ascii():
      return
    self._skip_ws()
    if self.pos >= len(self.s):
      self.fail("empty input")
    ch: char = self.s[self.pos]
    match ch:
      case '"':
        self._skip_string_value()
        return
      case 't':
        _skip_bb: list[bool] = []
        self._parse_bool_value(_skip_bb)
        return
      case 'f':
        _skip_bf: list[bool] = []
        self._parse_bool_value(_skip_bf)
        return
      case 'n':
        if self.pos + 4 <= len(self.s) and self.s[self.pos : self.pos + 4] == "null":
          self.pos += 4
          return
        self.fail("expected null")
      case '-' | '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9':
        self._skip_number_value()
        return
      case '[':
        depth: int = 0
        for _ in range(len(self.s)):
          if self.pos >= len(self.s):
            break
          ch_arr: char = self.s[self.pos]
          match ch_arr:
            case '[':
              depth += 1
            case ']':
              depth -= 1
              if depth == 0:
                self.pos += 1
                return
            case '"':
              self._skip_string_value()
              continue
            case _:
              pass
          self.pos += 1
        self.fail("unterminated array")
      case '{':
        depth2: int = 0
        for _ in range(len(self.s)):
          if self.pos >= len(self.s):
            break
          ch_obj: char = self.s[self.pos]
          match ch_obj:
            case '{':
              depth2 += 1
            case '}':
              depth2 -= 1
              if depth2 == 0:
                self.pos += 1
                return
            case '"':
              self._skip_string_value()
              continue
            case _:
              pass
          self.pos += 1
        self.fail("unterminated object")
      case _:
        self.fail("bad value")

  @staticmethod
  def from_text(text: str) -> Self:
    dec: Self = new()
    dec.s = text
    dec.pos = 0
    return dec

  def src_view(self) -> span[char]:
    """输入 ``s`` 码点只读视图（``serde`` 热路径）。"""
    return self.s.view

  def src_len(self) -> int:
    """``src_view`` 长度（供生成 C++ 快路径，勿经 ``PyStr.__getitem__``）。"""
    return len(self.src_view())

  def src_char(self, i: int) -> char:
    """``_src_view[i]``（``i`` 与 ``pos`` 同属输入 ``s``）。"""
    return self.src_view()[i]

  def src_ascii_ok(self) -> bool:
    """输入是否已绑定紧凑 ASCII 字节视图（仅 ``loads`` 热路径 C++ 使用）。"""
    return self.ascii_ok

  def enable_str_arena(self) -> None:
    """``loads`` 热路径：按需启用 ``str_arena``（纯 ``int``/``list[int]`` 等勿调用）。"""
    self.str_arena_active = True
    sl: int = self.src_len()
    if sl > 0:
      self.str_arena.reserve(sl // 2)

  def mark(self) -> int:
    return self.pos

  def restore(self, m: int) -> None:
    self.pos = m

  def _slice_at(self, start: int, end: int) -> span[char]:
    """半开区间 ``[start, end)``，下标与 ``pos`` 同属 ``s``。"""
    return self.src_view()[start:end]

  def skip_empty_array(self) -> None:
    """假定游标已在 ``[``；若为 ``[]`` 则跳过并返回。"""
    self._skip_ws()
    n: int = self.src_len()
    if self.pos < n and self.src_char(self.pos) in "[":
      if self.pos + 1 < n and self.src_char(self.pos + 1) in "]":
        self.pos += 2
        return
    self.fail("expected empty array")

  def load_str_span(self) -> span[char]:
    """无转义 JSON 字符串：返回码点视图；有转义则物化后取其 ``codes.view``。"""
    self._skip_ws()
    return self._load_str_span_bound()

  def _load_str_span_bound(self) -> span[char]:
    return self.load_str_span_ascii()

  def skip_spaces(self) -> None:
    self._skip_ws()

  def read_quoted(self) -> str:
    buf: list[str] = []
    self._parse_string_value(buf)
    return buf[0]

  def begin_root_object(self) -> None:
    self._skip_ws()
    self.expect_char("{")

  def try_match_key(self, expected: str) -> bool:
    """无转义键：原位匹配 ``,"expected":``，不匹配则恢复游标（不分配 ``key``）。"""
    if self.ascii_ok:
      return self._try_match_key_ascii_bound(expected)
    return self._try_match_key_chars(expected)

  def _try_match_key_chars(self, expected: str) -> bool:
    """非 ASCII 文档上的 ``try_match_key``（``src_char`` 路径）。"""
    mark: int = self.pos
    self._skip_ws()
    n: int = self.src_len()
    if self.pos < n and self.src_char(self.pos) in ",":
      self.pos += 1
      self._skip_ws()
      n = self.src_len()
    if self.pos >= n or self.src_char(self.pos) not in '"':
      self.pos = mark
      return False
    self.pos += 1
    elen: int = len(expected)
    for i in range(elen):
      if self.pos >= n or self.src_char(self.pos) != expected[i]:
        self.pos = mark
        return False
      self.pos += 1
    if self.pos >= n or self.src_char(self.pos) not in '"':
      self.pos = mark
      return False
    self.pos += 1
    self._skip_ws()
    n = self.src_len()
    if self.pos >= n or self.src_char(self.pos) not in ":":
      self.pos = mark
      return False
    self.pos += 1
    return True

  def skip_field(self) -> None:
    if self.try_skip_field_ascii():
      return
    _k: str = self.load_key()
    self.skip_value()

  def load_key(self) -> str:
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] == ord(","):
      self.pos += 1
      self._skip_ws()
    if self.pos >= len(self.s) or self.s[self.pos] != ord('"'):
      self.fail("expected string key")
    self.pos += 1
    start: int = self.pos
    h: int = 0
    while self.pos < len(self.s):
      c: char = self.s[self.pos]
      if c == ord('"'):
        key = self.s[start:self.pos]
        key.cache_hash(h)
        self.pos += 1
        self._skip_ws()
        self.expect_char(":")
        return key
      if c == ord("\\"):
        self.pos = start - 1
        kbuf2: list[str] = []
        self._parse_string_value(kbuf2)
        key = kbuf2[0]
        self._skip_ws()
        self.expect_char(":")
        return key
      h = h * 31 + int(c)
      self.pos += 1
    self.fail("unterminated string")
    return ""

  def skip_value(self) -> None:
    self._skip_value()

  def _parse_int_at(self) -> int:
    n: int = self.src_len()
    neg: bool = False
    if self.pos < n and self.src_char(self.pos) in "-":
      neg = True
      self.pos += 1
    val: int = 0
    any_d: bool = False
    while self.pos < n:
      c: char = self.src_char(self.pos)
      if c not in "0123456789":
        break
      val *= 10
      val += int(c) - ord("0")
      any_d = True
      self.pos += 1
    if not any_d:
      self.fail("expected int")
    if neg:
      val = -val
    return val

  def parse_int_at(self) -> int:
    """假定游标已在 JSON 数值首字符；不跳过前导空白。"""
    return self._parse_int_at()

  def _parse_int_at_bound(self) -> int:
    """ASCII 快路径：``scan.parse_int_at_ascii`` 叶子。"""
    return self.parse_int_at_ascii()

  def _skip_ws_bound(self) -> None:
    """ASCII bound 空白跳过：``scan.skip_ws_bound`` 叶子。"""
    self.skip_ws_bound()

  def _str_assign_from_seg_bound(self, seg: span[char]) -> str:
    """``seg`` → 新 ``str``（``scan.str_assign_from_seg`` 叶子）。"""
    return self.str_assign_from_seg(seg)

  def _str_assign_from_seg_slot_bound(self, slot: Pointer[str], seg: span[char]) -> None:
    init(slot, self.str_assign_from_seg(seg))

  def _try_match_key_ascii_bound(self, expected: str) -> bool:
    mark: int = self.pos
    self._skip_ws_bound()
    n: int = self.src_len()
    if self.pos < n and self.src_char(self.pos) in ",":
      self.pos += 1
      self._skip_ws_bound()
      n = self.src_len()
    if self.pos >= n or self.src_char(self.pos) not in '"':
      self.pos = mark
      return False
    self.pos += 1
    elen: int = len(expected)
    for i in range(elen):
      if self.pos >= n or self.src_char(self.pos) != expected[i]:
        self.pos = mark
        return False
      self.pos += 1
    if self.pos >= n or self.src_char(self.pos) not in '"':
      self.pos = mark
      return False
    self.pos += 1
    self._skip_ws_bound()
    n = self.src_len()
    if self.pos >= n or self.src_char(self.pos) not in ":":
      self.pos = mark
      return False
    self.pos += 1
    return True

  def load_container[T](self) -> T:
    """``list[…]`` / ``dict[str, …]`` wildcard 容器（``Json.loads`` 分派）。"""
    if T is list[...]:
      return self.load_list_element[T.Element]()
    elif T is dict[str, ...]:
      return self.load_dict_element[T.Value]()

  def load_generic[T](self) -> T:
    return T.deserialize(self)

  def load_list_element[U](self) -> list[U]:
    out: list[U] = []
    self.begin_array()
    self.skip_spaces()
    if self.at_array_end():
      return out
    est: int = (self.src_len() - self.pos) // 48
    if est > 0:
      out.capacity = est
    while True:
      out.append(U.deserialize(self))
      self.skip_spaces()
      if self.at_array_end():
        return out
      self.expect_char(",")
      self.skip_spaces()

  def load_dict_element[V](self) -> dict[str, V]:
    out: dict[str, V] = {}
    self.skip_spaces()
    self.expect_char("{")
    self.skip_spaces()
    n: int = self.src_len()
    if self.pos < n and self.src_char(self.pos) in "}":
      self.pos += 1
      return out
    while True:
      k: str = self.load_key()
      self.skip_spaces()
      v: V = V.deserialize(self)
      out[k] = v
      self.skip_spaces()
      n = self.src_len()
      if self.pos < n and self.src_char(self.pos) in "}":
        self.pos += 1
        return out
      self.expect_char(",")
      self.skip_spaces()

  def _parse_varint_at(self) -> varint:
    n: int = self.src_len()
    start: int = self.pos
    if self.pos < n and self.src_char(self.pos) in "-":
      self.pos += 1
    any_d: bool = False
    while self.pos < n:
      c: char = self.src_char(self.pos)
      if c not in "0123456789":
        break
      any_d = True
      self.pos += 1
    if not any_d:
      self.fail("expected int")
    tok: str = self.s[start:self.pos]
    return new(tok)

  def parse_varint_at(self) -> varint:
    """假定游标已在 JSON 数值首字符；不跳过前导空白。"""
    return self._parse_varint_at()

  def parse_float_at(self) -> float:
    """假定游标已在 JSON 数值首字符；不跳过前导空白。"""
    fbuf: list[float] = []
    self._parse_float_value(fbuf)
    return fbuf[0]

  def parse_bool_at(self) -> bool:
    """假定游标已在 ``true``/``false`` 首字符。"""
    return self._parse_bool_at()

  def load_list_int_value(self) -> list[int]:
    """假定游标已在 ``[``。"""
    return self._load_list_int_at()

  def load_list_varint_value(self) -> list[varint]:
    """假定游标已在 ``[``。"""
    return self._load_list_varint_at()

  def load_list_str_value(self) -> list[str]:
    """假定游标已在 ``[``。"""
    return self._load_list_str_at()

  def load_list_float_value(self) -> list[float]:
    """假定游标已在 ``[``。"""
    return self._load_list_float_at()

  def load_int(self) -> int:
    self._skip_ws()
    return self._parse_int_at()

  def load_varint(self) -> varint:
    self._skip_ws()
    return self._parse_varint_at()

  def load_float(self) -> float:
    self._skip_ws()
    fbuf: list[float] = []
    self._parse_float_value(fbuf)
    return fbuf[0]

  def load_string_slow(self) -> str:
    """含转义等复杂 JSON 字符串。"""
    sbuf: list[str] = []
    self._parse_string_value(sbuf)
    return sbuf[0]

  def load_str(self) -> str:
    self._skip_ws()
    if self.pos >= len(self.s) or self.s[self.pos] != ord('"'):
      return self.load_string_slow()
    self.pos += 1
    start: int = self.pos
    while self.pos < len(self.s):
      if self.s[self.pos] == ord('"'):
        raw: str = self.s[start:self.pos]
        self.pos += 1
        return raw
      if self.s[self.pos] == ord("\\"):
        self.pos = start - 1
        return self.load_string_slow()
      self.pos += 1
    self.fail("unterminated string")
    return ""

  def _parse_bool_at(self) -> bool:
    if self.pos + 4 <= len(self.s) and self.s[self.pos : self.pos + 4] == "true":
      self.pos += 4
      return True
    if self.pos + 5 <= len(self.s) and self.s[self.pos : self.pos + 5] == "false":
      self.pos += 5
      return False
    self.fail("expected bool")
    return False

  def load_bool(self) -> bool:
    bbuf: list[bool] = []
    self._parse_bool_value(bbuf)
    return bbuf[0]

  def _prealloc_list_ascii(self, out: list[int] @ref, bytes_per_elem: int) -> None:
    est: int = (self.ascii_len - self.pos) // bytes_per_elem
    if est > 0:
      out.capacity = est

  def _prealloc_dict_ascii(self, out: dict[str, int] @ref, bytes_per_entry: int) -> None:
    est: int = (self.ascii_len - self.pos) // bytes_per_entry
    if est > 0:
      cap: int = est * 3 // 2 + 1
      if cap < 8:
        cap = 8
      out.capacity = cap

  def _ascii_byte_is(self, n: int, ch: str) -> bool:
    if self.pos >= n:
      return False
    ec: char = ch[0]
    if self.ascii_ok:
      return self.byte_at(self.pos) == int(ec)
    return self.src_char(self.pos) == ec

  def _load_list_int_ascii_loop(self, out: list[int] @ref) -> None:
    n: int = self.ascii_len
    self._prealloc_list_ascii(out, 6)
    while True:
      slot: Pointer[int] = out.serde_push_slot()
      init(slot, self._parse_int_at_bound())
      out.serde_commit_push()
      self._skip_ws_bound()
      n = self.ascii_len
      if self._ascii_byte_is(n, "]"):
        self.pos += 1
        return
      if self.pos >= n or not self._ascii_byte_is(n, ","):
        self.fail("expected , or ]")
      self.pos += 1
      self._skip_ws_bound()

  def _load_list_int_ascii_loop_ref(self, out: list[int] @ref) -> None:
    while True:
      out.append(self.parse_int_at())
      self.skip_ws()
      if self.pos < self.src_len() and self.src_char(self.pos) in "]":
        self.pos += 1
        return
      self.expect_char(",")
      self.skip_ws()

  def _load_list_str_ascii_loop(self, out: list[str] @ref) -> None:
    n: int = self.ascii_len
    est: int = (self.ascii_len - self.pos) // 8
    if est > 0:
      out.capacity = est
    while True:
      seg: span[char] = self._load_str_span_bound()
      slot: Pointer[str] = out.serde_push_slot()
      self._str_assign_from_seg_slot_bound(slot, seg)
      out.serde_commit_push()
      self._skip_ws_bound()
      n = self.ascii_len
      if self._ascii_byte_is(n, "]"):
        self.pos += 1
        return
      if self.pos >= n or not self._ascii_byte_is(n, ","):
        self.fail("expected , or ]")
      self.pos += 1
      self._skip_ws_bound()

  def _load_list_str_ascii_loop_ref(self, out: list[str] @ref) -> None:
    while True:
      out.append(self.load_str())
      self.skip_ws()
      if self.pos < self.src_len() and self.src_char(self.pos) in "]":
        self.pos += 1
        return
      self.expect_char(",")
      self.skip_ws()

  def _dict_str_int_push_ascii(self, out: dict[str, int] @ref) -> None:
    kseg: span[char] = self._load_str_span_bound()
    k: str = self._str_assign_from_seg_bound(kseg)
    self._skip_ws_bound()
    n: int = self.ascii_len
    if self.pos >= n or not self._ascii_byte_is(n, ":"):
      self.fail("expected :")
    self.pos += 1
    out[k] = self._parse_int_at_bound()

  def _dict_str_int_push_ascii_ref(self, out: dict[str, int] @ref) -> None:
    seg: span[char] = self.load_str_span()
    k: str = str.from_span(seg)
    self.skip_ws()
    self.expect_char(":")
    out[k] = self.parse_int_at()

  def _load_dict_str_int_ascii_loop(self, out: dict[str, int] @ref) -> None:
    n: int = self.ascii_len
    self._prealloc_dict_ascii(out, 12)
    while True:
      self._dict_str_int_push_ascii(out)
      self._skip_ws_bound()
      n = self.ascii_len
      if self._ascii_byte_is(n, "}"):
        self.pos += 1
        return
      if self.pos >= n or not self._ascii_byte_is(n, ","):
        self.fail("expected , or }")
      self.pos += 1
      self._skip_ws_bound()

  def _load_dict_str_int_ascii_loop_ref(self, out: dict[str, int] @ref) -> None:
    while True:
      self._dict_str_int_push_ascii_ref(out)
      self.skip_ws()
      if self.pos < self.src_len() and self.src_char(self.pos) in "}":
        self.pos += 1
        return
      self.expect_char(",")
      self.skip_ws()

  def _dict_str_str_push_ascii(self, out: dict[str, str] @ref) -> None:
    kseg: span[char] = self._load_str_span_bound()
    k: str = self._str_assign_from_seg_bound(kseg)
    self._skip_ws_bound()
    n: int = self.ascii_len
    if self.pos >= n or not self._ascii_byte_is(n, ":"):
      self.fail("expected :")
    self.pos += 1
    vseg: span[char] = self._load_str_span_bound()
    v: str = self._str_assign_from_seg_bound(vseg)
    out[k] = v

  def _dict_str_str_push_ascii_ref(self, out: dict[str, str] @ref) -> None:
    kseg: span[char] = self.load_str_span()
    k: str = str.from_span(kseg)
    self.skip_ws()
    self.expect_char(":")
    vseg: span[char] = self.load_str_span()
    v: str = str.from_span(vseg)
    out[k] = v

  def _load_dict_str_str_ascii_loop(self, out: dict[str, str] @ref) -> None:
    n: int = self.ascii_len
    est: int = (self.ascii_len - self.pos) // 14
    if est > 0:
      cap: int = est * 3 // 2 + 1
      if cap < 8:
        cap = 8
      out.capacity = cap
    while True:
      self._dict_str_str_push_ascii(out)
      self._skip_ws_bound()
      n = self.ascii_len
      if self._ascii_byte_is(n, "}"):
        self.pos += 1
        return
      if self.pos >= n or not self._ascii_byte_is(n, ","):
        self.fail("expected , or }")
      self.pos += 1
      self._skip_ws_bound()

  def _load_dict_str_str_ascii_loop_ref(self, out: dict[str, str] @ref) -> None:
    while True:
      self._dict_str_str_push_ascii_ref(out)
      self.skip_ws()
      if self.pos < self.src_len() and self.src_char(self.pos) in "}":
        self.pos += 1
        return
      self.expect_char(",")
      self.skip_ws()

  def _dict_str_varint_push_ascii(self, out: dict[str, varint] @ref) -> None:
    kseg: span[char] = self._load_str_span_bound()
    k: str = self._str_assign_from_seg_bound(kseg)
    self._skip_ws_bound()
    n: int = self.ascii_len
    if self.pos >= n or not self._ascii_byte_is(n, ":"):
      self.fail("expected :")
    self.pos += 1
    out[k] = self.parse_varint_at()

  def _dict_str_varint_push_ascii_ref(self, out: dict[str, varint] @ref) -> None:
    seg: span[char] = self.load_str_span()
    k: str = str.from_span(seg)
    self.skip_ws()
    self.expect_char(":")
    out[k] = self.parse_varint_at()

  def _load_dict_str_varint_ascii_loop(self, out: dict[str, varint] @ref) -> None:
    n: int = self.ascii_len
    est: int = (self.ascii_len - self.pos) // 12
    if est > 0:
      cap: int = est * 3 // 2 + 1
      if cap < 8:
        cap = 8
      out.capacity = cap
    while True:
      self._dict_str_varint_push_ascii(out)
      self._skip_ws_bound()
      n = self.ascii_len
      if self._ascii_byte_is(n, "}"):
        self.pos += 1
        return
      if self.pos >= n or not self._ascii_byte_is(n, ","):
        self.fail("expected , or }")
      self.pos += 1
      self._skip_ws_bound()

  def _load_dict_str_varint_ascii_loop_ref(self, out: dict[str, varint] @ref) -> None:
    while True:
      self._dict_str_varint_push_ascii_ref(out)
      self.skip_ws()
      if self.pos < self.src_len() and self.src_char(self.pos) in "}":
        self.pos += 1
        return
      self.expect_char(",")
      self.skip_ws()

  def _dict_str_float_push_ascii(self, out: dict[str, float] @ref) -> None:
    kseg: span[char] = self._load_str_span_bound()
    k: str = self._str_assign_from_seg_bound(kseg)
    self._skip_ws_bound()
    n: int = self.ascii_len
    if self.pos >= n or not self._ascii_byte_is(n, ":"):
      self.fail("expected :")
    self.pos += 1
    out[k] = self.parse_float_at()

  def _dict_str_float_push_ascii_ref(self, out: dict[str, float] @ref) -> None:
    seg: span[char] = self.load_str_span()
    k: str = str.from_span(seg)
    self.skip_ws()
    self.expect_char(":")
    out[k] = self.parse_float_at()

  def _load_dict_str_float_ascii_loop(self, out: dict[str, float] @ref) -> None:
    n: int = self.ascii_len
    est: int = (self.ascii_len - self.pos) // 16
    if est > 0:
      cap: int = est * 3 // 2 + 1
      if cap < 8:
        cap = 8
      out.capacity = cap
    while True:
      self._dict_str_float_push_ascii(out)
      self._skip_ws_bound()
      n = self.ascii_len
      if self._ascii_byte_is(n, "}"):
        self.pos += 1
        return
      if self.pos >= n or not self._ascii_byte_is(n, ","):
        self.fail("expected , or }")
      self.pos += 1
      self._skip_ws_bound()

  def _load_dict_str_float_ascii_loop_ref(self, out: dict[str, float] @ref) -> None:
    while True:
      self._dict_str_float_push_ascii_ref(out)
      self.skip_ws()
      if self.pos < self.src_len() and self.src_char(self.pos) in "}":
        self.pos += 1
        return
      self.expect_char(",")
      self.skip_ws()

  def scan_test_parse_int_at_bound(self) -> int:
    """集成测：``_parse_int_at_bound`` 快路径。"""
    return self._parse_int_at_bound()

  def scan_test_load_list_int_ascii_loop(self, out: list[int] @ref) -> None:
    """集成测：``@native`` 叶子组合的 ASCII ``list[int]`` 循环。"""
    self._load_list_int_ascii_loop(out)

  def scan_test_load_list_int_ascii_loop_ref(self, out: list[int] @ref) -> None:
    """集成测：纯 Python ``*_ref`` 组合的 ASCII ``list[int]`` 循环。"""
    self._load_list_int_ascii_loop_ref(out)

  def scan_test_load_list_str_ascii_loop(self, out: list[str] @ref) -> None:
    self._load_list_str_ascii_loop(out)

  def scan_test_load_list_str_ascii_loop_ref(self, out: list[str] @ref) -> None:
    self._load_list_str_ascii_loop_ref(out)

  def scan_test_load_dict_str_int_ascii_loop(self, out: dict[str, int] @ref) -> None:
    self._load_dict_str_int_ascii_loop(out)

  def scan_test_load_dict_str_int_ascii_loop_ref(self, out: dict[str, int] @ref) -> None:
    self._load_dict_str_int_ascii_loop_ref(out)

  def scan_test_load_dict_str_str_ascii_loop(self, out: dict[str, str] @ref) -> None:
    self._load_dict_str_str_ascii_loop(out)

  def scan_test_load_dict_str_str_ascii_loop_ref(self, out: dict[str, str] @ref) -> None:
    self._load_dict_str_str_ascii_loop_ref(out)

  def _load_list_int_at(self) -> list[int]:
    self.expect_char("[")
    out: list[int] = []
    self.try_bind_ascii()
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "]":
      self.pos += 1
      return out
    if self.ascii_ok:
      self._load_list_int_ascii_loop(out)
      return out
    while True:
      out.append(self._parse_int_at())
      self._skip_ws()
      if self.pos < len(self.s) and self.s[self.pos] in "]":
        self.pos += 1
        return out
      self.expect_char(",")
      self._skip_ws()

  def _load_list_varint_at(self) -> list[varint]:
    self.expect_char("[")
    out: list[varint] = []
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "]":
      self.pos += 1
      return out
    while True:
      out.append(self._parse_varint_at())
      self._skip_ws()
      if self.pos < len(self.s) and self.s[self.pos] in "]":
        self.pos += 1
        return out
      self.expect_char(",")
      self._skip_ws()

  def load_list_int(self) -> list[int]:
    self._skip_ws()
    return self.load_list_int_value()

  def load_list_varint(self) -> list[varint]:
    self._skip_ws()
    return self.load_list_varint_value()

  def _load_list_str_at(self) -> list[str]:
    self.expect_char("[")
    out: list[str] = []
    self.try_bind_ascii()
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "]":
      self.pos += 1
      return out
    if self.ascii_ok:
      self._load_list_str_ascii_loop(out)
      return out
    while True:
      out.append(self.load_str())
      self._skip_ws()
      if self.pos < len(self.s) and self.s[self.pos] in "]":
        self.pos += 1
        return out
      self.expect_char(",")
      self._skip_ws()

  def load_list_str(self) -> list[str]:
    self._skip_ws()
    return self.load_list_str_value()

  def _load_list_float_at(self) -> list[float]:
    self.expect_char("[")
    out: list[float] = []
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "]":
      self.pos += 1
      return out
    while True:
      fbuf: list[float] = []
      self._parse_float_value(fbuf)
      out.append(fbuf[0])
      self._skip_ws()
      if self.pos < len(self.s) and self.s[self.pos] in "]":
        self.pos += 1
        return out
      self.expect_char(",")
      self._skip_ws()

  def load_list_float(self) -> list[float]:
    self._skip_ws()
    return self.load_list_float_value()

  def _load_dict_str_int_at(self) -> dict[str, int]:
    self.expect_char("{")
    out: dict[str, int] = {}
    self.try_bind_ascii()
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1
      return out
    if self.ascii_ok:
      self._load_dict_str_int_ascii_loop(out)
      return out
    while True:
      kbuf: list[str] = []
      self._parse_string_value(kbuf)
      k: str = kbuf[0]
      self._skip_ws()
      self.expect_char(":")
      vbuf: list[int] = []
      self._parse_int_value(vbuf)
      out[k] = vbuf[0]
      self._skip_ws()
      if self.pos < len(self.s) and self.s[self.pos] in "}":
        self.pos += 1
        return out
      self.expect_char(",")
      self._skip_ws()

  def load_dict_str_int(self) -> dict[str, int]:
    self._skip_ws()
    return self._load_dict_str_int_at()

  def _load_dict_str_varint_at(self) -> dict[str, varint]:
    self.expect_char("{")
    out: dict[str, varint] = {}
    self.try_bind_ascii()
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1
      return out
    if self.ascii_ok:
      self._load_dict_str_varint_ascii_loop(out)
      return out
    while True:
      kbuf: list[str] = []
      self._parse_string_value(kbuf)
      k: str = kbuf[0]
      self._skip_ws()
      self.expect_char(":")
      vbuf: list[varint] = []
      self._parse_varint_value(vbuf)
      out[k] = vbuf[0]
      self._skip_ws()
      if self.pos < len(self.s) and self.s[self.pos] in "}":
        self.pos += 1
        return out
      self.expect_char(",")
      self._skip_ws()

  def load_dict_str_varint(self) -> dict[str, varint]:
    self._skip_ws()
    return self._load_dict_str_varint_at()

  def _load_dict_str_str_at(self) -> dict[str, str]:
    self.expect_char("{")
    out: dict[str, str] = {}
    self.try_bind_ascii()
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1
      return out
    if self.ascii_ok:
      self._load_dict_str_str_ascii_loop(out)
      return out
    while True:
      kbuf: list[str] = []
      self._parse_string_value(kbuf)
      k: str = kbuf[0]
      self._skip_ws()
      self.expect_char(":")
      vbuf: list[str] = []
      self._parse_string_value(vbuf)
      out[k] = vbuf[0]
      self._skip_ws()
      if self.pos < len(self.s) and self.s[self.pos] in "}":
        self.pos += 1
        return out
      self.expect_char(",")
      self._skip_ws()

  def load_dict_str_str(self) -> dict[str, str]:
    self._skip_ws()
    return self._load_dict_str_str_at()

  def _load_dict_str_float_at(self) -> dict[str, float]:
    self.expect_char("{")
    out: dict[str, float] = {}
    self.try_bind_ascii()
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1
      return out
    if self.ascii_ok:
      self._load_dict_str_float_ascii_loop(out)
      return out
    while True:
      kbuf: list[str] = []
      self._parse_string_value(kbuf)
      k: str = kbuf[0]
      self._skip_ws()
      self.expect_char(":")
      vbuf: list[float] = []
      self._parse_float_value(vbuf)
      out[k] = vbuf[0]
      self._skip_ws()
      if self.pos < len(self.s) and self.s[self.pos] in "}":
        self.pos += 1
        return out
      self.expect_char(",")
      self._skip_ws()

  def load_dict_str_float(self) -> dict[str, float]:
    self._skip_ws()
    return self._load_dict_str_float_at()

  def at_object_end(self) -> bool:
    self._skip_ws()
    if self.pos >= len(self.s):
      self.fail("unterminated object")
    if self.s[self.pos] in "}":
      self.pos += 1
      return True
    return False

  def begin_array(self) -> None:
    self._skip_ws()
    self.expect_char("[")

  def at_array_end(self) -> bool:
    self._skip_ws()
    if self.pos >= len(self.s):
      self.fail("unterminated array")
    if self.s[self.pos] in "]":
      self.pos += 1
      return True
    return False

  def load_tag_field(self) -> str:
    key: str = self.load_key()
    if key != "tag":
      self.fail("expected tag field")
    return self.load_str()

  def begin_payload_object(self) -> None:
    key: str = self.load_key()
    if key != "payload":
      self.fail("expected payload field")
    self._skip_ws()
    self.expect_char("{")

  def end_payload_object(self) -> None:
    self._skip_ws()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1

  def byte_at_ref(self, i: int) -> int:
    """第 ``i`` 字节（``int(src_char)``）。"""
    return int(self.src_char(i))


  def byte_at(self, i: int) -> int:
    """bound ASCII 下第 ``i`` 字节（``ascii_bytes`` 或 ``src_char``）。"""
    p: Pointer[char] = self.ascii_bytes
    if self.ascii_ok and p is not None:
      return int(p[i])
    return self.byte_at_ref(i)


  def _load_str_span_slow(self) -> span[char]:
    n: int = self.src_len()
    if self.pos >= n or self.src_char(self.pos) not in '"':
      slow: str = self.load_string_slow()
      return slow.view
    self.pos += 1
    start: int = self.pos
    while self.pos < n:
      c: char = self.src_char(self.pos)
      if c in '"':
        end: int = self.pos
        self.pos += 1
        return self.s.view[start:end]
      if c in "\\":
        self.pos = start - 1
        slow2: str = self.load_string_slow()
        return slow2.view
      self.pos += 1
    self.fail("unterminated string")
    return self.s.view[:0]


  def parse_int_at_ascii_ref(self) -> int:
    """游标处 JSON 整数（``JsonDecoder.parse_int_at`` 语义参照）。"""
    return self.parse_int_at()


  def parse_int_at_ascii(self) -> int:
    """bound ASCII 下 SwAR 整数解析（游标已在数值首字符）。"""
    if not self.ascii_ok:
      self.fail("ascii int parse requires bound view")
      return 0
    n: int = self.ascii_len
    p: Pointer[char] = self.ascii_bytes
    pos: int = self.pos
    neg: bool = False
    if pos < n and self.byte_at(pos) == ord("-"):
      neg = True
      pos += 1
    val: int64 = 0
    any_d: bool = False
    i: int = pos
    while i < n:
      if p is not None and i + 8 <= n:
        chunk: uint64 = load_u64_le(p, i)
        if Self._swar_is8digits(chunk):
          val *= 100000000
          val += int64(Self._swar_parse8(chunk))
          i += 8
          any_d = True
          continue
      c: int = self.byte_at(i)
      if c < ord("0") or c > ord("9"):
        break
      val *= 10
      val += int64(c - ord("0"))
      i += 1
      any_d = True
    if not any_d:
      self.fail("expected int")
      return 0
    self.pos = i
    if neg:
      val = -val
    return int(val)


  def skip_ws_bound_ref(self) -> None:
    """bound 空白跳过（``skip_ws`` 语义参照）。"""
    self.skip_ws()


  def skip_ws_bound(self) -> None:
    """``ascii_ok`` 时 8 字节空白快扫，否则 ``skip_ws``。"""
    if not self.ascii_ok:
      self.skip_ws()
      return
    n: int = self.ascii_len
    i: int = self.pos
    p: Pointer[char] = self.ascii_bytes
    while i < n:
      if p is not None and i + 8 <= n:
        chunk: uint64 = load_u64_le(p, i)
        if Self._chunk_all_ws(chunk):
          i += 8
          continue
      if not Self._is_ws_byte(self.byte_at(i)):
        break
      i += 1
    self.pos = i


  def load_str_span_ascii_ref(self) -> span[char]:
    """无转义 JSON 字符串 span（逐字符扫描语义参照）。"""
    return self._load_str_span_slow()


  def load_str_span_ascii(self) -> span[char]:
    """bound ASCII 下无转义引号串快扫；有转义则 ``load_string_slow``。"""
    if not self.ascii_ok:
      self.skip_spaces()
      return self._load_str_span_slow()
    n: int = self.ascii_len
    p: Pointer[char] = self.ascii_bytes
    if self.pos >= n or self.byte_at(self.pos) != ord('"'):
      slow: str = self.load_string_slow()
      return slow.view
    self.pos += 1
    start: int = self.pos
    i: int = start
    while i < n:
      if p is not None and i + 8 <= n:
        chunk: uint64 = load_u64_le(p, i)
        special: bool = False
        for k in range(8):
          c: int = Self._chunk_byte(chunk, k)
          if c == ord('"'):
            self.pos = i + k + 1
            return self.s.view[start:i + k]
          if c == ord("\\"):
            special = True
            break
        if not special:
          i += 8
          continue
        break
      c2: int = self.byte_at(i)
      if c2 == ord('"'):
        self.pos = i + 1
        return self.s.view[start:i]
      if c2 == ord("\\"):
        break
      i += 1
    if i >= n:
      self.fail("unterminated string")
      return self.s.view[:0]
    self.pos = start - 1
    slow2: str = self.load_string_slow()
    return slow2.view


  def str_assign_from_seg_ref(self, seg: span[char]) -> str:
    """``seg`` → 新 ``str``（``copy_from_span``）。"""
    dst: str = ""
    dst.copy_from_span(seg)
    return dst


  def str_assign_from_seg(self, seg: span[char]) -> str:
    """``seg`` → 新 ``str``（Arena 时 ``copy_buf`` + ``adopt_span``）。"""
    seg_len: int = len(seg)
    if seg_len == 0 or not self.str_arena_active:
      return self.str_assign_from_seg_ref(seg)
    buf: Pointer[char] = self.str_arena.acquire(seg_len)
    if buf is None:
      return self.str_assign_from_seg_ref(seg)
    copy_buf(buf, seg.at(), seg_len)
    dst: str = ""
    owned: span[char] = new(buf, seg_len, 1)
    dst.adopt_span(owned)
    self.str_arena.release(buf)
    return dst


  def _skip_string_ascii(self) -> None:
    """跳过 JSON 字符串字面量（``byte_at_ref`` 组合）。"""
    n: int = self.src_len()
    i: int = self.pos
    if i >= n or self.byte_at_ref(i) != ord('"'):
      self.fail("expected string")
    i += 1
    while i < n:
      c: int = self.byte_at_ref(i)
      if c == ord('"'):
        self.pos = i + 1
        return
      if c == ord("\\"):
        i += 1
        if i >= n:
          self.fail("unterminated string")
        if self.byte_at_ref(i) == ord("u"):
          i += 5
        else:
          i += 1
        continue
      i += 1
    self.fail("unterminated string")


  def _skip_number_ascii(self) -> None:
    n: int = self.src_len()
    i: int = self.pos
    if i < n and self.byte_at_ref(i) == ord("-"):
      i += 1
    for i in range(i, n):
      c: int = self.byte_at_ref(i)
      if ord("0") <= c <= ord("9") or c in {ord("."), ord("e"), ord("E"), ord("+"), ord("-")}:
        continue
      break
    self.pos = i


  def _skip_container_ascii(self, open_ch: int, close_ch: int) -> None:
    n: int = self.src_len()
    depth: int = 0
    while self.pos < n:
      c: char = self.src_char(self.pos)
      match c:
        case _ if c == open_ch:
          depth += 1
        case _ if c == close_ch:
          depth -= 1
          if depth == 0:
            self.pos += 1
            return
        case '"':
          self._skip_string_ascii()
          continue
        case _:
          pass
      self.pos += 1
    if open_ch == ord("["):
      self.fail("unterminated array")
    self.fail("unterminated object")


  def _skip_value_ascii(self) -> None:
    self.skip_ws_bound_ref()
    n: int = self.src_len()
    if self.pos >= n:
      self.fail("empty input")
    c: char = self.src_char(self.pos)
    match c:
      case '"':
        self._skip_string_ascii()
        return
      case 't':
        if self.pos + 4 <= n:
          if (
            self.src_char(self.pos + 0) == 't'
            and self.src_char(self.pos + 1) == 'r'
            and self.src_char(self.pos + 2) == 'u'
            and self.src_char(self.pos + 3) == 'e'
          ):
            self.pos += 4
            return
        self.fail("expected bool")
      case 'f':
        if self.pos + 5 <= n:
          if (
            self.src_char(self.pos + 0) == 'f'
            and self.src_char(self.pos + 1) == 'a'
            and self.src_char(self.pos + 2) == 'l'
            and self.src_char(self.pos + 3) == 's'
            and self.src_char(self.pos + 4) == 'e'
          ):
            self.pos += 5
            return
        self.fail("expected bool")
      case 'n':
        if self.pos + 4 <= n:
          if (
            self.src_char(self.pos + 0) == 'n'
            and self.src_char(self.pos + 1) == 'u'
            and self.src_char(self.pos + 2) == 'l'
            and self.src_char(self.pos + 3) == 'l'
          ):
            self.pos += 4
            return
      case '-' | '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9':
        self._skip_number_ascii()
        return
      case '[':
        self._skip_container_ascii(ord("["), ord("]"))
        return
      case '{':
        self._skip_container_ascii(ord("{"), ord("}"))
        return
      case _:
        self.fail("bad value")


  def try_skip_value_ascii(self) -> bool:
    """跳过单个 JSON 值（纯 Python 组合 ``byte_at_ref`` / ``skip_ws_bound_ref``）。"""
    self.try_bind_ascii()
    if not self.ascii_ok:
      return False
    self._skip_value_ascii()
    return True


  def try_skip_field_ascii(self) -> bool:
    """跳过 ``"key": value`` 字段（纯 Python 组合）。"""
    self.try_bind_ascii()
    if not self.ascii_ok:
      return False
    mark: int = self.pos
    self.skip_ws_bound_ref()
    n: int = self.src_len()
    if self.pos < n and self.byte_at_ref(self.pos) == ord(","):
      self.pos += 1
      self.skip_ws_bound_ref()
    if self.pos >= n or self.byte_at_ref(self.pos) != ord('"'):
      self.pos = mark
      return False
    self._skip_string_ascii()
    self.skip_ws_bound_ref()
    if self.pos >= n or self.byte_at_ref(self.pos) != ord(":"):
      self.pos = mark
      return False
    self.pos += 1
    self._skip_value_ascii()
    return True

class Json:
  """JSON 模块级 API（对齐 CPython ``json`` 子集）。"""

  @staticmethod
  @overload
  def _finish_dump(enc: JsonEncoder, fp: StringIO) -> None:
    fp.clear_buffer()
    enc.flush_to(fp)

  @staticmethod
  @overload
  def _finish_dump(enc: JsonEncoder, fp: TextIOWrapper) -> None:
    enc.flush_to(fp)

  @staticmethod
  @overload
  def _write_fast(s: str, fp: StringIO) -> None:
    fp.clear_buffer()
    fp.write(s)

  @staticmethod
  @overload
  def _write_fast(s: str, fp: TextIOWrapper) -> None:
    fp.write(s)

  @staticmethod
  @immutable
  def loads_uses_str_arena[T]() -> bool:
    """``loads`` 是否需 ``str_arena``（标量/纯数值容器为 ``False``）。"""
    if T in { int, varint, float, bool, list[int], list[varint], list[float] }:
      return False
    else:
      return True

  @staticmethod
  @overload
  def dumps(obj: bool, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_bool(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: int, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_int(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: varint, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_varint(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: float, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_float(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: str, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_str(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: list[int], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fast_encode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_int(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: list[varint], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fast_encode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_varint(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: list[str], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fast_encode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_str(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: list[float], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fast_encode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_float(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: dict[str, int], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fast_encode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_int(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: dict[str, varint], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fast_encode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_varint(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: dict[str, str], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fast_encode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_str(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: dict[str, float], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fast_encode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_float(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps[T](obj: T, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    obj.serialize(enc)
    return enc.take()



  @staticmethod
  @overload
  def dumps[T](obj: list[T], indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    n: int = len(obj)
    if indent == 0 and n > 0:
      enc.grow_buf(n * 48 + 16)
    enc.begin_array()
    for i in range(n):
      obj[i].serialize(enc)
    enc.end_array()
    return enc.take()



  @staticmethod
  @overload
  def dump(obj: bool, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_bool(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: int, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_int(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: varint, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_varint(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: float, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_float(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: str, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_str(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[int], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_int(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[varint], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_varint(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[str], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_str(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[float], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_float(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, int], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_int(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, varint], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_varint(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, str], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_str(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, float], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_float(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump[T](obj: T, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    obj.serialize(enc)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump[T](obj: list[T], fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    n: int = len(obj)
    if indent == 0 and n > 0:
      enc.grow_buf(n * 48 + 16)
    enc.begin_array()
    for i in range(n):
      obj[i].serialize(enc)
    enc.end_array()
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: bool, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_bool(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: int, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_int(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: varint, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_varint(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: float, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_float(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: str, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_str(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[int], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_int(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[varint], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_varint(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[str], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_str(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[float], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_list_float(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, int], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_int(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, varint], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_varint(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, str], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_str(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, float], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._write_fast(JsonEncoder.fast_encode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dump_dict_str_float(obj)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump[T](obj: T, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    obj.serialize(enc)
    Self._finish_dump(enc, fp)



  @staticmethod
  @overload
  def dump[T](obj: list[T], fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    n: int = len(obj)
    if indent == 0 and n > 0:
      enc.grow_buf(n * 48 + 16)
    enc.begin_array()
    for i in range(n):
      obj[i].serialize(enc)
    enc.end_array()
    Self._finish_dump(enc, fp)



  @staticmethod
  def loads[T](s: str) -> T:
    """``json.loads``；``T`` 为返回值静态类型（``Json.loads[User](s)`` 或赋值推断）。"""
    dec: JsonDecoder = new.from_text(s)
    dec.try_bind_ascii()
    if Self.loads_uses_str_arena[T]():
      dec.enable_str_arena()
    if T is int:
      out = dec.load_int()
    elif T is varint:
      out = dec.load_varint()
    elif T is float:
      out = dec.load_float()
    elif T is str:
      out = dec.load_str()
    elif T is bool:
      out = dec.load_bool()
    elif T is list[int]:
      out = dec.load_list_int()
    elif T is list[varint]:
      out = dec.load_list_varint()
    elif T is list[str]:
      out = dec.load_list_str()
    elif T is list[float]:
      out = dec.load_list_float()
    elif T is list[...]:
      out = dec.load_container[T]()
    elif T is dict[str, int]:
      out = dec.load_dict_str_int()
    elif T is dict[str, varint]:
      out = dec.load_dict_str_varint()
    elif T is dict[str, str]:
      out = dec.load_dict_str_str()
    elif T is dict[str, float]:
      out = dec.load_dict_str_float()
    elif T is dict[str, ...]:
      out = dec.load_container[T]()
    else:
      out = dec.load_generic[T]()
    if dec.str_arena_active:
      dec.str_arena.reset()
      dec.str_arena_active = False
    dec.release_ascii()
    return out

  @staticmethod
  @overload
  def load[T](fp: TextIOWrapper) -> T:
    """``json.load``：``fp.read()`` 后 ``Json.loads[T]``。"""
    return Self.loads[T](fp.read())

  @staticmethod
  @overload
  def load[T](fp: StringIO) -> T:
    return Self.loads[T](fp.read())


@union
class JsonDocStep:
  @variant
  class Field:
    key: str

  @variant
  class Index:
    index: int


@copyable
@dataclass
class JsonDocument[T]:
  """JSON 持久化文档；打开文件用 ``new.open(path, mode)``（``x: JsonDocument[T] = new.open(...)``；勿 ``JsonDocument[T].open``，S06b）。"""

  path: str = ""
  mode: str = ""
  text: str = ""
  orig: str = ""
  dec: JsonDecoder = new()
  writable: bool = False
  dirty: bool = False
  text_gen: int = 0
  arr_cache_bracket: int = -1
  arr_cache_offsets: list[int] @optional = []

  def _array_index(self, idx: int):
    self.dec.skip_spaces()
    self.dec.expect_char("[")
    self.dec.skip_spaces()
    open_pos: int = self.dec.pos - 1
    n: int = len(self.dec.s)
    if self.dec.pos < n and self.dec.s[self.dec.pos] in "]":
      self.dec.fail("index out of range")
    if idx < 0:
      self.dec.fail("index out of range")
    if not self._arr_cache_valid(open_pos):
      self._arr_cache_reset(open_pos)
    offs: list[int] = self.arr_cache_offsets
    if len(offs) > idx:
      self.dec.pos = offs[idx]
      return
    if offs:
      self.dec.pos = offs[-1]
      self.dec.skip_value()
      self.dec.skip_spaces()
      if self.dec.pos < n and self.dec.s[self.dec.pos] in "]":
        self.dec.fail("index out of range")
      self.dec.expect_char(",")
      self.dec.skip_spaces()
    while len(offs) <= idx:
      if self.dec.pos < n and self.dec.s[self.dec.pos] in "]":
        self.dec.fail("index out of range")
      offs.append(self.dec.pos)
      if len(offs) - 1 == idx:
        break
      self.dec.skip_value()
      self.dec.skip_spaces()
      if self.dec.pos < n and self.dec.s[self.dec.pos] in "]":
        self.dec.fail("index out of range")
      self.dec.expect_char(",")
      self.dec.skip_spaces()
    self.dec.pos = offs[idx]

  def _object_key(self, key: str):
    self.dec.skip_spaces()
    n: int = len(self.dec.s)
    if self.dec.pos < n and self.dec.s[self.dec.pos] in "{":
      self.dec.pos += 1
      self.dec.skip_spaces()
    if self.dec.pos < n and self.dec.s[self.dec.pos] in "}":
      self.dec.fail("missing key")
    while True:
      if self.dec.at_object_end():
        self.dec.fail("missing key")
      if self.dec.try_match_key(key):
        return
      self.dec.skip_field()

  def _container_close_index(self, open_pos: int) -> int:
    open_c: char = self.dec.s[open_pos]
    if open_c not in "[{":
      self.dec.fail("expected container")
    depth: int = 0
    n: int = len(self.dec.s)
    i: int = open_pos
    while i < n:
      c: char = self.dec.s[i]
      if open_c in "{":
        match c:
          case '{':
            depth += 1
          case '}':
            depth -= 1
            if depth == 0:
              return i
          case _:
            pass
      elif open_c in "[":
        match c:
          case '[':
            depth += 1
          case ']':
            depth -= 1
            if depth == 0:
              return i
          case _:
            pass
      elif c in '"':
        i += 1
        while i < n:
          c2: char = self.dec.s[i]
          if c2 in '"':
            break
          if c2 in "\\":
            i += 1
          i += 1
      i += 1
    self.dec.fail("unterminated container")
    return open_pos

  @overload
  def _encode_for_patch(self, value: str) -> str:
    return Json.dumps(value)

  @overload
  def _encode_for_patch(self, value) -> str:
    enc: JsonEncoder = new()
    value.serialize(enc)
    return enc.take()

  @staticmethod
  def open(path: str, mode: str = "r") -> Self:
    doc: Self = new()
    doc.path = path
    doc.mode = mode
    doc.writable = False
    n: int = len(mode)
    for i in range(n):
      c: char = mode[i]
      if c in "+wa":
        doc.writable = True
        break
    if "w" in mode:
      doc.text = "{}"
    else:
      f: TextIOWrapper = new(path, "r")
      doc.text = f.read()
      f.close()
    doc.orig = doc.text
    doc.dirty = False
    doc.sync_dec()
    return doc

  def __enter__(self) -> Self:
    return self

  def __exit__(self):
    self.commit()

  def __getattr__(self, name: str) -> JsonDocCursor[T]:
    cur: JsonDocCursor[T] = new()
    cur.doc = self
    cur.steps.append(JsonDocStep.Field(name))
    return cur

  def __getitem__(self, i: int) -> JsonDocCursor[T]:
    cur: JsonDocCursor[T] = new()
    cur.doc = self
    cur.steps.append(JsonDocStep.Index(i))
    return cur

  def __setattr__(self, name: str, value):
    steps: list[JsonDocStep] = [JsonDocStep.Field(name)]
    self.replace_at(steps, value)

  def __setitem__(self, i: int, value):
    steps: list[JsonDocStep] = [JsonDocStep.Index(i)]
    self.replace_at(steps, value)

  def __delitem__(self, i: int):
    steps: list[JsonDocStep] = []
    self.del_item_at(steps, i)

  def load[T](self) -> T:
    """全量读入（等价 ``Json.loads[T](全文)``）。"""
    return Json.loads[T](self.text)

  def dump(self) -> str:
    """当前文档快照（``str``）。"""
    return self.text

  def commit(self):
    """将 dirty 变更写回存储（原子替换）。"""
    if not self.writable:
      raise OSError()
    if not self.dirty:
      return
    tmp: str = self.path + ".tmp"
    w: TextIOWrapper = new(tmp, "w")
    w.write(self.text)
    w.close()
    replace(tmp, self.path)
    self.orig = self.text
    self.dirty = False

  def discard(self):
    """放弃未 ``commit`` 的内存变更。"""
    self.text = self.orig
    self.dirty = False
    self.sync_dec()

  def read_str_at(self, steps: list[JsonDocStep]) -> str:
    self._apply_steps(steps)
    seg: span[char] = self.dec.load_str_span()
    return str.from_span(seg)

  def read_int_at(self, steps: list[JsonDocStep]) -> int:
    self._apply_steps(steps)
    return self.dec.load_int()

  def read_bool_at(self, steps: list[JsonDocStep]) -> bool:
    self._apply_steps(steps)
    return self.dec.load_bool()

  def replace_at(self, steps: list[JsonDocStep], value):
    self._apply_steps(steps)
    enc: str = self._encode_for_patch(value)
    self._replace_at_decoder(enc)

  def append_at(self, steps: list[JsonDocStep], item):
    self._apply_steps(steps)
    enc: str = self._encode_for_patch(item)
    self._append_at_array(enc)

  def del_item_at(self, steps: list[JsonDocStep], i: int):
    self._apply_steps(steps)
    self._array_index(i)
    self._delete_at_decoder()

  def _arr_cache_valid(self, open_pos: int) -> bool:
    return self.arr_cache_bracket == open_pos

  def _arr_cache_reset(self, open_pos: int):
    self.arr_cache_bracket = open_pos
    self.arr_cache_offsets = []

  def _reset_dec_for_nav(self):
    """每次懒导航前完整同步 ``dec``（含 ASCII 绑定），避免多次 ``read_*`` 游标残留。"""
    self.sync_dec()

  def _require_writable(self):
    if not self.writable:
      raise OSError()

  def _mark_dirty(self, next: str):
    self.text = next
    self.dirty = True
    self.text_gen += 1
    self.sync_dec()

  def sync_dec(self):
    self.dec.release_ascii()
    self.dec.s = self.text
    self.dec.pos = 0
    self.dec.ascii_bind_done = False
    self.dec.ascii_ok = False
    self.dec.ascii_len = 0
    self.dec.ascii_bytes = None
    self.dec.ascii_bytes_owned = False
    self._arr_cache_reset(-1)
    self.dec.try_bind_ascii()

  def _replace_at_decoder(self, encoded: str):
    self._require_writable()
    start: int = self.dec.pos
    self.dec.skip_value()
    end: int = self.dec.pos
    nxt: str = self.text.replace_slice(start, end, encoded)
    self._mark_dirty(nxt)

  def _delete_at_decoder(self):
    self._require_writable()
    if self.dec.s != self.text:
      self.sync_dec()
    start: int = self.dec.pos
    self.dec.skip_spaces()
    n: int = len(self.dec.s)
    if self.dec.pos >= n:
      self.dec.fail("empty input")
    c: char = self.dec.s[self.dec.pos]
    end: int = self.dec.pos
    if c in "[{":
      close_i: int = self._container_close_index(self.dec.pos)
      end = close_i + 1
      self.dec.pos = end
    else:
      self.dec.skip_value()
      end = self.dec.pos
    self.dec.skip_spaces()
    n = len(self.dec.s)
    if self.dec.pos < n and self.dec.s[self.dec.pos] in ",":
      end += 1
    elif start > 0:
      sn: int = len(self.text)
      scan_hi: int = start - 1
      if scan_hi >= sn:
        scan_hi = sn - 1
      for scan in range(scan_hi, 0, -1):
        c2: char = self.text[scan]
        if c2 in ",":
          start = scan
          break
        if c2 in "[{":
          break
    sn: int = len(self.text)
    if start < 0:
      start = 0
    if start > sn:
      start = sn
    if end < start:
      end = start
    if end > sn:
      end = sn
    nxt: str = self.text.replace_slice(start, end, "")
    self._mark_dirty(nxt)

  def _append_at_array(self, encoded: str):
    self._require_writable()
    self.dec.skip_spaces()
    self.dec.expect_char("[")
    open_pos: int = self.dec.pos - 1
    self.dec.skip_spaces()
    close: int = self._container_close_index(open_pos)
    nxt: str = ""
    if self.dec.pos < close and self.dec.s[self.dec.pos] in "]":
      nxt = self.text.replace_slice(close, close, encoded)
    else:
      mid: str = "," + encoded
      nxt = self.text.replace_slice(close, close, mid)
    self._mark_dirty(nxt)

  def _apply_steps(self, steps: list[JsonDocStep]):
    self._reset_dec_for_nav()
    self.dec.begin_root_object()
    for st in steps:
      match st:  # py2cpp: strict-off
        case new.Field(key):
          self._object_key(key)
        case new.Index(idx):
          self._array_index(idx)


@copyable
@dataclass
class JsonDocCursor[T]:
  """``JsonDocument`` 懒路径节点（``doc.teams[0].name``）。"""

  doc: Pointer[JsonDocument[T]] = None
  steps: list[JsonDocStep] @optional = []

  def __getattr__(self, name: str) -> Self:
    out: Self = self
    out.steps.append(JsonDocStep.Field(name))
    return out

  def __getitem__(self, i: int) -> Self:
    out: Self = self
    out.steps.append(JsonDocStep.Index(i))
    return out

  def __setattr__(self, name: str, value):
    self.steps.append(JsonDocStep.Field(name))
    self.doc.replace_at(self.steps, value)

  def __setitem__(self, i: int, value):
    self.steps.append(JsonDocStep.Index(i))
    self.doc.replace_at(self.steps, value)

  def __delitem__(self, i: int):
    self.doc.del_item_at(self.steps, i)

  def read_str(self) -> str:
    return self.doc.read_str_at(self.steps)

  def read_int(self) -> int:
    return self.doc.read_int_at(self.steps)

  def read_bool(self) -> bool:
    return self.doc.read_bool_at(self.steps)

  def append(self, item):
    self.doc.append_at(self.steps, item)
