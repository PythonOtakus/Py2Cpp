"""JSON 同质子集 + ``JsonEncoder`` / ``JsonDecoder``（``@serializable`` 默认后端）。

单文件：encode/decode 快路径为类方法；``loadU64Le`` 等叶子见 ``util/memory``，``span``→``str`` 用 ``str.fromSpan``。
"""
from __future__ import annotations

from ..builtins import *
from ..util.dict import dict
from ..util.list import list
from ..util.arena import Arena
from ..util.memory import (
  copyArray,
  copyArrayRef,
  loadU64Le,
)
from ..util.span import span
from ..core.exceptions import OSError, ValueError
from ..io.path import Path
from ..numeric.long import long
from ..io import StringIO, TextIOWrapper
from ..io.protocols import TextReaderType, TextWriterType
from ..text import str


_Empty: str = ""
_JsonKeyTag: str = "tag"
_JsonKeyPayload: str = "payload"

_Add8: uint64 = 0x4646464646464646
_Sub8: uint64 = 0x3030303030303030
_Mask8: uint64 = 0x8080808080808080


class JSONDecodeError(ValueError):
  """JSON 解析失败。"""

  pass


@dataclass(eq=False)
class JsonEncoder:
  """JSON ``EncoderType`` 实现；union 变体为 ``{"tag":…,"payload":{…}}``。

  默认在内部 ``char[:]`` 缓冲累积；``take()`` 移动取出 ``str``（``Json.dumps`` 快路径），
  ``finish()`` 经 ``str.fromArray`` 拷贝返回；``flushTo`` 直写 ``TextWriterType``（``Json.dump``）。
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

  def growArray(self, end: int) -> None:
    """预扩容内部 ``char[:]`` 缓冲（``end`` 为目标 ``_at`` 上界）。"""
    self._ensure(end)

  def push(self, piece: str) -> None:
    """追加 JSON 片段到内部 ``char[:]`` 缓冲。"""
    if not piece:
      return
    end: int = self._at + len(piece)
    self._ensure(end)
    self._at = piece.copyTo(self._buf, self._at)

  def _stripTrailingComma(self) -> None:
    if self._at > 0 and self._buf[self._at - 1] == ord(","):
      self._at -= 1

  def _newlineIndent(self) -> str:
    if not self._pretty():
      return ""
    n: int = self.depth * self.indent
    padParts: list[str] = []
    for _ in range(n):
      padParts.append(" ")
    return "\n" + str.concat(padParts)

  def _commaSep(self) -> str:
    if not self._pretty():
      return ","
    return "," + self._newlineIndent()

  def commaSep(self) -> str:
    return self._commaSep()

  @staticmethod
  @immutable
  def encodeStr(s: str) -> str:
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
  def _encodeBool(obj: bool) -> str:
    if obj:
      return "true"
    return "false"

  @staticmethod
  @immutable
  def _encodeFloat(obj: float) -> str:
    return str(obj)

  @staticmethod
  @immutable
  def _encodeInt(obj: int) -> str:
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
  def _encodeListInt(obj: list[int]) -> str:
    parts: list[str] = ["["]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      parts.append(Self._encodeInt(obj[i]))
    parts.append("]")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encodeListLong(obj: list[long]) -> str:
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
  def _encodeListFloat(obj: list[float]) -> str:
    parts: list[str] = ["["]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      parts.append(Self._encodeFloat(obj[i]))
    parts.append("]")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encodeListStr(obj: list[str]) -> str:
    parts: list[str] = ["["]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      parts.append(Self.encodeStr(obj[i]))
    parts.append("]")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encodeDictStrInt(obj: dict[str, int]) -> str:
    parts: list[str] = ["{"]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      k: str = obj.keyAt(i)
      parts.append(Self.encodeStr(k))
      parts.append(":")
      parts.append(Self._encodeInt(obj.valueAt(i)))
    parts.append("}")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encodeDictStrLong(obj: dict[str, long]) -> str:
    parts: list[str] = ["{"]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      k: str = obj.keyAt(i)
      parts.append(Self.encodeStr(k))
      parts.append(":")
      parts.append(str(obj.valueAt(i)))
    parts.append("}")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encodeDictStrFloat(obj: dict[str, float]) -> str:
    parts: list[str] = ["{"]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      k: str = obj.keyAt(i)
      parts.append(Self.encodeStr(k))
      parts.append(":")
      parts.append(Self._encodeFloat(obj.valueAt(i)))
    parts.append("}")
    return str.concat(parts)

  @staticmethod
  @immutable
  def _encodeDictStrStr(obj: dict[str, str]) -> str:
    parts: list[str] = ["{"]
    n: int = len(obj)
    for i in range(n):
      if i > 0:
        parts.append(",")
      k: str = obj.keyAt(i)
      parts.append(Self.encodeStr(k))
      parts.append(":")
      parts.append(Self.encodeStr(obj.valueAt(i)))
    parts.append("}")
    return str.concat(parts)

  def beginObject(self) -> None:
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
      self.sep = self._newlineIndent()

  def endObject(self) -> None:
    self.depth -= 1
    if not self._pretty():
      if self.depth > 0:
        self._stripTrailingComma()
      self._ensure(self._at + 1)
      self._buf[self._at] = ord("}")
      self._at += 1
      if self.depth > 0:
        self.sep = ","
      return
    if self._pretty():
      self.push(self._newlineIndent())
    elif self.depth > 0:
      self._stripTrailingComma()
    self.push("}")
    if self.depth > 0:
      self.sep = self._commaSep()

  def beginArray(self) -> None:
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
      self.sep = self._newlineIndent()

  def endArray(self) -> None:
    self.depth -= 1
    if not self._pretty():
      if self.depth > 0:
        self._stripTrailingComma()
      self._ensure(self._at + 1)
      self._buf[self._at] = ord("]")
      self._at += 1
      self.sep = ","
      return
    if self._pretty():
      self.push(self._newlineIndent())
    elif self.depth > 0:
      self._stripTrailingComma()
    self.push("]")
    self.sep = self._commaSep()

  def dumpKey(self, name: str) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      end: int = self._at + len(name) * 2 + 3
      self._ensure(end)
      self._at = Self.appendQuotedAt(self._buf, self._at, name)
      self._buf[self._at] = ord(":")
      self._at += 1
      self.sep = ""
      return
    colon: str = ": "
    self.push(self.sep)
    self.push(Self.encodeStr(name))
    self.push(colon)
    self.sep = ""

  def dumpInt(self, value: int) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      self._ensure(self._at + 24)
      self._at = Self.appendIntAt(self._buf, self._at, value)
      self.sep = ","
      return
    self.push(self.sep)
    self.push(Self._encodeInt(value))
    self.sep = self._commaSep()

  def dumpLong(self, value: long) -> None:
    if self.sep:
      self.push(self.sep)
    self.push(str(value))
    self.sep = "," if not self._pretty() else self._commaSep()

  def dumpFloat(self, value: float) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      self.push(str(value))
      self.sep = ","
      return
    self.push(self.sep)
    self.push(Self._encodeFloat(value))
    self.sep = self._commaSep()

  def dumpBool(self, value: bool) -> None:
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
    self.push(Self._encodeBool(value))
    self.sep = self._commaSep()

  def dumpStr(self, value: str) -> None:
    if not self._pretty():
      if self.sep:
        self.push(self.sep)
      end: int = self._at + len(value) * 2 + 3
      self._ensure(end)
      self._at = Self.appendQuotedAt(self._buf, self._at, value)
      self.sep = ","
      return
    self.push(self.sep)
    self.push(Self.encodeStr(value))
    self.sep = self._commaSep()

  def dumpFieldInt(self, key: str, value: int) -> None:
    if self._pretty():
      self.dumpKey(key)
      self.dumpInt(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.appendQuotedAt(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    self._at = Self.appendIntAt(self._buf, self._at, value)
    self.sep = ","

  def dumpFieldLong(self, key: str, value: long) -> None:
    if self._pretty():
      self.dumpKey(key)
      self.dumpLong(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.appendQuotedAt(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    self._at = str(value).copyTo(self._buf, self._at)
    self.sep = ","

  def dumpFieldStr(self, key: str, value: str) -> None:
    if self._pretty():
      self.dumpKey(key)
      self.dumpStr(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.appendQuotedAt(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    self._at = Self.appendQuotedAt(self._buf, self._at, value)
    self.sep = ","

  def dumpFieldBool(self, key: str, value: bool) -> None:
    if self._pretty():
      self.dumpKey(key)
      self.dumpBool(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.appendQuotedAt(self._buf, self._at, key)
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

  def dumpFieldListInt(self, key: str, value: list[int]) -> None:
    if self._pretty():
      self.dumpKey(key)
      self.dumpListInt(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.appendQuotedAt(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.appendListAt(self._buf, self._at, value)
    self.sep = ","

  def dumpFieldListStr(self, key: str, value: list[str]) -> None:
    if self._pretty():
      self.dumpKey(key)
      self.dumpListStr(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.appendQuotedAt(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.appendListAt(self._buf, self._at, value)
    self.sep = ","

  def dumpFieldListFloat(self, key: str, value: list[float]) -> None:
    if self._pretty():
      self.dumpKey(key)
      self.dumpListFloat(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.appendQuotedAt(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.appendListAt(self._buf, self._at, value)
    self.sep = ","

  def dumpFieldListLong(self, key: str, value: list[long]) -> None:
    if self._pretty():
      self.dumpKey(key)
      self.dumpListLong(value)
      return
    if self.sep:
      self.push(self.sep)
    self._at = Self.appendQuotedAt(self._buf, self._at, key)
    self._buf[self._at] = ord(":")
    self._at += 1
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.appendListLongAt(self._buf, self._at, value)
    self.sep = ","

  def dumpListInt(self, value: list[int]) -> None:
    if self.sep:
      self.push(self.sep)
    if self._pretty():
      self.push(Self._encodeListInt(value))
      self.sep = self._commaSep()
      return
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.appendListAt(self._buf, self._at, value)
    self.sep = ","

  def dumpListFloat(self, value: list[float]) -> None:
    if self.sep:
      self.push(self.sep)
    if self._pretty():
      self.push(Self._encodeListFloat(value))
      self.sep = self._commaSep()
      return
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.appendListAt(self._buf, self._at, value)
    self.sep = ","

  def dumpListLong(self, value: list[long]) -> None:
    if self.sep:
      self.push(self.sep)
    if self._pretty():
      self.push(Self._encodeListLong(value))
      self.sep = self._commaSep()
      return
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.appendListLongAt(self._buf, self._at, value)
    self.sep = ","

  def dumpListStr(self, value: list[str]) -> None:
    if self.sep:
      self.push(self.sep)
    if self._pretty():
      self.push(Self._encodeListStr(value))
      self.sep = self._commaSep()
      return
    if not value:
      self._ensure(self._at + 2)
      self._buf[self._at] = ord("[")
      self._at += 1
      self._buf[self._at] = ord("]")
      self._at += 1
    else:
      self._at = Self.appendListAt(self._buf, self._at, value)
    self.sep = ","

  def dumpDictStrInt(self, value: dict[str, int]) -> None:
    self.push(self.sep)
    if self._pretty():
      self.push(Self._encodeDictStrInt(value))
    else:
      self.push(Self.fastEncode(value))
    self.sep = self._commaSep()

  def dumpDictStrLong(self, value: dict[str, long]) -> None:
    self.push(self.sep)
    if self._pretty():
      self.push(Self._encodeDictStrLong(value))
    else:
      self.push(Self.fastEncode(value))
    self.sep = self._commaSep()

  def dumpDictStrStr(self, value: dict[str, str]) -> None:
    self.push(self.sep)
    if self._pretty():
      self.push(Self._encodeDictStrStr(value))
    else:
      self.push(Self.fastEncode(value))
    self.sep = self._commaSep()

  def dumpDictStrFloat(self, value: dict[str, float]) -> None:
    self.push(self.sep)
    if self._pretty():
      self.push(Self._encodeDictStrFloat(value))
    else:
      self.push(Self.fastEncode(value))
    self.sep = self._commaSep()

  def beginVariant(self, tag: str) -> None:
    self.beginObject()
    self.dumpFieldStr(_JsonKeyTag, tag)
    self.dumpKey(_JsonKeyPayload)
    self.beginObject()

  def endVariant(self) -> None:
    self.endObject()
    self.endObject()

  def finish(self) -> str:
    if self._at == 0:
      return ""
    return str.fromArray(self._buf, self._at)

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
  def flushTo(self, fp: StringIO) -> None:
    if self._at == 0:
      return
    fp.write(self._buf, self._at)

  @overload
  def flushTo(self, fp: TextIOWrapper) -> None:
    if self._at == 0:
      return
    fp.write(self._buf, self._at)

  @staticmethod
  def appendIntAt(buf: char[:], at: int, obj: int) -> int:
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
  def appendQuotedAt(buf: char[:], at: int, s: str) -> int:
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
  def appendLongAt(buf: char[:], at: int, obj: long) -> int:
    """``long`` 十进制文本 → ``buf[at:]``（``str(obj)`` 语义）。"""
    return str(obj).copyTo(buf, at)


  @staticmethod
  def appendFloatAt(buf: char[:], at: int, obj: float) -> int:
    """``float`` 文本 → ``buf[at:]``（``str(obj)`` 语义）。"""
    return str(obj).copyTo(buf, at)


  @staticmethod
  def appendListIntAt(buf: char[:], at: int, obj: list[int]) -> int:
    """JSON ``list[int]`` → ``buf[at:]``，返回新尾下标。"""
    cnt: int = len(obj)
    buf.reserve(at + (cnt * 12) + 2)
    buf[at] = ord("[")
    at += 1
    for i in range(cnt):
      if i > 0:
        buf[at] = ord(",")
        at += 1
      at = Self.appendIntAt(buf, at, obj[i])
    buf[at] = ord("]")
    at += 1
    return at


  @staticmethod
  def appendListStrAt(buf: char[:], at: int, obj: list[str]) -> int:
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
      at = Self.appendQuotedAt(buf, at, obj[i])
    buf[at] = ord("]")
    at += 1
    return at


  @staticmethod
  def appendListFloatAt(buf: char[:], at: int, obj: list[float]) -> int:
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
      at = Self.appendFloatAt(buf, at, obj[i])
    buf[at] = ord("]")
    at += 1
    return at


  @staticmethod
  def appendListLongAt(buf: char[:], at: int, obj: list[long]) -> int:
    """JSON ``list[long]`` → ``buf[at:]``，返回新尾下标。"""
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
      at = Self.appendLongAt(buf, at, obj[i])
    buf[at] = ord("]")
    at += 1
    return at


  @staticmethod
  @overload
  @staticmethod
  def appendListAt(buf: char[:], at: int, obj: list[int]) -> int:
    return Self.appendListIntAt(buf, at, obj)


  @staticmethod
  @overload
  @staticmethod
  def appendListAt(buf: char[:], at: int, obj: list[str]) -> int:
    return Self.appendListStrAt(buf, at, obj)


  @staticmethod
  @overload
  @staticmethod
  def appendListAt(buf: char[:], at: int, obj: list[float]) -> int:
    return Self.appendListFloatAt(buf, at, obj)


  @staticmethod
  def _appendDictStrIntAt(buf: char[:], at: int, obj: dict[str, int]) -> int:
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
      k: str = obj.keyAt(i)
      at = Self.appendQuotedAt(buf, at, k)
      buf[at] = ord(":")
      at += 1
      at = Self.appendIntAt(buf, at, obj.valueAt(i))
    buf[at] = ord("}")
    at += 1
    return at


  @staticmethod
  def _appendDictStrStrAt(buf: char[:], at: int, obj: dict[str, str]) -> int:
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      k: str = obj.keyAt(i)
      v: str = obj.valueAt(i)
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
      k: str = obj.keyAt(i)
      at = Self.appendQuotedAt(buf, at, k)
      buf[at] = ord(":")
      at += 1
      at = Self.appendQuotedAt(buf, at, obj.valueAt(i))
    buf[at] = ord("}")
    at += 1
    return at


  @staticmethod
  def _appendDictStrLongAt(buf: char[:], at: int, obj: dict[str, long]) -> int:
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      k: str = obj.keyAt(i)
      est += (len(k) * 2) + len(str(obj.valueAt(i))) + 5
    buf.reserve(est)
    buf[at] = ord("{")
    at += 1
    first: bool = True
    for i in range(cnt):
      if not first:
        buf[at] = ord(",")
        at += 1
      first = False
      k: str = obj.keyAt(i)
      at = Self.appendQuotedAt(buf, at, k)
      buf[at] = ord(":")
      at += 1
      at = Self.appendLongAt(buf, at, obj.valueAt(i))
    buf[at] = ord("}")
    at += 1
    return at


  @staticmethod
  def _appendDictStrFloatAt(buf: char[:], at: int, obj: dict[str, float]) -> int:
    cnt: int = len(obj)
    est: int = at + 2
    for i in range(cnt):
      k: str = obj.keyAt(i)
      est += (len(k) * 2) + len(str(obj.valueAt(i))) + 5
    buf.reserve(est)
    buf[at] = ord("{")
    at += 1
    first: bool = True
    for i in range(cnt):
      if not first:
        buf[at] = ord(",")
        at += 1
      first = False
      k: str = obj.keyAt(i)
      at = Self.appendQuotedAt(buf, at, k)
      buf[at] = ord(":")
      at += 1
      at = Self.appendFloatAt(buf, at, obj.valueAt(i))
    buf[at] = ord("}")
    at += 1
    return at
  @staticmethod
  @overload
  @staticmethod
  def fastEncode(obj: list[int]) -> str:
    cnt: int = len(obj)
    buf: char[:] = new((cnt * 12) + 2)
    at: int = Self.appendListIntAt(buf, 0, obj)
    return str.fromArray(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fastEncode(obj: list[str]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      est += (len(obj[i]) * 2) + 3
    buf: char[:] = new(est)
    at: int = Self.appendListStrAt(buf, 0, obj)
    return str.fromArray(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fastEncode(obj: list[float]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      est += len(str(obj[i])) + 1
    buf: char[:] = new(est)
    at: int = Self.appendListFloatAt(buf, 0, obj)
    return str.fromArray(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fastEncode(obj: list[long]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      est += len(str(obj[i])) + 1
    buf: char[:] = new(est)
    at: int = Self.appendListLongAt(buf, 0, obj)
    return str.fromArray(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fastEncode(obj: dict[str, int]) -> str:
    cnt: int = len(obj)
    buf: char[:] = new((cnt * 32) + 2)
    at: int = Self._appendDictStrIntAt(buf, 0, obj)
    return str.fromArray(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fastEncode(obj: dict[str, str]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      k: str = obj.keyAt(i)
      v: str = obj.valueAt(i)
      est += (len(k) * 2) + (len(v) * 2) + 5
    buf: char[:] = new(est)
    at: int = Self._appendDictStrStrAt(buf, 0, obj)
    return str.fromArray(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fastEncode(obj: dict[str, long]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      k: str = obj.keyAt(i)
      est += (len(k) * 2) + len(str(obj.valueAt(i))) + 5
    buf: char[:] = new(est)
    at: int = Self._appendDictStrLongAt(buf, 0, obj)
    return str.fromArray(buf, at)


  @staticmethod
  @overload
  @staticmethod
  def fastEncode(obj: dict[str, float]) -> str:
    cnt: int = len(obj)
    est: int = 2
    for i in range(cnt):
      k: str = obj.keyAt(i)
      est += (len(k) * 2) + len(str(obj.valueAt(i))) + 5
    buf: char[:] = new(est)
    at: int = Self._appendDictStrFloatAt(buf, 0, obj)
    return str.fromArray(buf, at)


@copyable
@dataclass(eq=False, repr=False)
class JsonDecoder:
  """JSON ``DecoderType`` 实现；游标保存在 ``pos``。"""

  s: str = ""
  pos: int = 0
  asciiBindDone: bool = False
  asciiOk: bool = False
  asciiLen: int = 0
  asciiBytes: Pointer[char] = None
  asciiBytesOwned: bool = False
  strArena: Arena = new()
  strArenaActive: bool = False

  def __repr__(self) -> str:
    return f"JsonDecoder(s={self.s!r}, pos={self.pos})"

  def __copy__(self, other: Self):
    self.s = other.s
    self.pos = other.pos
    self.asciiBindDone = False
    self.asciiOk = False
    self.asciiLen = 0
    self.asciiBytes = None
    self.asciiBytesOwned = False
    self.strArena.reset()
    self.strArenaActive = False

  @staticmethod
  @immutable
  def _isWsByte(c: int) -> bool:
    return c in {9, 10, 13, 32}

  @staticmethod
  @immutable
  def _chunkByte(chunk: uint64, k: int) -> int:
    sh: uint64 = k * 8
    return int((chunk >> sh) & 0xFF)

  @staticmethod
  @immutable
  def _chunkAllWs(chunk: uint64) -> bool:
    for k in range(8):
      if not Self._isWsByte(Self._chunkByte(chunk, k)):
        return False
    return True

  @staticmethod
  @immutable
  def _swarIs8digits(chunk: uint64) -> bool:
    t: uint64 = ((chunk + _Add8) | (chunk - _Sub8)) & _Mask8
    return not t

  @staticmethod
  @immutable
  def _swarParse8(chunk: uint64) -> int:
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

  def tryBindAscii(self) -> None:
    """尝试绑定 ASCII 字节视图（纯 Python；``ord`` / ``srcChar`` 译后内联）。"""
    if self.asciiBindDone:
      return
    self.asciiBindDone = True
    n: int = self.srcLen()
    if n <= 0:
      return
    for i in range(n):
      c: char = self.srcChar(i)
      if int(c) < 0 or int(c) > 127:
        self.asciiOk = False
        return
    self.asciiBytes = self.s.view.at(0)
    self.asciiBytesOwned = False
    self.asciiLen = n
    self.asciiOk = True

  def releaseAscii(self) -> None:
    """释放 ASCII 视图标志。"""
    self.asciiOk = False
    self.asciiBindDone = False
    self.asciiLen = 0
    self.asciiBytes = None
    self.asciiBytesOwned = False

  def skipWs(self) -> None:
    """跳过 JSON 空白（``_skipWs`` 公开入口）。"""
    self._skipWs()

  def _skipWs(self) -> None:
    src: span[char] = self.srcView()
    n: int = len(src)
    for j in range(self.pos, n):
      if src[j] not in "\t\n\r ":
        self.pos = j
        return
    self.pos = n

  def expectChar(self, ch: str) -> None:
    if self.pos >= len(self.s) or self.s[self.pos] not in ch:
      self.fail("unexpected char")
    self.pos += 1

  def _parseStringValue(self, out: list[str] @ref) -> None:
    self._skipWs()
    if self.pos >= len(self.s) or self.s[self.pos] not in '"':
      self.fail("expected string")
    self.pos += 1
    parts: list[str] = []
    while self.pos < len(self.s):
      if self.s[self.pos] in '"':
        out.append(_Empty.join(parts))
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

  def _scanJsonNumber(self, startOut: list[int] @ref, endOut: list[int] @ref) -> None:
    """写入数字 token 的 ``[start, end)``（``end`` 为首个非数字字符下标）。"""
    self._skipWs()
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
    startOut.append(start)
    endOut.append(i)
    self.pos = i

  def _parseIntValue(self, out: list[int] @ref) -> None:
    startOut: list[int] = []
    endOut: list[int] = []
    self._scanJsonNumber(startOut, endOut)
    start: int = startOut[0]
    end: int = endOut[0]
    for j in range(start, end):
      if self.s[j] in ".eE":
        self.fail("expected int")
    tok: str = self.s[start:end]
    out.append(int(tok))

  def _parseLongValue(self, out: list[long] @ref) -> None:
    startOut: list[int] = []
    endOut: list[int] = []
    self._scanJsonNumber(startOut, endOut)
    start: int = startOut[0]
    end: int = endOut[0]
    for j in range(start, end):
      if self.s[j] in ".eE":
        self.fail("expected int")
    tok: str = self.s[start:end]
    out.append(long(tok))

  def _parseFloatValue(self, out: list[float] @ref) -> None:
    startOut: list[int] = []
    endOut: list[int] = []
    self._scanJsonNumber(startOut, endOut)
    start: int = startOut[0]
    end: int = endOut[0]
    tok: str = self.s[start:end]
    out.append(float(tok))

  def _skipNumberValue(self) -> None:
    _buf: list[float] = []
    self._parseFloatValue(_buf)

  def _parseBoolValue(self, out: list[bool] @ref) -> None:
    self._skipWs()
    if self.pos + 4 <= len(self.s) and self.s[self.pos : self.pos + 4] == "true":
      out.append(True)
      self.pos += 4
      return
    if self.pos + 5 <= len(self.s) and self.s[self.pos : self.pos + 5] == "false":
      out.append(False)
      self.pos += 5
      return
    self.fail("expected bool")

  def _skipStringValue(self) -> None:
    """跳过 JSON 字符串字面量（不构造 ``str``，``skipValue`` / 数组导航热路径）。"""
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

  def _skipValue(self) -> None:
    if self.trySkipValueAscii():
      return
    self._skipWs()
    if self.pos >= len(self.s):
      self.fail("empty input")
    ch: char = self.s[self.pos]
    match ch:
      case '"':
        self._skipStringValue()
        return
      case 't':
        _skipBb: list[bool] = []
        self._parseBoolValue(_skipBb)
        return
      case 'f':
        _skipBf: list[bool] = []
        self._parseBoolValue(_skipBf)
        return
      case 'n':
        if self.pos + 4 <= len(self.s) and self.s[self.pos : self.pos + 4] == "null":
          self.pos += 4
          return
        self.fail("expected null")
      case '-' | '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9':
        self._skipNumberValue()
        return
      case '[':
        depth: int = 0
        for _ in range(len(self.s)):
          if self.pos >= len(self.s):
            break
          chArr: char = self.s[self.pos]
          match chArr:
            case '[':
              depth += 1
            case ']':
              depth -= 1
              if depth == 0:
                self.pos += 1
                return
            case '"':
              self._skipStringValue()
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
          chObj: char = self.s[self.pos]
          match chObj:
            case '{':
              depth2 += 1
            case '}':
              depth2 -= 1
              if depth2 == 0:
                self.pos += 1
                return
            case '"':
              self._skipStringValue()
              continue
            case _:
              pass
          self.pos += 1
        self.fail("unterminated object")
      case _:
        self.fail("bad value")

  @staticmethod
  def fromText(text: str) -> Self:
    dec: Self = new()
    dec.s = text
    dec.pos = 0
    return dec

  def srcView(self) -> span[char]:
    """输入 ``s`` 码点只读视图（``serde`` 热路径）。"""
    return self.s.view

  def srcLen(self) -> int:
    """``srcView`` 长度（供生成 C++ 快路径，勿经 ``PyStr.__getitem__``）。"""
    return len(self.srcView())

  def srcChar(self, i: int) -> char:
    """``_src_view[i]``（``i`` 与 ``pos`` 同属输入 ``s``）。"""
    return self.srcView()[i]

  def srcAsciiOk(self) -> bool:
    """输入是否已绑定紧凑 ASCII 字节视图（仅 ``loads`` 热路径 C++ 使用）。"""
    return self.asciiOk

  def enableStrArena(self) -> None:
    """``loads`` 热路径：按需启用 ``strArena``（纯 ``int``/``list[int]`` 等勿调用）。"""
    self.strArenaActive = True
    sl: int = self.srcLen()
    if sl > 0:
      self.strArena.reserve(sl // 2)

  def mark(self) -> int:
    return self.pos

  def restore(self, m: int) -> None:
    self.pos = m

  def _sliceAt(self, start: int, end: int) -> span[char]:
    """半开区间 ``[start, end)``，下标与 ``pos`` 同属 ``s``。"""
    return self.srcView()[start:end]

  def skipEmptyArray(self) -> None:
    """假定游标已在 ``[``；若为 ``[]`` 则跳过并返回。"""
    self._skipWs()
    n: int = self.srcLen()
    if self.pos < n and self.srcChar(self.pos) in "[":
      if self.pos + 1 < n and self.srcChar(self.pos + 1) in "]":
        self.pos += 2
        return
    self.fail("expected empty array")

  def loadStrSpan(self) -> span[char]:
    """无转义 JSON 字符串：返回码点视图；有转义则物化后取其 ``codes.view``。"""
    self._skipWs()
    return self._loadStrSpanBound()

  def _loadStrSpanBound(self) -> span[char]:
    return self.loadStrSpanAscii()

  def skipSpaces(self) -> None:
    self._skipWs()

  def readQuoted(self) -> str:
    buf: list[str] = []
    self._parseStringValue(buf)
    return buf[0]

  def beginRootObject(self) -> None:
    self._skipWs()
    self.expectChar("{")

  def tryMatchKey(self, expected: str) -> bool:
    """无转义键：原位匹配 ``,"expected":``，不匹配则恢复游标（不分配 ``key``）。"""
    if self.asciiOk:
      return self._tryMatchKeyAsciiBound(expected)
    return self._tryMatchKeyChars(expected)

  def _tryMatchKeyChars(self, expected: str) -> bool:
    """非 ASCII 文档上的 ``tryMatchKey``（``srcChar`` 路径）。"""
    mark: int = self.pos
    self._skipWs()
    n: int = self.srcLen()
    if self.pos < n and self.srcChar(self.pos) in ",":
      self.pos += 1
      self._skipWs()
      n = self.srcLen()
    if self.pos >= n or self.srcChar(self.pos) not in '"':
      self.pos = mark
      return False
    self.pos += 1
    elen: int = len(expected)
    for i in range(elen):
      if self.pos >= n or self.srcChar(self.pos) != expected[i]:
        self.pos = mark
        return False
      self.pos += 1
    if self.pos >= n or self.srcChar(self.pos) not in '"':
      self.pos = mark
      return False
    self.pos += 1
    self._skipWs()
    n = self.srcLen()
    if self.pos >= n or self.srcChar(self.pos) not in ":":
      self.pos = mark
      return False
    self.pos += 1
    return True

  def skipField(self) -> None:
    if self.trySkipFieldAscii():
      return
    _k: str = self.loadKey()
    self.skipValue()

  def loadKey(self) -> str:
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] == ord(","):
      self.pos += 1
      self._skipWs()
    if self.pos >= len(self.s) or self.s[self.pos] != ord('"'):
      self.fail("expected string key")
    self.pos += 1
    start: int = self.pos
    h: int = 0
    while self.pos < len(self.s):
      c: char = self.s[self.pos]
      if c == ord('"'):
        key = self.s[start:self.pos]
        key.cacheHash(h)
        self.pos += 1
        self._skipWs()
        self.expectChar(":")
        return key
      if c == ord("\\"):
        self.pos = start - 1
        kbuf2: list[str] = []
        self._parseStringValue(kbuf2)
        key = kbuf2[0]
        self._skipWs()
        self.expectChar(":")
        return key
      h = h * 31 + int(c)
      self.pos += 1
    self.fail("unterminated string")
    return ""

  def skipValue(self) -> None:
    self._skipValue()

  def _parseIntAt(self) -> int:
    n: int = self.srcLen()
    neg: bool = False
    if self.pos < n and self.srcChar(self.pos) in "-":
      neg = True
      self.pos += 1
    val: int = 0
    anyD: bool = False
    while self.pos < n:
      c: char = self.srcChar(self.pos)
      if c not in "0123456789":
        break
      val *= 10
      val += int(c) - ord("0")
      anyD = True
      self.pos += 1
    if not anyD:
      self.fail("expected int")
    if neg:
      val = -val
    return val

  def parseIntAt(self) -> int:
    """假定游标已在 JSON 数值首字符；不跳过前导空白。"""
    return self._parseIntAt()

  def _parseIntAtBound(self) -> int:
    """ASCII 快路径：``scan.parseIntAtAscii`` 叶子。"""
    return self.parseIntAtAscii()

  def _skipWsBound(self) -> None:
    """ASCII bound 空白跳过：``scan.skipWsBound`` 叶子。"""
    self.skipWsBound()

  def _strAssignFromSegBound(self, seg: span[char]) -> str:
    """``seg`` → 新 ``str``（``scan.strAssignFromSeg`` 叶子）。"""
    return self.strAssignFromSeg(seg)

  def _strAssignFromSegSlotBound(self, slot: Pointer[str], seg: span[char]) -> None:
    init(slot, self.strAssignFromSeg(seg))

  def _tryMatchKeyAsciiBound(self, expected: str) -> bool:
    mark: int = self.pos
    self._skipWsBound()
    n: int = self.srcLen()
    if self.pos < n and self.srcChar(self.pos) in ",":
      self.pos += 1
      self._skipWsBound()
      n = self.srcLen()
    if self.pos >= n or self.srcChar(self.pos) not in '"':
      self.pos = mark
      return False
    self.pos += 1
    elen: int = len(expected)
    for i in range(elen):
      if self.pos >= n or self.srcChar(self.pos) != expected[i]:
        self.pos = mark
        return False
      self.pos += 1
    if self.pos >= n or self.srcChar(self.pos) not in '"':
      self.pos = mark
      return False
    self.pos += 1
    self._skipWsBound()
    n = self.srcLen()
    if self.pos >= n or self.srcChar(self.pos) not in ":":
      self.pos = mark
      return False
    self.pos += 1
    return True

  def loadContainer[Root](self) -> Root:
    """``list[…]`` / ``dict[str, …]`` wildcard 容器（``Json.loads`` 分派）。"""
    if Root is list[...]:
      return self.loadListElement[Root.Element]()
    elif Root is dict[str, ...]:
      return self.loadDictElement[Root.Value]()

  def loadGeneric[Root](self) -> Root:
    return Root.deserialize(self)

  def loadValue[Root](self) -> Root:
    """递归解码一个值，供泛型容器元素复用。"""
    if Root is int:
      return self.loadInt()
    elif Root is long:
      return self.loadLong()
    elif Root is float:
      return self.loadFloat()
    elif Root is str:
      return self.loadStr()
    elif Root is bool:
      return self.loadBool()
    elif Root is list[int]:
      return self.loadListInt()
    elif Root is list[long]:
      return self.loadListLong()
    elif Root is list[str]:
      return self.loadListStr()
    elif Root is list[float]:
      return self.loadListFloat()
    elif Root is list[...]:
      return self.loadContainer[Root]()
    elif Root is dict[str, int]:
      return self.loadDictStrInt()
    elif Root is dict[str, long]:
      return self.loadDictStrLong()
    elif Root is dict[str, str]:
      return self.loadDictStrStr()
    elif Root is dict[str, float]:
      return self.loadDictStrFloat()
    elif Root is dict[str, ...]:
      return self.loadContainer[Root]()
    else:
      return self.loadGeneric[Root]()

  def loadListElement[U](self) -> list[U]:
    out: list[U] = []
    self.beginArray()
    self.skipSpaces()
    if self.atArrayEnd():
      return out
    est: int = (self.srcLen() - self.pos) // 48
    if est > 0:
      out.capacity = est
    while True:
      out.append(self.loadValue[U]())
      self.skipSpaces()
      if self.atArrayEnd():
        return out
      self.expectChar(",")
      self.skipSpaces()

  def loadDictElement[V](self) -> dict[str, V]:
    out: dict[str, V] = {}
    self.skipSpaces()
    self.expectChar("{")
    self.skipSpaces()
    n: int = self.srcLen()
    if self.pos < n and self.srcChar(self.pos) in "}":
      self.pos += 1
      return out
    while True:
      k: str = self.loadKey()
      self.skipSpaces()
      v: V = self.loadValue[V]()
      out[k] = v
      self.skipSpaces()
      n = self.srcLen()
      if self.pos < n and self.srcChar(self.pos) in "}":
        self.pos += 1
        return out
      self.expectChar(",")
      self.skipSpaces()

  def _parseLongAt(self) -> long:
    n: int = self.srcLen()
    start: int = self.pos
    if self.pos < n and self.srcChar(self.pos) in "-":
      self.pos += 1
    anyD: bool = False
    while self.pos < n:
      c: char = self.srcChar(self.pos)
      if c not in "0123456789":
        break
      anyD = True
      self.pos += 1
    if not anyD:
      self.fail("expected int")
    tok: str = self.s[start:self.pos]
    return new(tok)

  def parseLongAt(self) -> long:
    """假定游标已在 JSON 数值首字符；不跳过前导空白。"""
    return self._parseLongAt()

  def parseFloatAt(self) -> float:
    """假定游标已在 JSON 数值首字符；不跳过前导空白。"""
    fbuf: list[float] = []
    self._parseFloatValue(fbuf)
    return fbuf[0]

  def parseBoolAt(self) -> bool:
    """假定游标已在 ``true``/``false`` 首字符。"""
    return self._parseBoolAt()

  def loadListIntValue(self) -> list[int]:
    """假定游标已在 ``[``。"""
    return self._loadListIntAt()

  def loadListLongValue(self) -> list[long]:
    """假定游标已在 ``[``。"""
    return self._loadListLongAt()

  def loadListStrValue(self) -> list[str]:
    """假定游标已在 ``[``。"""
    return self._loadListStrAt()

  def loadListFloatValue(self) -> list[float]:
    """假定游标已在 ``[``。"""
    return self._loadListFloatAt()

  def loadInt(self) -> int:
    self._skipWs()
    return self._parseIntAt()

  def loadLong(self) -> long:
    self._skipWs()
    return self._parseLongAt()

  def loadFloat(self) -> float:
    self._skipWs()
    fbuf: list[float] = []
    self._parseFloatValue(fbuf)
    return fbuf[0]

  def loadStringSlow(self) -> str:
    """含转义等复杂 JSON 字符串。"""
    sbuf: list[str] = []
    self._parseStringValue(sbuf)
    return sbuf[0]

  def loadStr(self) -> str:
    self._skipWs()
    if self.pos >= len(self.s) or self.s[self.pos] != ord('"'):
      return self.loadStringSlow()
    self.pos += 1
    start: int = self.pos
    while self.pos < len(self.s):
      if self.s[self.pos] == ord('"'):
        raw: str = self.s[start:self.pos]
        self.pos += 1
        return raw
      if self.s[self.pos] == ord("\\"):
        self.pos = start - 1
        return self.loadStringSlow()
      self.pos += 1
    self.fail("unterminated string")
    return ""

  def _parseBoolAt(self) -> bool:
    if self.pos + 4 <= len(self.s) and self.s[self.pos : self.pos + 4] == "true":
      self.pos += 4
      return True
    if self.pos + 5 <= len(self.s) and self.s[self.pos : self.pos + 5] == "false":
      self.pos += 5
      return False
    self.fail("expected bool")
    return False

  def loadBool(self) -> bool:
    bbuf: list[bool] = []
    self._parseBoolValue(bbuf)
    return bbuf[0]

  def _preallocListAscii(self, out: list[int] @ref, bytesPerElem: int) -> None:
    est: int = (self.asciiLen - self.pos) // bytesPerElem
    if est > 0:
      out.capacity = est

  def _preallocDictAscii(self, out: dict[str, int] @ref, bytesPerEntry: int) -> None:
    est: int = (self.asciiLen - self.pos) // bytesPerEntry
    if est > 0:
      cap: int = est * 3 // 2 + 1
      if cap < 8:
        cap = 8
      out.capacity = cap

  def _asciiByteIs(self, n: int, ch: str) -> bool:
    if self.pos >= n:
      return False
    ec: char = ch[0]
    if self.asciiOk:
      return self.byteAt(self.pos) == int(ec)
    return self.srcChar(self.pos) == ec

  def _loadListIntAsciiLoop(self, out: list[int] @ref) -> None:
    n: int = self.asciiLen
    self._preallocListAscii(out, 6)
    while True:
      slot: Pointer[int] = out.serdePushSlot()
      init(slot, self._parseIntAtBound())
      out.serdeCommitPush()
      self._skipWsBound()
      n = self.asciiLen
      if self._asciiByteIs(n, "]"):
        self.pos += 1
        return
      if self.pos >= n or not self._asciiByteIs(n, ","):
        self.fail("expected , or ]")
      self.pos += 1
      self._skipWsBound()

  def _loadListIntAsciiLoopRef(self, out: list[int] @ref) -> None:
    while True:
      out.append(self.parseIntAt())
      self.skipWs()
      if self.pos < self.srcLen() and self.srcChar(self.pos) in "]":
        self.pos += 1
        return
      self.expectChar(",")
      self.skipWs()

  def _loadListStrAsciiLoop(self, out: list[str] @ref) -> None:
    n: int = self.asciiLen
    est: int = (self.asciiLen - self.pos) // 8
    if est > 0:
      out.capacity = est
    while True:
      seg: span[char] = self._loadStrSpanBound()
      slot: Pointer[str] = out.serdePushSlot()
      self._strAssignFromSegSlotBound(slot, seg)
      out.serdeCommitPush()
      self._skipWsBound()
      n = self.asciiLen
      if self._asciiByteIs(n, "]"):
        self.pos += 1
        return
      if self.pos >= n or not self._asciiByteIs(n, ","):
        self.fail("expected , or ]")
      self.pos += 1
      self._skipWsBound()

  def _loadListStrAsciiLoopRef(self, out: list[str] @ref) -> None:
    while True:
      out.append(self.loadStr())
      self.skipWs()
      if self.pos < self.srcLen() and self.srcChar(self.pos) in "]":
        self.pos += 1
        return
      self.expectChar(",")
      self.skipWs()

  def _dictStrIntPushAscii(self, out: dict[str, int] @ref) -> None:
    kseg: span[char] = self._loadStrSpanBound()
    k: str = self._strAssignFromSegBound(kseg)
    self._skipWsBound()
    n: int = self.asciiLen
    if self.pos >= n or not self._asciiByteIs(n, ":"):
      self.fail("expected :")
    self.pos += 1
    out[k] = self._parseIntAtBound()

  def _dictStrIntPushAsciiRef(self, out: dict[str, int] @ref) -> None:
    seg: span[char] = self.loadStrSpan()
    k: str = str.fromSpan(seg)
    self.skipWs()
    self.expectChar(":")
    out[k] = self.parseIntAt()

  def _loadDictStrIntAsciiLoop(self, out: dict[str, int] @ref) -> None:
    n: int = self.asciiLen
    self._preallocDictAscii(out, 12)
    while True:
      self._dictStrIntPushAscii(out)
      self._skipWsBound()
      n = self.asciiLen
      if self._asciiByteIs(n, "}"):
        self.pos += 1
        return
      if self.pos >= n or not self._asciiByteIs(n, ","):
        self.fail("expected , or }")
      self.pos += 1
      self._skipWsBound()

  def _loadDictStrIntAsciiLoopRef(self, out: dict[str, int] @ref) -> None:
    while True:
      self._dictStrIntPushAsciiRef(out)
      self.skipWs()
      if self.pos < self.srcLen() and self.srcChar(self.pos) in "}":
        self.pos += 1
        return
      self.expectChar(",")
      self.skipWs()

  def _dictStrStrPushAscii(self, out: dict[str, str] @ref) -> None:
    kseg: span[char] = self._loadStrSpanBound()
    k: str = self._strAssignFromSegBound(kseg)
    self._skipWsBound()
    n: int = self.asciiLen
    if self.pos >= n or not self._asciiByteIs(n, ":"):
      self.fail("expected :")
    self.pos += 1
    vseg: span[char] = self._loadStrSpanBound()
    v: str = self._strAssignFromSegBound(vseg)
    out[k] = v

  def _dictStrStrPushAsciiRef(self, out: dict[str, str] @ref) -> None:
    kseg: span[char] = self.loadStrSpan()
    k: str = str.fromSpan(kseg)
    self.skipWs()
    self.expectChar(":")
    vseg: span[char] = self.loadStrSpan()
    v: str = str.fromSpan(vseg)
    out[k] = v

  def _loadDictStrStrAsciiLoop(self, out: dict[str, str] @ref) -> None:
    n: int = self.asciiLen
    est: int = (self.asciiLen - self.pos) // 14
    if est > 0:
      cap: int = est * 3 // 2 + 1
      if cap < 8:
        cap = 8
      out.capacity = cap
    while True:
      self._dictStrStrPushAscii(out)
      self._skipWsBound()
      n = self.asciiLen
      if self._asciiByteIs(n, "}"):
        self.pos += 1
        return
      if self.pos >= n or not self._asciiByteIs(n, ","):
        self.fail("expected , or }")
      self.pos += 1
      self._skipWsBound()

  def _loadDictStrStrAsciiLoopRef(self, out: dict[str, str] @ref) -> None:
    while True:
      self._dictStrStrPushAsciiRef(out)
      self.skipWs()
      if self.pos < self.srcLen() and self.srcChar(self.pos) in "}":
        self.pos += 1
        return
      self.expectChar(",")
      self.skipWs()

  def _dictStrLongPushAscii(self, out: dict[str, long] @ref) -> None:
    kseg: span[char] = self._loadStrSpanBound()
    k: str = self._strAssignFromSegBound(kseg)
    self._skipWsBound()
    n: int = self.asciiLen
    if self.pos >= n or not self._asciiByteIs(n, ":"):
      self.fail("expected :")
    self.pos += 1
    out[k] = self.parseLongAt()

  def _dictStrLongPushAsciiRef(self, out: dict[str, long] @ref) -> None:
    seg: span[char] = self.loadStrSpan()
    k: str = str.fromSpan(seg)
    self.skipWs()
    self.expectChar(":")
    out[k] = self.parseLongAt()

  def _loadDictStrLongAsciiLoop(self, out: dict[str, long] @ref) -> None:
    n: int = self.asciiLen
    est: int = (self.asciiLen - self.pos) // 12
    if est > 0:
      cap: int = est * 3 // 2 + 1
      if cap < 8:
        cap = 8
      out.capacity = cap
    while True:
      self._dictStrLongPushAscii(out)
      self._skipWsBound()
      n = self.asciiLen
      if self._asciiByteIs(n, "}"):
        self.pos += 1
        return
      if self.pos >= n or not self._asciiByteIs(n, ","):
        self.fail("expected , or }")
      self.pos += 1
      self._skipWsBound()

  def _loadDictStrLongAsciiLoopRef(self, out: dict[str, long] @ref) -> None:
    while True:
      self._dictStrLongPushAsciiRef(out)
      self.skipWs()
      if self.pos < self.srcLen() and self.srcChar(self.pos) in "}":
        self.pos += 1
        return
      self.expectChar(",")
      self.skipWs()

  def _dictStrFloatPushAscii(self, out: dict[str, float] @ref) -> None:
    kseg: span[char] = self._loadStrSpanBound()
    k: str = self._strAssignFromSegBound(kseg)
    self._skipWsBound()
    n: int = self.asciiLen
    if self.pos >= n or not self._asciiByteIs(n, ":"):
      self.fail("expected :")
    self.pos += 1
    out[k] = self.parseFloatAt()

  def _dictStrFloatPushAsciiRef(self, out: dict[str, float] @ref) -> None:
    seg: span[char] = self.loadStrSpan()
    k: str = str.fromSpan(seg)
    self.skipWs()
    self.expectChar(":")
    out[k] = self.parseFloatAt()

  def _loadDictStrFloatAsciiLoop(self, out: dict[str, float] @ref) -> None:
    n: int = self.asciiLen
    est: int = (self.asciiLen - self.pos) // 16
    if est > 0:
      cap: int = est * 3 // 2 + 1
      if cap < 8:
        cap = 8
      out.capacity = cap
    while True:
      self._dictStrFloatPushAscii(out)
      self._skipWsBound()
      n = self.asciiLen
      if self._asciiByteIs(n, "}"):
        self.pos += 1
        return
      if self.pos >= n or not self._asciiByteIs(n, ","):
        self.fail("expected , or }")
      self.pos += 1
      self._skipWsBound()

  def _loadDictStrFloatAsciiLoopRef(self, out: dict[str, float] @ref) -> None:
    while True:
      self._dictStrFloatPushAsciiRef(out)
      self.skipWs()
      if self.pos < self.srcLen() and self.srcChar(self.pos) in "}":
        self.pos += 1
        return
      self.expectChar(",")
      self.skipWs()

  def scanTestParseIntAtBound(self) -> int:
    """集成测：``_parseIntAtBound`` 快路径。"""
    return self._parseIntAtBound()

  def scanTestLoadListIntAsciiLoop(self, out: list[int] @ref) -> None:
    """集成测：``@native`` 叶子组合的 ASCII ``list[int]`` 循环。"""
    self._loadListIntAsciiLoop(out)

  def scanTestLoadListIntAsciiLoopRef(self, out: list[int] @ref) -> None:
    """集成测：纯 Python ``*_ref`` 组合的 ASCII ``list[int]`` 循环。"""
    self._loadListIntAsciiLoopRef(out)

  def scanTestLoadListStrAsciiLoop(self, out: list[str] @ref) -> None:
    self._loadListStrAsciiLoop(out)

  def scanTestLoadListStrAsciiLoopRef(self, out: list[str] @ref) -> None:
    self._loadListStrAsciiLoopRef(out)

  def scanTestLoadDictStrIntAsciiLoop(self, out: dict[str, int] @ref) -> None:
    self._loadDictStrIntAsciiLoop(out)

  def scanTestLoadDictStrIntAsciiLoopRef(self, out: dict[str, int] @ref) -> None:
    self._loadDictStrIntAsciiLoopRef(out)

  def scanTestLoadDictStrStrAsciiLoop(self, out: dict[str, str] @ref) -> None:
    self._loadDictStrStrAsciiLoop(out)

  def scanTestLoadDictStrStrAsciiLoopRef(self, out: dict[str, str] @ref) -> None:
    self._loadDictStrStrAsciiLoopRef(out)

  def _loadListIntAt(self) -> list[int]:
    self.expectChar("[")
    out: list[int] = []
    self.tryBindAscii()
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "]":
      self.pos += 1
      return out
    if self.asciiOk:
      self._loadListIntAsciiLoop(out)
      return out
    while True:
      out.append(self._parseIntAt())
      self._skipWs()
      if self.pos < len(self.s) and self.s[self.pos] in "]":
        self.pos += 1
        return out
      self.expectChar(",")
      self._skipWs()

  def _loadListLongAt(self) -> list[long]:
    self.expectChar("[")
    out: list[long] = []
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "]":
      self.pos += 1
      return out
    while True:
      out.append(self._parseLongAt())
      self._skipWs()
      if self.pos < len(self.s) and self.s[self.pos] in "]":
        self.pos += 1
        return out
      self.expectChar(",")
      self._skipWs()

  def loadListInt(self) -> list[int]:
    self._skipWs()
    return self.loadListIntValue()

  def loadListLong(self) -> list[long]:
    self._skipWs()
    return self.loadListLongValue()

  def _loadListStrAt(self) -> list[str]:
    self.expectChar("[")
    out: list[str] = []
    self.tryBindAscii()
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "]":
      self.pos += 1
      return out
    if self.asciiOk:
      self._loadListStrAsciiLoop(out)
      return out
    while True:
      out.append(self.loadStr())
      self._skipWs()
      if self.pos < len(self.s) and self.s[self.pos] in "]":
        self.pos += 1
        return out
      self.expectChar(",")
      self._skipWs()

  def loadListStr(self) -> list[str]:
    self._skipWs()
    return self.loadListStrValue()

  def _loadListFloatAt(self) -> list[float]:
    self.expectChar("[")
    out: list[float] = []
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "]":
      self.pos += 1
      return out
    while True:
      fbuf: list[float] = []
      self._parseFloatValue(fbuf)
      out.append(fbuf[0])
      self._skipWs()
      if self.pos < len(self.s) and self.s[self.pos] in "]":
        self.pos += 1
        return out
      self.expectChar(",")
      self._skipWs()

  def loadListFloat(self) -> list[float]:
    self._skipWs()
    return self.loadListFloatValue()

  def _loadDictStrIntAt(self) -> dict[str, int]:
    self.expectChar("{")
    out: dict[str, int] = {}
    self.tryBindAscii()
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1
      return out
    if self.asciiOk:
      self._loadDictStrIntAsciiLoop(out)
      return out
    while True:
      kbuf: list[str] = []
      self._parseStringValue(kbuf)
      k: str = kbuf[0]
      self._skipWs()
      self.expectChar(":")
      vbuf: list[int] = []
      self._parseIntValue(vbuf)
      out[k] = vbuf[0]
      self._skipWs()
      if self.pos < len(self.s) and self.s[self.pos] in "}":
        self.pos += 1
        return out
      self.expectChar(",")
      self._skipWs()

  def loadDictStrInt(self) -> dict[str, int]:
    self._skipWs()
    return self._loadDictStrIntAt()

  def _loadDictStrLongAt(self) -> dict[str, long]:
    self.expectChar("{")
    out: dict[str, long] = {}
    self.tryBindAscii()
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1
      return out
    if self.asciiOk:
      self._loadDictStrLongAsciiLoop(out)
      return out
    while True:
      kbuf: list[str] = []
      self._parseStringValue(kbuf)
      k: str = kbuf[0]
      self._skipWs()
      self.expectChar(":")
      vbuf: list[long] = []
      self._parseLongValue(vbuf)
      out[k] = vbuf[0]
      self._skipWs()
      if self.pos < len(self.s) and self.s[self.pos] in "}":
        self.pos += 1
        return out
      self.expectChar(",")
      self._skipWs()

  def loadDictStrLong(self) -> dict[str, long]:
    self._skipWs()
    return self._loadDictStrLongAt()

  def _loadDictStrStrAt(self) -> dict[str, str]:
    self.expectChar("{")
    out: dict[str, str] = {}
    self.tryBindAscii()
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1
      return out
    if self.asciiOk:
      self._loadDictStrStrAsciiLoop(out)
      return out
    while True:
      kbuf: list[str] = []
      self._parseStringValue(kbuf)
      k: str = kbuf[0]
      self._skipWs()
      self.expectChar(":")
      vbuf: list[str] = []
      self._parseStringValue(vbuf)
      out[k] = vbuf[0]
      self._skipWs()
      if self.pos < len(self.s) and self.s[self.pos] in "}":
        self.pos += 1
        return out
      self.expectChar(",")
      self._skipWs()

  def loadDictStrStr(self) -> dict[str, str]:
    self._skipWs()
    return self._loadDictStrStrAt()

  def _loadDictStrFloatAt(self) -> dict[str, float]:
    self.expectChar("{")
    out: dict[str, float] = {}
    self.tryBindAscii()
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1
      return out
    if self.asciiOk:
      self._loadDictStrFloatAsciiLoop(out)
      return out
    while True:
      kbuf: list[str] = []
      self._parseStringValue(kbuf)
      k: str = kbuf[0]
      self._skipWs()
      self.expectChar(":")
      vbuf: list[float] = []
      self._parseFloatValue(vbuf)
      out[k] = vbuf[0]
      self._skipWs()
      if self.pos < len(self.s) and self.s[self.pos] in "}":
        self.pos += 1
        return out
      self.expectChar(",")
      self._skipWs()

  def loadDictStrFloat(self) -> dict[str, float]:
    self._skipWs()
    return self._loadDictStrFloatAt()

  def atObjectEnd(self) -> bool:
    self._skipWs()
    if self.pos >= len(self.s):
      self.fail("unterminated object")
    if self.s[self.pos] in "}":
      self.pos += 1
      return True
    return False

  def beginArray(self) -> None:
    self._skipWs()
    self.expectChar("[")

  def atArrayEnd(self) -> bool:
    self._skipWs()
    if self.pos >= len(self.s):
      self.fail("unterminated array")
    if self.s[self.pos] in "]":
      self.pos += 1
      return True
    return False

  def loadTagField(self) -> str:
    key: str = self.loadKey()
    if key != "tag":
      self.fail("expected tag field")
    return self.loadStr()

  def beginPayloadObject(self) -> None:
    key: str = self.loadKey()
    if key != "payload":
      self.fail("expected payload field")
    self._skipWs()
    self.expectChar("{")

  def endPayloadObject(self) -> None:
    self._skipWs()
    if self.pos < len(self.s) and self.s[self.pos] in "}":
      self.pos += 1

  def byteAtRef(self, i: int) -> int:
    """第 ``i`` 字节（``int(srcChar)``）。"""
    return int(self.srcChar(i))


  def byteAt(self, i: int) -> int:
    """bound ASCII 下第 ``i`` 字节（``asciiBytes`` 或 ``srcChar``）。"""
    p: Pointer[char] = self.asciiBytes
    if self.asciiOk and p is not None:
      return int(p[i])
    return self.byteAtRef(i)


  def _loadStrSpanSlow(self) -> span[char]:
    n: int = self.srcLen()
    if self.pos >= n or self.srcChar(self.pos) not in '"':
      slow: str = self.loadStringSlow()
      return slow.view
    self.pos += 1
    start: int = self.pos
    while self.pos < n:
      c: char = self.srcChar(self.pos)
      if c in '"':
        end: int = self.pos
        self.pos += 1
        return self.s.view[start:end]
      if c in "\\":
        self.pos = start - 1
        slow2: str = self.loadStringSlow()
        return slow2.view
      self.pos += 1
    self.fail("unterminated string")
    return self.s.view[:0]


  def parseIntAtAsciiRef(self) -> int:
    """游标处 JSON 整数（``JsonDecoder.parseIntAt`` 语义参照）。"""
    return self.parseIntAt()


  def parseIntAtAscii(self) -> int:
    """bound ASCII 下 SwAR 整数解析（游标已在数值首字符）。"""
    if not self.asciiOk:
      self.fail("ascii int parse requires bound view")
      return 0
    n: int = self.asciiLen
    p: Pointer[char] = self.asciiBytes
    pos: int = self.pos
    neg: bool = False
    if pos < n and self.byteAt(pos) == ord("-"):
      neg = True
      pos += 1
    val: int64 = 0
    anyD: bool = False
    i: int = pos
    while i < n:
      if p is not None and i + 8 <= n:
        chunk: uint64 = loadU64Le(p, i)
        if Self._swarIs8digits(chunk):
          val *= 100000000
          val += int64(Self._swarParse8(chunk))
          i += 8
          anyD = True
          continue
      c: int = self.byteAt(i)
      if c < ord("0") or c > ord("9"):
        break
      val *= 10
      val += int64(c - ord("0"))
      i += 1
      anyD = True
    if not anyD:
      self.fail("expected int")
      return 0
    self.pos = i
    if neg:
      val = -val
    return int(val)


  def skipWsBoundRef(self) -> None:
    """bound 空白跳过（``skipWs`` 语义参照）。"""
    self.skipWs()


  def skipWsBound(self) -> None:
    """``asciiOk`` 时 8 字节空白快扫，否则 ``skipWs``。"""
    if not self.asciiOk:
      self.skipWs()
      return
    n: int = self.asciiLen
    i: int = self.pos
    p: Pointer[char] = self.asciiBytes
    while i < n:
      if p is not None and i + 8 <= n:
        chunk: uint64 = loadU64Le(p, i)
        if Self._chunkAllWs(chunk):
          i += 8
          continue
      if not Self._isWsByte(self.byteAt(i)):
        break
      i += 1
    self.pos = i


  def loadStrSpanAsciiRef(self) -> span[char]:
    """无转义 JSON 字符串 span（逐字符扫描语义参照）。"""
    return self._loadStrSpanSlow()


  def loadStrSpanAscii(self) -> span[char]:
    """bound ASCII 下无转义引号串快扫；有转义则 ``loadStringSlow``。"""
    if not self.asciiOk:
      self.skipSpaces()
      return self._loadStrSpanSlow()
    n: int = self.asciiLen
    p: Pointer[char] = self.asciiBytes
    if self.pos >= n or self.byteAt(self.pos) != ord('"'):
      slow: str = self.loadStringSlow()
      return slow.view
    self.pos += 1
    start: int = self.pos
    i: int = start
    while i < n:
      if p is not None and i + 8 <= n:
        chunk: uint64 = loadU64Le(p, i)
        special: bool = False
        for k in range(8):
          c: int = Self._chunkByte(chunk, k)
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
      c2: int = self.byteAt(i)
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
    slow2: str = self.loadStringSlow()
    return slow2.view


  def strAssignFromSegRef(self, seg: span[char]) -> str:
    """``seg`` → 新 ``str``（``copyFromSpan``）。"""
    dst: str = ""
    dst.copyFromSpan(seg)
    return dst


  def strAssignFromSeg(self, seg: span[char]) -> str:
    """``seg`` → 新 ``str``（Arena 时 ``copyArray`` + ``adoptSpan``）。"""
    segLen: int = len(seg)
    if segLen == 0 or not self.strArenaActive:
      return self.strAssignFromSegRef(seg)
    buf: Pointer[char] = self.strArena.acquire(segLen)
    if buf is None:
      return self.strAssignFromSegRef(seg)
    copyArray(buf, seg.at(), segLen)
    dst: str = ""
    dst.adoptSpan(span[char](buf, segLen, 1))
    self.strArena.release(buf)
    return dst


  def _skipStringAscii(self) -> None:
    """跳过 JSON 字符串字面量（``byteAtRef`` 组合）。"""
    n: int = self.srcLen()
    i: int = self.pos
    if i >= n or self.byteAtRef(i) != ord('"'):
      self.fail("expected string")
    i += 1
    while i < n:
      c: int = self.byteAtRef(i)
      if c == ord('"'):
        self.pos = i + 1
        return
      if c == ord("\\"):
        i += 1
        if i >= n:
          self.fail("unterminated string")
        if self.byteAtRef(i) == ord("u"):
          i += 5
        else:
          i += 1
        continue
      i += 1
    self.fail("unterminated string")


  def _skipNumberAscii(self) -> None:
    n: int = self.srcLen()
    i: int = self.pos
    if i < n and self.byteAtRef(i) == ord("-"):
      i += 1
    for i in range(i, n):
      c: int = self.byteAtRef(i)
      if ord("0") <= c <= ord("9") or c in {ord("."), ord("e"), ord("E"), ord("+"), ord("-")}:
        continue
      break
    self.pos = i


  def _skipContainerAscii(self, openCh: int, closeCh: int) -> None:
    n: int = self.srcLen()
    depth: int = 0
    while self.pos < n:
      c: char = self.srcChar(self.pos)
      match c:
        case _ if c == openCh:
          depth += 1
        case _ if c == closeCh:
          depth -= 1
          if depth == 0:
            self.pos += 1
            return
        case '"':
          self._skipStringAscii()
          continue
        case _:
          pass
      self.pos += 1
    if openCh == ord("["):
      self.fail("unterminated array")
    self.fail("unterminated object")


  def _skipValueAscii(self) -> None:
    self.skipWsBoundRef()
    n: int = self.srcLen()
    if self.pos >= n:
      self.fail("empty input")
    c: char = self.srcChar(self.pos)
    match c:
      case '"':
        self._skipStringAscii()
        return
      case 't':
        if self.pos + 4 <= n:
          if (
            self.srcChar(self.pos + 0) == 't'
            and self.srcChar(self.pos + 1) == 'r'
            and self.srcChar(self.pos + 2) == 'u'
            and self.srcChar(self.pos + 3) == 'e'
          ):
            self.pos += 4
            return
        self.fail("expected bool")
      case 'f':
        if self.pos + 5 <= n:
          if (
            self.srcChar(self.pos + 0) == 'f'
            and self.srcChar(self.pos + 1) == 'a'
            and self.srcChar(self.pos + 2) == 'l'
            and self.srcChar(self.pos + 3) == 's'
            and self.srcChar(self.pos + 4) == 'e'
          ):
            self.pos += 5
            return
        self.fail("expected bool")
      case 'n':
        if self.pos + 4 <= n:
          if (
            self.srcChar(self.pos + 0) == 'n'
            and self.srcChar(self.pos + 1) == 'u'
            and self.srcChar(self.pos + 2) == 'l'
            and self.srcChar(self.pos + 3) == 'l'
          ):
            self.pos += 4
            return
      case '-' | '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9':
        self._skipNumberAscii()
        return
      case '[':
        self._skipContainerAscii(ord("["), ord("]"))
        return
      case '{':
        self._skipContainerAscii(ord("{"), ord("}"))
        return
      case _:
        self.fail("bad value")


  def trySkipValueAscii(self) -> bool:
    """跳过单个 JSON 值（纯 Python 组合 ``byteAtRef`` / ``skipWsBoundRef``）。"""
    self.tryBindAscii()
    if not self.asciiOk:
      return False
    self._skipValueAscii()
    return True


  def trySkipFieldAscii(self) -> bool:
    """跳过 ``"key": value`` 字段（纯 Python 组合）。"""
    self.tryBindAscii()
    if not self.asciiOk:
      return False
    mark: int = self.pos
    self.skipWsBoundRef()
    n: int = self.srcLen()
    if self.pos < n and self.byteAtRef(self.pos) == ord(","):
      self.pos += 1
      self.skipWsBoundRef()
    if self.pos >= n or self.byteAtRef(self.pos) != ord('"'):
      self.pos = mark
      return False
    self._skipStringAscii()
    self.skipWsBoundRef()
    if self.pos >= n or self.byteAtRef(self.pos) != ord(":"):
      self.pos = mark
      return False
    self.pos += 1
    self._skipValueAscii()
    return True

class Json:
  """JSON 模块级 API（对齐 CPython ``json`` 子集）。"""

  @staticmethod
  @overload
  def _finishDump(enc: JsonEncoder, fp: StringIO) -> None:
    fp.clearBuffer()
    enc.flushTo(fp)

  @staticmethod
  @overload
  def _finishDump(enc: JsonEncoder, fp: TextIOWrapper) -> None:
    enc.flushTo(fp)

  @staticmethod
  @overload
  def _writeFast(s: str, fp: StringIO) -> None:
    fp.clearBuffer()
    fp.write(s)

  @staticmethod
  @overload
  def _writeFast(s: str, fp: TextIOWrapper) -> None:
    fp.write(s)

  @staticmethod
  @immutable
  def loadsUsesStrArena[Root]() -> bool:
    """``loads`` 是否需 ``strArena``（标量/纯数值容器为 ``False``）。"""
    if Root in { int, long, float, bool, list[int], list[long], list[float] }:
      return False
    else:
      return True

  @staticmethod
  @overload
  def dumps(obj: bool, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpBool(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: int, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpInt(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: long, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpLong(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: float, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpFloat(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: str, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpStr(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: list[int], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fastEncode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListInt(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: list[long], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fastEncode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListLong(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: list[str], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fastEncode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListStr(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: list[float], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fastEncode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListFloat(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: dict[str, int], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fastEncode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrInt(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: dict[str, long], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fastEncode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrLong(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: dict[str, str], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fastEncode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrStr(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps(obj: dict[str, float], indent: int = 0) -> str:
    if indent == 0:
      return JsonEncoder.fastEncode(obj)
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrFloat(obj)
    return enc.take()



  @staticmethod
  @overload
  def dumps[Root](obj: Root, indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    obj.serialize(enc)
    return enc.take()



  @staticmethod
  @overload
  def dumps[Root](obj: list[Root], indent: int = 0) -> str:
    enc: JsonEncoder = new()
    enc.indent = indent
    n: int = len(obj)
    if indent == 0 and n > 0:
      enc.growArray(n * 48 + 16)
    enc.beginArray()
    for i in range(n):
      obj[i].serialize(enc)
    enc.endArray()
    return enc.take()



  @staticmethod
  @overload
  def dump(obj: bool, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpBool(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: int, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpInt(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: long, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpLong(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: float, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpFloat(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: str, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpStr(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[int], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListInt(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[long], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListLong(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[str], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListStr(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[float], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListFloat(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, int], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrInt(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, long], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrLong(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, str], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrStr(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, float], fp: StringIO, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrFloat(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump[Root](obj: Root, fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    obj.serialize(enc)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump[Root](obj: list[Root], fp: StringIO, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    n: int = len(obj)
    if indent == 0 and n > 0:
      enc.growArray(n * 48 + 16)
    enc.beginArray()
    for i in range(n):
      obj[i].serialize(enc)
    enc.endArray()
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: bool, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpBool(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: int, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpInt(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: long, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpLong(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: float, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpFloat(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: str, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpStr(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[int], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListInt(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[long], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListLong(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[str], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListStr(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: list[float], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpListFloat(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, int], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrInt(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, long], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrLong(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, str], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrStr(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump(obj: dict[str, float], fp: TextIOWrapper, indent: int = 0) -> None:
    if indent == 0:
      Self._writeFast(JsonEncoder.fastEncode(obj), fp)
      return
    enc: JsonEncoder = new()
    enc.indent = indent
    enc.dumpDictStrFloat(obj)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump[Root](obj: Root, fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    obj.serialize(enc)
    Self._finishDump(enc, fp)



  @staticmethod
  @overload
  def dump[Root](obj: list[Root], fp: TextIOWrapper, indent: int = 0) -> None:
    enc: JsonEncoder = new()
    enc.indent = indent
    n: int = len(obj)
    if indent == 0 and n > 0:
      enc.growArray(n * 48 + 16)
    enc.beginArray()
    for i in range(n):
      obj[i].serialize(enc)
    enc.endArray()
    Self._finishDump(enc, fp)



  @staticmethod
  def loads[Root](s: str) -> Root:
    """``json.loads``；``T`` 为返回值静态类型（``Json.loads[User](s)`` 或赋值推断）。"""
    dec: JsonDecoder = new.fromText(s)
    dec.tryBindAscii()
    if Self.loadsUsesStrArena[Root]():
      dec.enableStrArena()
    if Root is int:
      out = dec.loadInt()
    elif Root is long:
      out = dec.loadLong()
    elif Root is float:
      out = dec.loadFloat()
    elif Root is str:
      out = dec.loadStr()
    elif Root is bool:
      out = dec.loadBool()
    elif Root is list[int]:
      out = dec.loadListInt()
    elif Root is list[long]:
      out = dec.loadListLong()
    elif Root is list[str]:
      out = dec.loadListStr()
    elif Root is list[float]:
      out = dec.loadListFloat()
    elif Root is list[...]:
      out = dec.loadContainer[Root]()
    elif Root is dict[str, int]:
      out = dec.loadDictStrInt()
    elif Root is dict[str, long]:
      out = dec.loadDictStrLong()
    elif Root is dict[str, str]:
      out = dec.loadDictStrStr()
    elif Root is dict[str, float]:
      out = dec.loadDictStrFloat()
    elif Root is dict[str, ...]:
      out = dec.loadContainer[Root]()
    else:
      out = dec.loadGeneric[Root]()
    if dec.strArenaActive:
      dec.strArena.reset()
      dec.strArenaActive = False
    dec.releaseAscii()
    return out

  @staticmethod
  @overload
  def load[Root](fp: TextIOWrapper) -> Root:
    """``json.load``：``fp.read()`` 后 ``Json.loads[T]``。"""
    return Self.loads[Root](fp.read())

  @staticmethod
  @overload
  def load[Root](fp: StringIO) -> Root:
    return Self.loads[Root](fp.read())


@union
class JsonDocStepUnion:
  @variant
  class Field:
    key: str

  @variant
  class Index:
    index: int


@copyable
@dataclass
class JsonDocument[Root]:
  """JSON 持久化文档；打开文件用 ``new.open(path, mode)``（``x: JsonDocument[T] = new.open(...)``；勿 ``JsonDocument[T].open``，S06b）。"""

  path: str = ""
  mode: str = ""
  text: str = ""
  orig: str = ""
  dec: JsonDecoder = new()
  writable: bool = False
  dirty: bool = False
  textGen: int = 0
  arrCacheBracket: int = -1
  arrCacheOffsets: list[int] @optional = []

  def _arrayIndex(self, idx: int):
    self.dec.skipSpaces()
    self.dec.expectChar("[")
    self.dec.skipSpaces()
    openPos: int = self.dec.pos - 1
    n: int = len(self.dec.s)
    if self.dec.pos < n and self.dec.s[self.dec.pos] in "]":
      self.dec.fail("index out of range")
    if idx < 0:
      self.dec.fail("index out of range")
    if not self._arrCacheValid(openPos):
      self._arrCacheReset(openPos)
    offs: list[int] = self.arrCacheOffsets
    if len(offs) > idx:
      self.dec.pos = offs[idx]
      return
    if offs:
      self.dec.pos = offs[-1]
      self.dec.skipValue()
      self.dec.skipSpaces()
      if self.dec.pos < n and self.dec.s[self.dec.pos] in "]":
        self.dec.fail("index out of range")
      self.dec.expectChar(",")
      self.dec.skipSpaces()
    while len(offs) <= idx:
      if self.dec.pos < n and self.dec.s[self.dec.pos] in "]":
        self.dec.fail("index out of range")
      offs.append(self.dec.pos)
      if len(offs) - 1 == idx:
        break
      self.dec.skipValue()
      self.dec.skipSpaces()
      if self.dec.pos < n and self.dec.s[self.dec.pos] in "]":
        self.dec.fail("index out of range")
      self.dec.expectChar(",")
      self.dec.skipSpaces()
    self.dec.pos = offs[idx]

  def _objectKey(self, key: str):
    self.dec.skipSpaces()
    n: int = len(self.dec.s)
    if self.dec.pos < n and self.dec.s[self.dec.pos] in "{":
      self.dec.pos += 1
      self.dec.skipSpaces()
    if self.dec.pos < n and self.dec.s[self.dec.pos] in "}":
      self.dec.fail("missing key")
    while True:
      if self.dec.atObjectEnd():
        self.dec.fail("missing key")
      if self.dec.tryMatchKey(key):
        return
      self.dec.skipField()

  def _containerCloseIndex(self, openPos: int) -> int:
    openC: char = self.dec.s[openPos]
    if openC not in "[{":
      self.dec.fail("expected container")
    depth: int = 0
    n: int = len(self.dec.s)
    i: int = openPos
    while i < n:
      c: char = self.dec.s[i]
      if openC in "{":
        match c:
          case '{':
            depth += 1
          case '}':
            depth -= 1
            if depth == 0:
              return i
          case _:
            pass
      elif openC in "[":
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
    return openPos

  @overload
  def _encodeForPatch(self, value: str) -> str:
    return Json.dumps(value)

  @overload
  def _encodeForPatch(self, value) -> str:
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
    doc.syncDec()
    return doc

  def __enter__(self) -> Self:
    return self

  def __exit__(self):
    self.commit()

  def __getattr__(self, name: str) -> JsonDocCursor[Root]:
    cur: JsonDocCursor[Root] = new()
    cur.doc = self
    cur.steps.append(JsonDocStepUnion.Field(name))
    return cur

  def __getitem__(self, i: int) -> JsonDocCursor[Root]:
    cur: JsonDocCursor[Root] = new()
    cur.doc = self
    cur.steps.append(JsonDocStepUnion.Index(i))
    return cur

  def __setattr__(self, name: str, value):
    steps: list[JsonDocStepUnion] = [JsonDocStepUnion.Field(name)]
    self.replaceAt(steps, value)

  def __setitem__(self, i: int, value):
    steps: list[JsonDocStepUnion] = [JsonDocStepUnion.Index(i)]
    self.replaceAt(steps, value)

  def __delitem__(self, i: int):
    steps: list[JsonDocStepUnion] = []
    self.delItemAt(steps, i)

  def load[Root](self) -> Root:
    """全量读入（等价 ``Json.loads[T](全文)``）。"""
    return Json.loads[Root](self.text)

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
    Path(tmp).replace(self.path)
    self.orig = self.text
    self.dirty = False

  def discard(self):
    """放弃未 ``commit`` 的内存变更。"""
    self.text = self.orig
    self.dirty = False
    self.syncDec()

  def readStrAt(self, steps: list[JsonDocStepUnion]) -> str:
    self._applySteps(steps)
    seg: span[char] = self.dec.loadStrSpan()
    return str.fromSpan(seg)

  def readIntAt(self, steps: list[JsonDocStepUnion]) -> int:
    self._applySteps(steps)
    return self.dec.loadInt()

  def readBoolAt(self, steps: list[JsonDocStepUnion]) -> bool:
    self._applySteps(steps)
    return self.dec.loadBool()

  def replaceAt(self, steps: list[JsonDocStepUnion], value):
    self._applySteps(steps)
    enc: str = self._encodeForPatch(value)
    self._replaceAtDecoder(enc)

  def appendAt(self, steps: list[JsonDocStepUnion], item):
    self._applySteps(steps)
    enc: str = self._encodeForPatch(item)
    self._appendAtArray(enc)

  def delItemAt(self, steps: list[JsonDocStepUnion], i: int):
    self._applySteps(steps)
    self._arrayIndex(i)
    self._deleteAtDecoder()

  def _arrCacheValid(self, openPos: int) -> bool:
    return self.arrCacheBracket == openPos

  def _arrCacheReset(self, openPos: int):
    self.arrCacheBracket = openPos
    self.arrCacheOffsets = []

  def _resetDecForNav(self):
    """每次懒导航前完整同步 ``dec``（含 ASCII 绑定），避免多次 ``read_*`` 游标残留。"""
    self.syncDec()

  def _requireWritable(self):
    if not self.writable:
      raise OSError()

  def _markDirty(self, next: str):
    self.text = next
    self.dirty = True
    self.textGen += 1
    self.syncDec()

  def syncDec(self):
    self.dec.releaseAscii()
    self.dec.s = self.text
    self.dec.pos = 0
    self.dec.asciiBindDone = False
    self.dec.asciiOk = False
    self.dec.asciiLen = 0
    self.dec.asciiBytes = None
    self.dec.asciiBytesOwned = False
    self._arrCacheReset(-1)
    self.dec.tryBindAscii()

  def _replaceAtDecoder(self, encoded: str):
    self._requireWritable()
    start: int = self.dec.pos
    self.dec.skipValue()
    end: int = self.dec.pos
    nxt: str = self.text.replaceSlice(encoded, start, end)
    self._markDirty(nxt)

  def _deleteAtDecoder(self):
    self._requireWritable()
    if self.dec.s != self.text:
      self.syncDec()
    start: int = self.dec.pos
    self.dec.skipSpaces()
    n: int = len(self.dec.s)
    if self.dec.pos >= n:
      self.dec.fail("empty input")
    c: char = self.dec.s[self.dec.pos]
    end: int = self.dec.pos
    if c in "[{":
      closeI: int = self._containerCloseIndex(self.dec.pos)
      end = closeI + 1
      self.dec.pos = end
    else:
      self.dec.skipValue()
      end = self.dec.pos
    self.dec.skipSpaces()
    n = len(self.dec.s)
    if self.dec.pos < n and self.dec.s[self.dec.pos] in ",":
      end += 1
    elif start > 0:
      sn: int = len(self.text)
      scanHi: int = start - 1
      if scanHi >= sn:
        scanHi = sn - 1
      for scan in range(scanHi, 0, -1):
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
    nxt: str = self.text.replaceSlice("", start, end)
    self._markDirty(nxt)

  def _appendAtArray(self, encoded: str):
    self._requireWritable()
    self.dec.skipSpaces()
    self.dec.expectChar("[")
    openPos: int = self.dec.pos - 1
    self.dec.skipSpaces()
    close: int = self._containerCloseIndex(openPos)
    nxt: str = ""
    if self.dec.pos < close and self.dec.s[self.dec.pos] in "]":
      nxt = self.text.replaceSlice(encoded, close, close)
    else:
      mid: str = "," + encoded
      nxt = self.text.replaceSlice(mid, close, close)
    self._markDirty(nxt)

  def _applySteps(self, steps: list[JsonDocStepUnion]):
    self._resetDecForNav()
    self.dec.beginRootObject()
    for st in steps:
      match st:  # py2cpp: strict-off
        case new.Field(key):
          self._objectKey(key)
        case new.Index(idx):
          self._arrayIndex(idx)


@copyable
@dataclass
class JsonDocCursor[Root]:
  """``JsonDocument`` 懒路径节点（``doc.teams[0].name``）。"""

  doc: Pointer[JsonDocument[Root]] = None
  steps: list[JsonDocStepUnion] @optional = []

  def __getattr__(self, name: str) -> Self:
    out: Self = self
    out.steps.append(JsonDocStepUnion.Field(name))
    return out

  def __getitem__(self, i: int) -> Self:
    out: Self = self
    out.steps.append(JsonDocStepUnion.Index(i))
    return out

  def __setattr__(self, name: str, value):
    self.steps.append(JsonDocStepUnion.Field(name))
    self.doc.replaceAt(self.steps, value)

  def __setitem__(self, i: int, value):
    self.steps.append(JsonDocStepUnion.Index(i))
    self.doc.replaceAt(self.steps, value)

  def __delitem__(self, i: int):
    self.doc.delItemAt(self.steps, i)

  def readStr(self) -> str:
    return self.doc.readStrAt(self.steps)

  def readInt(self) -> int:
    return self.doc.readIntAt(self.steps)

  def readBool(self) -> bool:
    return self.doc.readBoolAt(self.steps)

  def append(self, item):
    self.doc.appendAt(self.steps, item)
