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
def _json_quote(value: str) -> str:
  return JsonEncoder.encode_str(value)


@immutable
def _is_digit_text(value: str) -> bool:
  if not value:
    return False
  start: int = 0
  if value.startswith("-") or value.startswith("+"):
    start = 1
  if start >= len(value):
    return False
  for i in range(start, len(value)):
    c: char = value[i]
    if c < ord("0") or c > ord("9"):
      return False
  return True


@immutable
def _is_float_text(value: str) -> bool:
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
def _strip_comment(value: str) -> str:
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
def _decode_quoted(value: str) -> str:
  if len(value) < 2:
    return value
  if value[0] == ord("'") and value[-1] == ord("'"):
    return value[1:-1].replace("''", "'")
  if value[0] != ord('"') or value[-1] != ord('"'):
    return value
  body: str = value[1:-1]
  return body.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')


@immutable
def _scalar_json(value: str) -> str:
  text: str = value.strip()
  if text.startswith("!!str "):
    return _json_quote(_decode_quoted(text[6:].strip()))
  if text.startswith("!!int ") or text.startswith("!!float ") or text.startswith("!!bool "):
    text = text[6:].strip()
  if text.startswith("!"):
    if text.startswith("!!"):
      raise YamlConstructorError()
    if text.find(" ") > 0:
      text = text[text.find(" ") + 1:].strip()
    else:
      raise YamlConstructorError()
  if not text:
    return "null"
  if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
    return _json_quote(_decode_quoted(text))
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
  if _is_digit_text(text):
    return text
  if _is_float_text(text):
    return text
  return _json_quote(text)


