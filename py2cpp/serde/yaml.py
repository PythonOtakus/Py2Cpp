"""YAML 1.2 Core Schema 常用子集。

Python 3.13 标准库没有 ``yaml`` 模块；本模块提供 Py2Cpp 自有的 YAML
配置序列化 API。解析器先把 YAML 规范化为 JSON，再复用 ``serde.json``
完成静态容器与 ``@serializable`` 类型映射。
"""
from ..builtins import *
from ..core.exceptions import Exception
from ..io import StringIO, TextIOWrapper
from ..serde.json import Json, JsonEncoder


class YamlError(Exception):
  pass


class YamlScannerError(YamlError):
  pass


class YamlParserError(YamlError):
  pass


class YamlConstructorError(YamlError):
  pass


class YamlRepresenterError(YamlError):
  pass


@immutable
def _jsonQuote(value: str) -> str:
  return JsonEncoder.encodeStr(value)


@immutable
def _isDigitText(value: str) -> bool:
  if not value:
    return False
  start: int = 0
  if value.startsWith("-") or value.startsWith("+"):
    start = 1
  if start >= len(value):
    return False
  for i in range(start, len(value)):
    c: char = value[i]
    if c < ord("0") or c > ord("9"):
      return False
  return True


@immutable
def _isFloatText(value: str) -> bool:
  if not value:
    return False
  if value in {".inf", "+.inf", "-.inf", ".nan"}:
    return True
  dot: int = value.find(".")
  exp: int = value.find("e")
  if exp < 0:
    exp = value.find("E")
  return dot >= 0 or exp >= 0


@immutable
def _stripComment(value: str) -> str:
  quote: int = 0
  for i in range(len(value)):
    c: char = value[i]
    match c:
      case 39:
        if not quote:
          quote = c
        elif quote == c:
          quote = 0
      case 34:
        if not quote:
          quote = c
        elif quote == c:
          quote = 0
      case 35:
        if not quote and (i == 0 or value[i - 1] == ord(" ")):
          return value[:i].rstrip()
      case _:
        pass
  return value.rstrip()


@immutable
def _decodeQuoted(value: str) -> str:
  if len(value) < 2:
    return value
  if value[0] == ord("'") and value[-1] == ord("'"):
    return value[1:-1].replace("''", "'")
  if value[0] != ord('"') or value[-1] != ord('"'):
    return value
  body: str = value[1:-1]
  return body.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')


@immutable
def _scalarJson(value: str) -> str:
  text: str = value.strip()
  if text.startsWith("!!str "):
    return _jsonQuote(_decodeQuoted(text[6:].strip()))
  if text.startsWith("!!int ") or text.startsWith("!!float ") or text.startsWith("!!bool "):
    text = text[6:].strip()
  if text.startsWith("!"):
    if text.startsWith("!!"):
      raise YamlConstructorError()
    if text.find(" ") > 0:
      text = text[text.find(" ") + 1:].strip()
    else:
      raise YamlConstructorError()
  if not text:
    return "null"
  if (text.startsWith('"') and text.endsWith('"')) or (text.startsWith("'") and text.endsWith("'")):
    return _jsonQuote(_decodeQuoted(text))
  lower: str = text.lower()
  match lower:
    case "null":
      return "null"
    case "~":
      return "null"
    case "true":
      return "true"
    case "false":
      return "false"
    case ".inf":
      return "1e999"
    case "+.inf":
      return "1e999"
    case "-.inf":
      return "-1e999"
    case ".nan":
      return "0"
    case _:
      pass
  if _isDigitText(text):
    return text
  if _isFloatText(text):
    return text
  return _jsonQuote(text)


@immutable
def _splitFlowParts(body: str) -> list[str]:
  parts: list[str] = []
  start: int = 0
  depth: int = 0
  quote: int = 0
  for i in range(len(body)):
    c: char = body[i]
    match c:
      case 39:
        if not quote:
          quote = c
        elif quote == c:
          quote = 0
      case 34:
        if not quote:
          quote = c
        elif quote == c:
          quote = 0
      case 91:
        if not quote:
          depth += 1
      case 123:
        if not quote:
          depth += 1
      case 93:
        if not quote:
          depth -= 1
      case 125:
        if not quote:
          depth -= 1
      case 44:
        if not quote and depth == 0:
          parts.append(body[start:i].strip())
          start = i + 1
      case _:
        pass
  parts.append(body[start:].strip())
  return parts