@immutable
def _split_flow_parts(body: str) -> list[str]:
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
  lines: list[str] = []
  pos: int = 0
  anchor_names: list[str] = []
  anchor_values: list[str] = []

  def __init__(self, source: str):
    self.lines = []
    self.anchor_names = []
    self.anchor_values = []
    for raw in source.splitlines():
      line: str = raw.replace("\t", "  ")
      if line.strip() in {"", "---", "..."} or line.strip().startswith("%"):
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
    return _strip_comment(line.strip())

  def _error(self, message: str) -> None:
    raise YamlParserError()

  def _next_nonempty(self, start: int) -> int:
    i: int = start
    while i < len(self.lines) and not self._content(self.lines[i]):
      i += 1
    return i

  def parse(self) -> str:
    if not self.lines:
      return "null"
    return self._parse_block(self._indent(self.lines[0]))

  def _parse_block(self, indent: int) -> str:
    i: int = self._next_nonempty(self.pos)
    if i >= len(self.lines):
      return "null"
    self.pos = i
    content: str = self._content(self.lines[i])
    if content.startswith("-"):
      if len(content) == 1:
        return self._parse_sequence(indent)
      if content[1] == " ":
        return self._parse_sequence(indent)
    if self._mapping_split(content) < 0:
      self.pos += 1
      return self._flow_or_scalar(content)
    return self._parse_mapping(indent)

  def _parse_sequence(self, indent: int) -> str:
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
      if not content.startswith("-"):
        break
      if len(content) > 1 and content[1] != " ":
        break
      rest: str = content[1:].strip()
      self.pos += 1
      if not rest:
        self.pos = self._next_nonempty(self.pos)
        if self.pos < len(self.lines) and self._indent(self.lines[self.pos]) > indent:
          parts.append(self._parse_block(self._indent(self.lines[self.pos])))
        else:
          parts.append("null")
      elif self._mapping_split(rest) >= 0:
        parts.append(self._parse_inline_mapping(rest, indent + 2))
      elif rest.startswith("|") or rest.startswith(">"):
        parts.append(self._parse_multiline(indent, rest.startswith(">"), -1 if rest.find("-") >= 0 else 1 if rest.find("+") >= 0 else 0))
      else:
        parts.append(self._flow_or_scalar(rest))
    return "[" + ",".join(parts) + "]"

  def _parse_mapping(self, indent: int) -> str:
    parts: list[str] = []
    while self.pos < len(self.lines):
      line: str = self.lines[self.pos]
      if not self._content(line):
        self.pos += 1
        continue
      current: int = self._indent(line)
      content: str = self._content(line)
      if current != indent or content.startswith("-"):
        break
      split: int = self._mapping_split(content)
      if split < 0:
        self._error("expected mapping key and ':'")
      key: str = content[:split].strip()
      if key.startswith("?"):
        self._error("complex mapping keys are unsupported")
      rest: str = content[split + 1:].strip()
      self.pos += 1
      value: str
      if rest.startswith("|") or rest.startswith(">"):
        value = self._parse_multiline(indent, rest.startswith(">"), -1 if rest.find("-") >= 0 else 1 if rest.find("+") >= 0 else 0)
      elif rest:
        value = self._flow_or_scalar(rest)
      else:
        self.pos = self._next_nonempty(self.pos)
        if self.pos < len(self.lines) and self._indent(self.lines[self.pos]) > indent:
          value = self._parse_block(self._indent(self.lines[self.pos]))
        else:
          value = "null"
      if key == "<<":
        merge_text: str = rest
        if merge_text.startswith("*"):
          parts.extend(self._merge_anchor(merge_text[1:].strip()))
        elif merge_text.startswith("[") and merge_text.endswith("]"):
          for alias in _split_flow_parts(merge_text[1:-1]):
            if not alias.startswith("*"):
              self._error("merge sequence requires aliases")
            parts.extend(self._merge_anchor(alias[1:].strip()))
        else:
          self._error("merge requires an alias")
      else:
        parts.append(_json_quote(_decode_quoted(key)) + ":" + value)
    return "{" + ",".join(parts) + "}"

  @immutable
  def _mapping_split(self, value: str) -> int:
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

  def _parse_inline_mapping(self, first: str, child_indent: int) -> str:
    split: int = self._mapping_split(first)
    key: str = first[:split].strip()
    rest: str = first[split + 1:].strip()
    parts: list[str] = []
    if rest:
      parts.append(_json_quote(_decode_quoted(key)) + ":" + self._flow_or_scalar(rest))
    else:
      parts.append(_json_quote(_decode_quoted(key)) + ":null")
    while self.pos < len(self.lines):
      line: str = self.lines[self.pos]
      if not self._content(line):
        self.pos += 1
        continue
      if self._indent(line) != child_indent:
        break
      content: str = self._content(line)
      split = self._mapping_split(content)
      if split < 0:
        break
      key = content[:split].strip()
      rest = content[split + 1:].strip()
      self.pos += 1
      value: str
      if rest:
        value = self._flow_or_scalar(rest)
      else:
        self.pos = self._next_nonempty(self.pos)
        value = self._parse_block(self._indent(self.lines[self.pos])) if self.pos < len(self.lines) and self._indent(self.lines[self.pos]) > child_indent else "null"
      if key == "<<":
        merge_text: str = rest
        if merge_text.startswith("*"):
          parts.extend(self._merge_anchor(merge_text[1:].strip()))
        elif merge_text.startswith("[") and merge_text.endswith("]"):
          for alias in _split_flow_parts(merge_text[1:-1]):
            if not alias.startswith("*"):
              self._error("merge sequence requires aliases")
            parts.extend(self._merge_anchor(alias[1:].strip()))
        else:
          self._error("merge requires an alias")
      else:
        parts.append(_json_quote(_decode_quoted(key)) + ":" + value)
    return "{" + ",".join(parts) + "}"

  def _parse_multiline(self, parent_indent: int, folded: bool, chomp: int = 0) -> str:
    values: list[str] = []
    while self.pos < len(self.lines):
      line: str = self.lines[self.pos]
      if line.strip() and self._indent(line) <= parent_indent:
        break
      self.pos += 1
      if self._indent(line) > parent_indent:
        values.append(line[parent_indent + 2:])
      else:
        values.append("")
    separator: str = " " if folded else "\n"
    text: str = separator.join(values)
    if chomp < 0:
      return _json_quote(text.rstrip("\n"))
    if chomp > 0:
      return _json_quote(text.rstrip("\n") + "\n\n")
    return _json_quote(text.rstrip("\n") + "\n")

  def _anchor_index(self, name: str) -> int:
    for index in range(len(self.anchor_names)):
      if self.anchor_names[index] == name:
        return index
    return -1

  def _set_anchor(self, name: str, value: str) -> None:
    index: int = self._anchor_index(name)
    if index < 0:
      self.anchor_names.append(name)
      self.anchor_values.append(value)
    else:
      self.anchor_values[index] = value

  def _merge_anchor(self, name: str) -> list[str]:
    index: int = self._anchor_index(name)
    if index < 0:
      self._error("unknown merge alias")
    encoded: str = self.anchor_values[index]
    if not encoded.startswith("{") or not encoded.endswith("}"):
      self._error("merge alias must be a mapping")
    body: str = encoded[1:-1].strip()
    if not body:
      return []
    return _split_flow_parts(body)
  def _flow_or_scalar(self, value: str) -> str:
    text: str = value.strip()
    if text.startswith("&"):
      sep: int = text.find(" ")
      if sep < 0:
        self._error("anchor needs a value")
      name: str = text[1:sep]
      encoded: str = self._flow_or_scalar(text[sep + 1:].strip())
      self._set_anchor(name, encoded)
      return encoded
    if text.startswith("*"):
      index = self._anchor_index(text[1:].strip())
      if index < 0:
        self._error("unknown alias")
      return self.anchor_values[index]
    if text.startswith("[") and text.endswith("]"):
      body: str = text[1:-1].strip()
      if not body:
        return "[]"
      items: list[str] = []
      flow_parts: list[str] = _split_flow_parts(body)
      for part in flow_parts:
        items.append(self._flow_or_scalar(part))
      return "[" + ",".join(items) + "]"
    if text.startswith("{") and text.endswith("}"):
      body: str = text[1:-1].strip()
      if not body:
        return "{}"
      items: list[str] = []
      flow_parts: list[str] = _split_flow_parts(body)
      for part in flow_parts:
        split: int = self._mapping_split(part.strip())
        if split < 0:
          self._error("invalid flow mapping")
        key: str = part[:split].strip()
        val: str = part[split + 1:].strip()
        items.append(_json_quote(_decode_quoted(key)) + ":" + self._flow_or_scalar(val))
      return "{" + ",".join(items) + "}"
    return _scalar_json(text)


@copyable
class YamlEncoder:
  indent: int = 2
  flow_style: bool = True

  def encode[T](self, value: T) -> str:
    return Json.dumps(value, 0)


@immutable
def _yaml_documents(source: str) -> list[str]:
  docs: list[str] = []
  lines: list[str] = []
  for line in source.splitlines():
    marker: str = line.strip()
    if marker in {"---", "..."}:
      if lines:
        docs.append("\n".join(lines))
        lines = []
    elif not marker.startswith("%"):
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
  def loads_all[T](s: str) -> list[T]:
    result: list[T] = []
    for doc in _yaml_documents(s):
      result.append(Self.loads[T](doc))
    return result

  @staticmethod
  def dumps[T](obj: T, indent: int = 2) -> str:
    return Json.dumps(obj, 0)

  @staticmethod
  def load[T](fp: TextIOWrapper) -> T:
    return Self.loads[T](fp.read())

  @staticmethod
  def load_all[T](fp: TextIOWrapper) -> list[T]:
    return Self.loads_all[T](fp.read())

  @staticmethod
  def load_all_string[T](fp: StringIO) -> list[T]:
    return Self.loads_all[T](fp.read())

  @staticmethod
  def load_string[T](fp: StringIO) -> T:
    return Self.loads[T](fp.read())

  @staticmethod
  def dump[T](obj: T, fp: TextIOWrapper, indent: int = 2) -> None:
    fp.write(Self.dumps[T](obj, indent))

  @staticmethod
  def dump_string[T](obj: T, fp: StringIO, indent: int = 2) -> None:
    fp.clear_buffer()
    fp.write(Self.dumps[T](obj, indent))