class _YamlParser:
  lines: list[str]
  pos: int
  anchorNames: list[str]
  anchorValues: list[str]

  def __init__(self, source: str):
    self.lines = []
    self.anchorNames = []
    self.anchorValues = []
    for raw in source.splitLines():
      line: str = raw.replace("\t", "  ")
      if line.strip() in {"", "---", "..."} or line.strip().startsWith("%"):
        continue
      self.lines.append(line)
    self.pos = 0

  @immutable
  def _indent(self, line: str) -> int:
    n: int = 0
    while n < len(line) and line[n] == ord(" "):
      n += 1
    return n

  @immutable
  def _content(self, line: str) -> str:
    return _stripComment(line.strip())

  def _error(self, message: str) -> None:
    raise YamlParserError()

  def _nextNonempty(self, start: int) -> int:
    i: int = start
    while i < len(self.lines) and not self._content(self.lines[i]):
      i += 1
    return i

  def parse(self) -> str:
    if not self.lines:
      return "null"
    return self._parseBlock(self._indent(self.lines[0]))

  def _parseBlock(self, indent: int) -> str:
    i: int = self._nextNonempty(self.pos)
    if i >= len(self.lines):
      return "null"
    self.pos = i
    content: str = self._content(self.lines[i])
    if content.startsWith("-"):
      if len(content) == 1:
        return self._parseSequence(indent)
      if content[1] == " ":
        return self._parseSequence(indent)
    if self._mappingSplit(content) < 0:
      self.pos += 1
      return self._flowOrScalar(content)
    return self._parseMapping(indent)

  def _parseSequence(self, indent: int) -> str:
    parts: list[str] = []
    while self.pos < len(self.lines):
      line: str = self.lines[self.pos]
      if not self._content(line):
        self.pos += 1
        continue
      current: int = self._indent(line)
      content: str = self._content(line)
      if current != indent:
        break
      if not content.startsWith("-"):
        break
      if len(content) > 1 and content[1] != " ":
        break
      rest: str = content[1:].strip()
      self.pos += 1
      if not rest:
        self.pos = self._nextNonempty(self.pos)
        if self.pos < len(self.lines) and self._indent(self.lines[self.pos]) > indent:
          parts.append(self._parseBlock(self._indent(self.lines[self.pos])))
        else:
          parts.append("null")
      elif self._mappingSplit(rest) >= 0:
        parts.append(self._parseInlineMapping(rest, indent + 2))
      elif rest.startsWith("|") or rest.startsWith(">"):
        parts.append(self._parseMultiline(indent, rest.startsWith(">"), -1 if rest.find("-") >= 0 else 1 if rest.find("+") >= 0 else 0))
      else:
        parts.append(self._flowOrScalar(rest))
    return "[" + ",".join(parts) + "]"

  def _parseMapping(self, indent: int) -> str:
    parts: list[str] = []
    while self.pos < len(self.lines):
      line: str = self.lines[self.pos]
      if not self._content(line):
        self.pos += 1
        continue
      current: int = self._indent(line)
      content: str = self._content(line)
      if current != indent or content.startsWith("-"):
        break
      split: int = self._mappingSplit(content)
      if split < 0:
        self._error("expected mapping key and ':'")
      key: str = content[:split].strip()
      if key.startsWith("?"):
        self._error("complex mapping keys are unsupported")
      rest: str = content[split + 1:].strip()
      self.pos += 1
      value: str
      if rest.startsWith("|") or rest.startsWith(">"):
        value = self._parseMultiline(indent, rest.startsWith(">"), -1 if rest.find("-") >= 0 else 1 if rest.find("+") >= 0 else 0)
      elif rest:
        value = self._flowOrScalar(rest)
      else:
        self.pos = self._nextNonempty(self.pos)
        if self.pos < len(self.lines) and self._indent(self.lines[self.pos]) > indent:
          value = self._parseBlock(self._indent(self.lines[self.pos]))
        else:
          value = "null"
      if key == "<<":
        mergeText: str = rest
        if mergeText.startsWith("*"):
          parts.extend(self._mergeAnchor(mergeText[1:].strip()))
        elif mergeText.startsWith("[") and mergeText.endsWith("]"):
          for alias in _splitFlowParts(mergeText[1:-1]):
            if not alias.startsWith("*"):
              self._error("merge sequence requires aliases")
            parts.extend(self._mergeAnchor(alias[1:].strip()))
        else:
          self._error("merge requires an alias")
      else:
        parts.append(_jsonQuote(_decodeQuoted(key)) + ":" + value)
    return "{" + ",".join(parts) + "}"

  @immutable
  def _mappingSplit(self, value: str) -> int:
    quote: int = 0
    depth: int = 0
    for i in range(len(value)):
      c: char = value[i]
      match c:
        case 39:
          if not quote:
            quote = c
          elif quote == c:
            quote = 0
        case 34:
          if not quote:
            quote = c
          elif quote == c:
            quote = 0
        case 91:
          if not quote:
            depth += 1
        case 123:
          if not quote:
            depth += 1
        case 93:
          if not quote:
            depth -= 1
        case 125:
          if not quote:
            depth -= 1
        case 58:
          if not quote and depth == 0 and (i + 1 == len(value) or value[i + 1] == ord(" ")):
            return i
        case _:
          pass
    return -1

  def _parseInlineMapping(self, first: str, childIndent: int) -> str:
    split: int = self._mappingSplit(first)
    key: str = first[:split].strip()
    rest: str = first[split + 1:].strip()
    parts: list[str] = []
    if rest:
      parts.append(_jsonQuote(_decodeQuoted(key)) + ":" + self._flowOrScalar(rest))
    else:
      parts.append(_jsonQuote(_decodeQuoted(key)) + ":null")
    while self.pos < len(self.lines):
      line: str = self.lines[self.pos]
      if not self._content(line):
        self.pos += 1
        continue
      if self._indent(line) != childIndent:
        break
      content: str = self._content(line)
      split = self._mappingSplit(content)
      if split < 0:
        break
      key = content[:split].strip()
      rest = content[split + 1:].strip()
      self.pos += 1
      value: str
      if rest:
        value = self._flowOrScalar(rest)
      else:
        self.pos = self._nextNonempty(self.pos)
        value = self._parseBlock(self._indent(self.lines[self.pos])) if self.pos < len(self.lines) and self._indent(self.lines[self.pos]) > childIndent else "null"
      if key == "<<":
        mergeText: str = rest
        if mergeText.startsWith("*"):
          parts.extend(self._mergeAnchor(mergeText[1:].strip()))
        elif mergeText.startsWith("[") and mergeText.endsWith("]"):
          for alias in _splitFlowParts(mergeText[1:-1]):
            if not alias.startsWith("*"):
              self._error("merge sequence requires aliases")
            parts.extend(self._mergeAnchor(alias[1:].strip()))
        else:
          self._error("merge requires an alias")
      else:
        parts.append(_jsonQuote(_decodeQuoted(key)) + ":" + value)
    return "{" + ",".join(parts) + "}"

  def _parseMultiline(self, parentIndent: int, folded: bool, chomp: int = 0) -> str:
    values: list[str] = []
    while self.pos < len(self.lines):
      line: str = self.lines[self.pos]
      if line.strip() and self._indent(line) <= parentIndent:
        break
      self.pos += 1
      if self._indent(line) > parentIndent:
        values.append(line[parentIndent + 2:])
      else:
        values.append("")
    separator: str = " " if folded else "\n"
    text: str = separator.join(values)
    if chomp < 0:
      return _jsonQuote(text.rstrip("\n"))
    if chomp > 0:
      return _jsonQuote(text.rstrip("\n") + "\n\n")
    return _jsonQuote(text.rstrip("\n") + "\n")

  def _anchorIndex(self, name: str) -> int:
    for index in range(len(self.anchorNames)):
      if self.anchorNames[index] == name:
        return index
    return -1

  def _setAnchor(self, name: str, value: str) -> None:
    index: int = self._anchorIndex(name)
    if index < 0:
      self.anchorNames.append(name)
      self.anchorValues.append(value)
    else:
      self.anchorValues[index] = value

  def _mergeAnchor(self, name: str) -> list[str]:
    index: int = self._anchorIndex(name)
    if index < 0:
      self._error("unknown merge alias")
    encoded: str = self.anchorValues[index]
    if not encoded.startsWith("{") or not encoded.endsWith("}"):
      self._error("merge alias must be a mapping")
    body: str = encoded[1:-1].strip()
    if not body:
      return []
    return _splitFlowParts(body)
  def _flowOrScalar(self, value: str) -> str:
    text: str = value.strip()
    if text.startsWith("&"):
      sep: int = text.find(" ")
      if sep < 0:
        self._error("anchor needs a value")
      name: str = text[1:sep]
      encoded: str = self._flowOrScalar(text[sep + 1:].strip())
      self._setAnchor(name, encoded)
      return encoded
    if text.startsWith("*"):
      index = self._anchorIndex(text[1:].strip())
      if index < 0:
        self._error("unknown alias")
      return self.anchorValues[index]
    if text.startsWith("[") and text.endsWith("]"):
      body: str = text[1:-1].strip()
      if not body:
        return "[]"
      items: list[str] = []
      flowParts: list[str] = _splitFlowParts(body)
      for part in flowParts:
        items.append(self._flowOrScalar(part))
      return "[" + ",".join(items) + "]"
    if text.startsWith("{") and text.endsWith("}"):
      body: str = text[1:-1].strip()
      if not body:
        return "{}"
      items: list[str] = []
      flowParts: list[str] = _splitFlowParts(body)
      for part in flowParts:
        split: int = self._mappingSplit(part.strip())
        if split < 0:
          self._error("invalid flow mapping")
        key: str = part[:split].strip()
        val: str = part[split + 1:].strip()
        items.append(_jsonQuote(_decodeQuoted(key)) + ":" + self._flowOrScalar(val))
      return "{" + ",".join(items) + "}"
    return _scalarJson(text)


@copyable
class YamlEncoder:
  indent: int = 2
  flowStyle: bool = True

  def encode[T](self, value: T) -> str:
    return Json.dumps(value, 0)


@immutable
def _yamlDocuments(source: str) -> list[str]:
  docs: list[str] = []
  lines: list[str] = []
  for line in source.splitLines():
    marker: str = line.strip()
    if marker in {"---", "..."}:
      if lines:
        docs.append("\n".join(lines))
        lines = []
    elif not marker.startsWith("%"):
      lines.append(line)
  if lines:
    docs.append("\n".join(lines))
  return docs

class Yaml:
  @staticmethod
  def loads[T](s: str) -> T:
    parser: _YamlParser = new(s)
    normalized: str = parser.parse()
    return Json.loads[T](normalized)

  @staticmethod
  def loadsAll[T](s: str) -> list[T]:
    result: list[T] = []
    for doc in _yamlDocuments(s):
      result.append(Self.loads[T](doc))
    return result

  @staticmethod
  def dumps[T](obj: T, indent: int = 2) -> str:
    return Json.dumps(obj, 0)

  @staticmethod
  def load[T](fp: TextIOWrapper) -> T:
    return Self.loads[T](fp.read())

  @staticmethod
  def loadAll[T](fp: TextIOWrapper) -> list[T]:
    return Self.loadsAll[T](fp.read())

  @staticmethod
  def loadAllString[T](fp: StringIO) -> list[T]:
    return Self.loadsAll[T](fp.read())

  @staticmethod
  def loadString[T](fp: StringIO) -> T:
    return Self.loads[T](fp.read())

  @staticmethod
  def dump[T](obj: T, fp: TextIOWrapper, indent: int = 2) -> None:
    fp.write(Self.dumps[T](obj, indent))

  @staticmethod
  def dumpString[T](obj: T, fp: StringIO, indent: int = 2) -> None:
    fp.clearBuffer()
    fp.write(Self.dumps[T](obj, indent))

