"""PyML 配置模板展开器。"""
from ..builtins import *
from ..core.exceptions import Exception, ValueError
from ..io import StringIO, TextIOWrapper
from ..io.file.path import exists, join, realPath
from .json import JsonEncoder
from .yaml import Yaml


class PymlError(Exception):
  pass


@immutable
def _pymlStripComment(value: str) -> str:
  quote: char = 0
  for i in range(len(value)):
    c: char = value[i]
    if c in "'\"":
      if not quote:
        quote = c
      elif quote == c:
        quote = 0
    elif c == ord("#") and not quote and (i == 0 or value[i - 1] == ord(" ")):
      return value[:i].rstrip()
  return value.rstrip()


@copyable
@dataclass
class PymlContext:
  moduleName: str = ""
  moduleRoot: str = ""
  allowedRoot: str = ""


@union
class _PymlValueUnion:
  @variant
  class Integer:
    raw: str

  @variant
  class Float:
    raw: str

  @variant
  class String:
    raw: str

  @variant
  class Boolean:
    raw: str

  @variant
  class Null:
    pass

  @variant
  class Sequence:
    parts: list[str]

  @variant
  class Mapping:
    keys: list[str]
    values: list[str]

  @variant
  class Def:
    params: list[str]
    defaults: list[str]
    begin: int
    end: int
    indent: int
    closure: dict[str, _PymlValueUnion]

  @variant
  class Inline:
    params: list[str]
    defaults: list[str]
    begin: int
    end: int
    indent: int
    closure: dict[str, _PymlValueUnion]

  @variant
  class Block:
    sequence: bool
    lines: list[str]


@copyable
@dataclass
class _PymlLine:
  indent: int = 0
  text: str = ""
  number: int = 0


@immutable
def _pymlQuote(value: str) -> str:
  return JsonEncoder.encodeStr(value)


@immutable
def _pymlIndent(line: str) -> int:
  n: int = 0
  for i in range(len(line)):
    if line[i] != ord(" "):
      return n
    n += 1
  return n


@immutable
def _pymlSplit(text: str, sep: char = 44) -> list[str]:
  out: list[str] = []
  start: int = 0
  depth: int = 0
  quote: char = 0
  for i in range(len(text)):
    c: char = text[i]
    if c in "'\"":
      if not quote:
        quote = c
      elif quote == c:
        quote = 0
    elif not quote and c in "[{(":
      depth += 1
    elif not quote and c in "]})":
      depth -= 1
    elif not quote and not depth and c == sep:
      out.append(text[start:i].strip())
      start = i + 1
  out.append(text[start:].strip())
  return out


@immutable
def _pymlFindColon(text: str) -> int:
  quote: char = 0
  depth: int = 0
  for i in range(len(text)):
    c: char = text[i]
    match c:
      case q if q in "'\"":
        if not quote:
          quote = q
        elif quote == q:
          quote = 0
      case q if not quote and q in "[{(":
        depth += 1
      case q if not quote and q in "]})":
        depth -= 1
      case q if not quote and not depth and q == ord(":"):
        return i
      case _:
        pass
  return -1


@immutable
def _pymlFindOperator(text: str, op: str) -> int:
  """在不进入字符串或 flow 容器的前提下查找表达式运算符。"""
  quote: char = 0
  depth: int = 0
  i: int = 0
  while i <= len(text) - len(op):
    c: char = text[i]
    if c in "'\"":
      if not quote:
        quote = c
      elif quote == c:
        quote = 0
    elif not quote and c in "[{(":
      depth += 1
    elif not quote and c in "]})":
      depth -= 1
    elif not quote and not depth and text[i:i + len(op)] == op:
      if op == "-" and (i == 0 or text[i - 1] in "(,+-*/%"):
        i += 1
        continue
      return i
    i += 1
  return -1


@immutable
def _pymlOuterParentheses(text: str) -> bool:
  if len(text) < 2 or not text.startsWith("(") or not text.endsWith(")"):
    return False
  quote: char = 0
  depth: int = 0
  for i in range(len(text)):
    c: char = text[i]
    match c:
      case q if q in "'\"":
        if not quote:
          quote = q
        elif quote == q:
          quote = 0
      case q if not quote and q == ord("("):
        depth += 1
      case q if not quote and q == ord(")"):
        depth -= 1
        if not depth and i != len(text) - 1:
          return False
      case _:
        pass
  return not quote and not depth


class _PymlExpander:
  sourceName: str = "<string>"
  lines: list[_PymlLine] = []
  symbols: dict[str, _PymlValueUnion] = {}
  returned: bool = False
  resultValue: _PymlValueUnion
  runKind: int = 0
  callStack: list[str] = []
  context: PymlContext
  # Cache source text, never callable indexes tied to an importing line table.
  # Every importer rebases begin/end into its own line table.
  moduleCache: dict[str, str] = {}
  importStack: list[str] = []

  def __init__(self, source: str, context: PymlContext):
    self.lines = []
    self.symbols = {}
    self.returned = False
    self.resultValue = self._literal("null")
    self.runKind = 0
    self.callStack = []
    self.context = context
    self.moduleCache = {}
    self.importStack = []
    if context.moduleName:
      self.sourceName = context.moduleName
      self.importStack.append(context.moduleName)
    for raw in source.splitLines():
      clean: str = _pymlStripComment(raw.replace("\t", "  "))
      if not clean.strip():
        continue
      self.lines.append(_PymlLine(_pymlIndent(clean), clean.strip(), len(self.lines) + 1))

  def _fail(self, line: _PymlLine, message: str):
    raise PymlError()

  def _subtreeEnd(self, start: int, indent: int, end: int) -> int:
    i: int = start
    while i < end and self.lines[i].indent > indent:
      i += 1
    return i

  def _moduleName(self, line: _PymlLine, spec: str) -> str:
    """将受限的 Python 模块路径解析为规范逻辑模块名。"""
    raw: str = spec.strip()
    if not raw or "\\" in raw or "/" in raw or ":" in raw:
      self._fail(line, "invalid module path")
    dots: int = 0
    while dots < len(raw) and raw[dots] == ord("."):
      dots += 1
    tail: str = raw[dots:]
    if not tail or tail.startsWith(".") or tail.endsWith(".") or ".." in tail:
      self._fail(line, "invalid module path")
    parts: list[str] = tail.split(".")
    for part in parts:
      if not part or not part.isIdentifier():
        self._fail(line, "invalid module path")
    if not dots:
      return tail
    if not self.context.moduleName:
      self._fail(line, "relative import requires module context")
    base: list[str] = self.context.moduleName.split(".")
    base.pop()
    climb: int = dots - 1
    if climb > len(base):
      self._fail(line, "relative import escapes module root")
    for _ in range(climb):
      base.pop()
    for part in parts:
      base.append(part)
    return ".".join(base)

  def _loadModule(self, line: _PymlLine, spec: str) -> dict[str, _PymlValueUnion]:
    name: str = self._moduleName(line, spec)
    if name in self.importStack:
      self._fail(line, "module import cycle")
    if not self.context.moduleRoot:
      self._fail(line, "module import requires moduleRoot")
    path: str = self.context.moduleRoot
    for part in name.split("."):
      path = join(path, part)
    path += ".pyml"
    path = realPath(path)
    if self.context.allowedRoot:
      allowed: str = realPath(self.context.allowedRoot)
      if path != allowed and not path.startsWith(allowed + "\\") and not path.startsWith(allowed + "/"):
        self._fail(line, "module import escapes allowed root")
    if not exists(path):
      self._fail(line, "module not found")
    childContext: PymlContext = new(
      moduleName=name,
      moduleRoot=self.context.moduleRoot,
      allowedRoot=self.context.allowedRoot,
    )
    source: str = ""
    if name in self.moduleCache:
      source = self.moduleCache[name]
    else:
      fp: TextIOWrapper = new(path)
      source = fp.read()
      fp.close()
      self.moduleCache[name] = source
    self.importStack.append(name)
    child: Self = new(source, childContext)
    child.moduleCache = self.moduleCache
    child.importStack = self.importStack
    child.expand()
    self.importStack.pop()
    offset: int = len(self.lines)
    for childLine in child.lines:
      self.lines.append(childLine)
    exports: dict[str, _PymlValueUnion] = {}
    for exportName in child.symbols:
      exportValue: _PymlValueUnion = child.symbols[exportName]
      match exportValue:
        case new.Def(p, d, b, e, ind, captured):
          exports[exportName] = _PymlValueUnion.Def(p, d, b + offset, e + offset, ind, captured)
        case new.Inline(p, d, b, e, ind, captured):
          exports[exportName] = _PymlValueUnion.Inline(p, d, b + offset, e + offset, ind, captured)
        case _:
          exports[exportName] = exportValue
    return exports

  def _importSymbols(self, line: _PymlLine, text: str):
    marker: int = text.find(" import ")
    if marker < 7:
      self._fail(line, "invalid from import")
    module: dict[str, _PymlValueUnion] = self._loadModule(line, text[6:marker].strip())
    requested: str = text[marker + 8:].strip()
    if requested == "*":
      for name in module:
        if name in self.symbols:
          self._fail(line, "import collision")
        self.symbols[name] = module[name]
      return
    for item in _pymlSplit(requested):
      words: list[str] = item.split(" as ")
      if len(words) > 2:
        self._fail(line, "invalid import alias")
      source: str = words[0].strip()
      target: str = source
      if len(words) == 2:
        target = words[1].strip()
      if not source.startsWith("$") or not target.startsWith("$") or source not in module:
        self._fail(line, "invalid import symbol")
      if target in self.symbols:
        self._fail(line, "import collision")
      self.symbols[target] = module[source]

  def _containerKind(self, begin: int, end: int, indent: int) -> int:
    """1=mapping, 2=sequence, 0=尚无法由同级元素推断。"""
    for i in range(begin, end):
      line: _PymlLine = self.lines[i]
      if line.indent != indent:
        continue
      text: str = line.text
      if text.startsWith("$") or text.startsWith("@if ") or text.startsWith("@elif ") or text == "@else:" or text.startsWith("@for ") or text.startsWith("@expand "):
        continue
      if text.startsWith("- "):
        return 2
      if _pymlFindColon(text) >= 0:
        return 1
    return 0

  def _asBlock(self, line: _PymlLine, value: _PymlValueUnion) -> _PymlValueUnion:
    match value:
      case new.Block(_, _):
        return value
      case new.Sequence(parts):
        lines: list[str] = []
        for part in parts:
          lines.append("- " + part)
        return new.Block(True, lines)
      case new.Mapping(keys, values):
        lines: list[str] = []
        for i in range(len(keys)):
          lines.append(keys[i] + ": " + values[i])
        return new.Block(False, lines)
      case _:
        self._fail(line, "expand expects container")
    empty: list[str] = []
    return new.Block(False, empty)

  def _literal(self, text: str) -> _PymlValueUnion:
    raw: str = text.strip()
    lower: str = raw.lower()
    if lower in {"true", "false"}:
      return new.Boolean(raw)
    if lower in {"null", "~"}:
      return new.Null()
    if raw.startsWith("[") and raw.endsWith("]"):
      body: str = raw[1:-1].strip()
      parts: list[str] = []
      if body:
        parts = _pymlSplit(body)
      return new.Sequence(parts)
    if raw.startsWith("{") and raw.endsWith("}"):
      body: str = raw[1:-1].strip()
      keys: list[str] = []
      values: list[str] = []
      if body:
        for part in _pymlSplit(body):
          at: int = _pymlFindColon(part)
          if at < 0:
            raise PymlError()
          keys.append(part[:at].strip())
          values.append(part[at + 1:].strip())
      return new.Mapping(keys, values)
    if (raw.startsWith("'") and raw.endsWith("'")) or (raw.startsWith('"') and raw.endsWith('"')):
      return new.String(raw)
    dot: int = raw.find(".")
    if dot >= 0:
      return new.Float(raw)
    if raw and (raw[0] == ord("-") or (raw[0] >= ord("0") and raw[0] <= ord("9"))):
      return new.Integer(raw)
    return new.String(_pymlQuote(raw))

  def _blockLiteral(self, begin: int, end: int, parentIndent: int) -> _PymlValueUnion:
    """Preserve an indented YAML variable block as an expression container."""
    kind: int = 0
    for i in range(begin, end):
      line: _PymlLine = self.lines[i]
      if line.indent != parentIndent + 2:
        continue
      if line.text.startsWith("- "):
        kind = 2
      elif _pymlFindColon(line.text) >= 0:
        kind = 1
      else:
        self._fail(line, "invalid block literal")
      break
    if not kind:
      emptyKeys: list[str] = []
      emptyValues: list[str] = []
      return new.Mapping(emptyKeys, emptyValues)
    if kind == 2:
      parts: list[str] = []
      i: int = begin
      while i < end:
        line: _PymlLine = self.lines[i]
        if line.indent != parentIndent + 2:
          i += 1
          continue
        if not line.text.startsWith("- "):
          self._fail(line, "mixed block literal")
        child: int = i + 1
        after: int = self._subtreeEnd(child, line.indent, end)
        rhs: str = line.text[2:len(line.text)].strip()
        if child < after:
          if rhs:
            self._fail(line, "sequence item cannot have both value and body")
          rhs = self._valueText(self._blockLiteral(child, after, line.indent))
        parts.append(rhs if rhs else "null")
        i = after
      return new.Sequence(parts)
    keys: list[str] = []
    values: list[str] = []
    i: int = begin
    while i < end:
      line: _PymlLine = self.lines[i]
      if line.indent != parentIndent + 2:
        i += 1
        continue
      at: int = _pymlFindColon(line.text)
      if at < 0 or line.text.startsWith("- "):
        self._fail(line, "mixed block literal")
      child: int = i + 1
      after: int = self._subtreeEnd(child, line.indent, end)
      key: str = line.text[:at].strip()
      rhs: str = line.text[at + 1:len(line.text)].strip()
      if child < after:
        if rhs:
          self._fail(line, "mapping item cannot have both value and body")
        rhs = self._valueText(self._blockLiteral(child, after, line.indent))
      keys.append(key)
      values.append(rhs if rhs else "null")
      i = after
    return new.Mapping(keys, values)

  def _symbol(self, line: _PymlLine, name: str) -> _PymlValueUnion:
    if name not in self.symbols:
      self._fail(line, "undefined " + name)
    return self.symbols[name]

  def _accessSteps(self, line: _PymlLine, text: str) -> list[str]:
    """Parse $root.property[index] paths without permitting arbitrary attributes."""
    if not text.startsWith("$"):
      self._fail(line, "access path requires $")
    firstEnd: int = 1
    while firstEnd < len(text) and text[firstEnd] not in ".[":
      firstEnd += 1
    root: str = text[:firstEnd]
    if len(root) < 2 or not root[1:len(root)].isIdentifier():
      self._fail(line, "invalid access root")
    steps: list[str] = [root]
    i: int = firstEnd
    while i < len(text):
      if text[i] == ord("."):
        end: int = i + 1
        while end < len(text) and text[end] not in ".[":
          end += 1
        name: str = text[i + 1:end]
        if not name.isIdentifier():
          self._fail(line, "invalid property access")
        steps.append("." + name)
        i = end
      elif text[i] == ord("["):
        end: int = i + 1
        depth: int = 1
        quote: char = 0
        while end < len(text) and depth:
          c: char = text[end]
          match c:
            case q if q in "'\"":
              if not quote:
                quote = q
              elif quote == q:
                quote = 0
            case q if not quote and q == ord("["):
              depth += 1
            case q if not quote and q == ord("]"):
              depth -= 1
            case _:
              pass
          end += 1
        if depth:
          self._fail(line, "unterminated subscript")
        index: str = text[i + 1:end - 1].strip()
        if not index:
          self._fail(line, "empty subscript")
        steps.append("[" + index + "]")
        i = end
      else:
        self._fail(line, "invalid access path")
    return steps

  def _mappingKey(self, value: _PymlValueUnion) -> str:
    raw: str = self._valueText(value)
    match value:
      case new.String(_) if len(raw) >= 2:
        return raw[1:len(raw) - 1]
      case new.Integer(_) | new.Float(_) | new.Boolean(_) | new.Null():
        return raw
      case _:
        return ""

  def _mappingFind(self, keys: list[str], key: str) -> int:
    for i in range(len(keys)):
      raw: str = keys[i]
      if len(raw) >= 2 and ((raw.startsWith("\"") and raw.endsWith("\"")) or (raw.startsWith("'") and raw.endsWith("'"))):
        raw = raw[1:len(raw) - 1]
      if raw == key:
        return i
    return -1

  def _accessRead(self, line: _PymlLine, text: str) -> _PymlValueUnion:
    steps: list[str] = self._accessSteps(line, text)
    value: _PymlValueUnion = self._symbol(line, steps[0])
    for i in range(1, len(steps)):
      step: str = steps[i]
      if step.startsWith("."):
        key: str = step[1:len(step)]
        match value:
          case new.Mapping(keys, values):
            at: int = self._mappingFind(keys, key)
            if at < 0:
              self._fail(line, "mapping key not found")
            value = self._literal(values[at])
          case _:
            self._fail(line, "property access expects mapping")
      else:
        index: _PymlValueUnion = self._expr(line, step[1:len(step) - 1])
        match value:
          case new.Sequence(parts):
            match index:
              case new.Integer(raw):
                at: int = int(raw)
                if at < 0:
                  at += len(parts)
                if at < 0 or at >= len(parts):
                  self._fail(line, "sequence index out of range")
                value = self._literal(parts[at])
              case _:
                self._fail(line, "sequence index must be integer")
          case new.Mapping(keys, values):
            key = self._mappingKey(index)
            if not key:
              self._fail(line, "mapping index must be scalar")
            at = self._mappingFind(keys, key)
            if at < 0:
              self._fail(line, "mapping key not found")
            value = self._literal(values[at])
          case _:
            self._fail(line, "subscript expects collection")
    return value

  def _accessReplace(self, line: _PymlLine, value: _PymlValueUnion, steps: list[str], pos: int, replacement: _PymlValueUnion) -> _PymlValueUnion:
    if pos >= len(steps):
      return replacement
    step: str = steps[pos]
    if step.startsWith("."):
      key: str = step[1:len(step)]
      match value:
        case new.Mapping(keys, values):
          nextKeys: list[str] = keys.copy()
          nextValues: list[str] = values.copy()
          at: int = self._mappingFind(nextKeys, key)
          if at < 0:
            if pos != len(steps) - 1:
              self._fail(line, "mapping key not found")
            nextKeys.append(key)
            nextValues.append(self._valueText(replacement))
          else:
            nextValue: _PymlValueUnion = self._literal(nextValues[at])
            nextValues[at] = self._valueText(self._accessReplace(line, nextValue, steps, pos + 1, replacement))
          return new.Mapping(nextKeys, nextValues)
        case _:
          self._fail(line, "property assignment expects mapping")
    index: _PymlValueUnion = self._expr(line, step[1:len(step) - 1])
    match value:
      case new.Sequence(parts):
        match index:
          case new.Integer(raw):
            at: int = int(raw)
            if at < 0:
              at += len(parts)
            if at < 0 or at >= len(parts):
              self._fail(line, "sequence index out of range")
            nextParts: list[str] = parts.copy()
            nextValue: _PymlValueUnion = self._literal(nextParts[at])
            nextParts[at] = self._valueText(self._accessReplace(line, nextValue, steps, pos + 1, replacement))
            return new.Sequence(nextParts)
          case _:
            self._fail(line, "sequence index must be integer")
      case new.Mapping(keys, values):
        key: str = self._mappingKey(index)
        if not key:
          self._fail(line, "mapping index must be scalar")
        nextKeys: list[str] = keys.copy()
        nextValues: list[str] = values.copy()
        at: int = self._mappingFind(nextKeys, key)
        if at < 0:
          if pos != len(steps) - 1:
            self._fail(line, "mapping key not found")
          nextKeys.append(key)
          nextValues.append(self._valueText(replacement))
        else:
          nextValue: _PymlValueUnion = self._literal(nextValues[at])
          nextValues[at] = self._valueText(self._accessReplace(line, nextValue, steps, pos + 1, replacement))
        return new.Mapping(nextKeys, nextValues)
      case _:
        self._fail(line, "subscript assignment expects collection")
    return replacement

  def _accessWrite(self, line: _PymlLine, text: str, value: _PymlValueUnion):
    steps: list[str] = self._accessSteps(line, text)
    if len(steps) == 1:
      self.symbols[steps[0]] = value
      return
    root: _PymlValueUnion = self._symbol(line, steps[0])
    self.symbols[steps[0]] = self._accessReplace(line, root, steps, 1, value)

  def _valueText(self, value: _PymlValueUnion) -> str:
    match value:
      case new.Integer(raw) | new.Float(raw) | new.String(raw) | new.Boolean(raw):
        return raw
      case new.Null():
        return "null"
      case new.Sequence(parts):
        return "[" + ", ".join(parts) + "]"
      case new.Mapping(keys, values):
        out: list[str] = []
        for i in range(len(keys)):
          out.append(keys[i] + ": " + values[i])
        return "{" + ", ".join(out) + "}"
      case new.Block(_, lines):
        return "\n".join(lines)
      case new.Def(_, _, _, _, _, _) | new.Inline(_, _, _, _, _, _):
        return ""

  def _truth(self, value: _PymlValueUnion) -> bool:
    match value:
      case new.Boolean(raw):
        return raw.lower() == "true"
      case new.Null():
        return False
      case new.Integer(raw):
        return int(raw) != 0
      case new.Float(raw):
        return float(raw) != 0.0
      case new.Sequence(parts):
        return bool(parts)
      case new.Mapping(keys, _):
        return bool(keys)
      case new.String(raw):
        return raw not in {"\"\"", "''"}
      case new.Block(_, lines):
        return bool(lines)
      case _:
        return False

  def _signature(self, line: _PymlLine, text: str) -> (str, list[str], list[str]):
    openAt: int = text.find("(")
    if openAt < 2 or not text.endsWith(")"):
      self._fail(line, "invalid callable declaration")
    name: str = text[:openAt].strip()
    if not name.startsWith("$"):
      self._fail(line, "callable name requires $")
    params: list[str] = []
    defaults: list[str] = []
    body: str = text[openAt + 1:-1].strip()
    if body:
      for part in _pymlSplit(body):
        at: int = _pymlFindColon(part)
        param: str = part.strip()
        default: str = ""
        if at >= 0:
          param = part[:at].strip()
          default = part[at + 1:].strip()
        if not param.startsWith("$") or param in params:
          self._fail(line, "invalid callable parameter")
        params.append(param)
        defaults.append(default)
    return (name, params, defaults)

  def _bindCall(self, line: _PymlLine, params: list[str], defaults: list[str], argsText: str) -> dict[str, _PymlValueUnion]:
    bound: dict[str, _PymlValueUnion] = {}
    args: list[str] = []
    if argsText.strip():
      args = _pymlSplit(argsText)
    nextPos: int = 0
    for arg in args:
      at: int = _pymlFindColon(arg)
      if at < 0:
        at = arg.find("=")
      name: str = ""
      valueText: str = arg
      if at >= 0:
        name = arg[:at].strip()
        valueText = arg[at + 1:].strip()
        if not name.startsWith("$") or name not in params:
          self._fail(line, "invalid keyword argument")
      else:
        if nextPos >= len(params):
          self._fail(line, "too many arguments")
        name = params[nextPos]
        nextPos += 1
      if name in bound:
        self._fail(line, "duplicate argument")
      bound[name] = self._expr(line, valueText)
    for i in range(len(params)):
      if params[i] not in bound:
        if not defaults[i]:
          self._fail(line, "missing argument")
        default: str = defaults[i]
        if default.startsWith("="):
          bound[params[i]] = self._expr(line, default[1:])
        else:
          bound[params[i]] = self._literal(default)
    return bound

  def _call(self, line: _PymlLine, text: str, wantInline: bool) -> _PymlValueUnion:
    openAt: int = text.find("(")
    if openAt < 2 or not text.endsWith(")"):
      self._fail(line, "invalid callable invocation")
    name: str = text[:openAt].strip()
    target: _PymlValueUnion = self._symbol(line, name)
    params: list[str] = []
    defaults: list[str] = []
    begin: int = 0
    end: int = 0
    bodyIndent: int = 0
    closure: dict[str, _PymlValueUnion] = {}
    kind: int = 0
    match target:
      case new.Def(p, d, b, e, ind, captured):
        for item in p:
          params.append(item)
        for item in d:
          defaults.append(item)
        begin = b
        end = e
        bodyIndent = ind + 2
        closure = captured.copy()
        kind = 1
      case new.Inline(p, d, b, e, ind, captured):
        for item in p:
          params.append(item)
        for item in d:
          defaults.append(item)
        begin = b
        end = e
        bodyIndent = ind + 2
        closure = captured.copy()
        kind = 2
      case _:
        self._fail(line, "symbol is not callable")
    if (wantInline and kind != 2) or (not wantInline and kind != 1):
      self._fail(line, "invalid callable kind")
    if name in self.callStack:
      self._fail(line, "recursive callable")
    oldSymbols: dict[str, _PymlValueUnion] = self.symbols
    oldReturned: bool = self.returned
    oldReturn: _PymlValueUnion = self.resultValue
    oldKind: int = self.runKind
    args: dict[str, _PymlValueUnion] = self._bindCall(line, params, defaults, text[openAt + 1:-1])
    self.symbols = closure.copy()
    for param in params:
      self.symbols[param] = args[param]
    self.returned = False
    self.resultValue = self._literal("null")
    self.runKind = kind
    self.callStack.append(name)
    emitted: list[str] = []
    self._run(begin, end, bodyIndent, emitted)
    self.callStack.pop()
    result: _PymlValueUnion = new.Null()
    if kind == 1:
      if emitted or not self.returned:
        self._fail(line, "invalid scalar function result")
      result = self.resultValue
      match result:
        case new.Sequence(_) | new.Mapping(_) | new.Block(_, _) | new.Def(_, _, _, _, _, _) | new.Inline(_, _, _, _, _, _):
          self._fail(line, "scalar function returned container")
        case _:
          pass
    else:
      if self.returned or not emitted:
        self._fail(line, "invalid inline result")
      normalized: list[str] = []
      for emittedLine in emitted:
        normalized.append(emittedLine[bodyIndent:])
      first: str = normalized[0].lstrip()
      sequence: bool = first.startsWith("- ")
      for emittedLine in normalized:
        isSequence: bool = emittedLine.lstrip().startsWith("- ")
        if len(emittedLine) - len(emittedLine.lstrip()) == 0 and isSequence != sequence:
          self._fail(line, "mixed inline container")
      result: _PymlValueUnion = new.Block(sequence, normalized)
    self.symbols = oldSymbols
    self.returned = oldReturned
    self.resultValue = oldReturn
    self.runKind = oldKind
    return result

  def _binary(self, line: _PymlLine, leftText: str, rightText: str, op: str) -> _PymlValueUnion:
    left: _PymlValueUnion = self._expr(line, leftText)
    right: _PymlValueUnion = self._expr(line, rightText)
    leftRaw: str = self._valueText(left)
    rightRaw: str = self._valueText(right)
    match left:
      case new.Sequence(left_parts):
        match right:
          case new.Sequence(right_parts):
            if op != "+":
              self._fail(line, "invalid sequence operator")
            parts: list[str] = []
            for part in left_parts:
              parts.append(part)
            for part in right_parts:
              parts.append(part)
            return new.Sequence(parts)
          case _:
            self._fail(line, "invalid sequence operator")
      case _:
        pass
    isString: bool = False
    match left:
      case new.String(_):
        isString = True
      case _:
        pass
    match right:
      case new.String(_):
        isString = True
      case _:
        pass
    if isString:
      if op != "+":
        self._fail(line, "invalid string operator")
      return new.String(_pymlQuote(leftRaw[1:-1] + rightRaw[1:-1]))
    isFloat: bool = False
    match left:
      case new.Float(_):
        isFloat = True
      case _:
        pass
    match right:
      case new.Float(_):
        isFloat = True
      case _:
        pass
    isNumber: bool = False
    match left:
      case new.Integer(_) | new.Float(_):
        match right:
          case new.Integer(_) | new.Float(_):
            isNumber = True
          case _:
            pass
      case _:
        pass
    if not isNumber:
      self._fail(line, "invalid arithmetic operands")
    if isFloat:
      raw: str = ""
      match op:
        case "+":
          raw = str(float(leftRaw) + float(rightRaw))
        case "-":
          raw = str(float(leftRaw) - float(rightRaw))
        case "*":
          raw = str(float(leftRaw) * float(rightRaw))
        case "/":
          raw = str(float(leftRaw) / float(rightRaw))
        case _:
          raw = str(float(leftRaw) % float(rightRaw))
      return new.Float(raw)
    raw: str = ""
    match op:
      case "+":
        raw = str(int(leftRaw) + int(rightRaw))
      case "-":
        raw = str(int(leftRaw) - int(rightRaw))
      case "*":
        raw = str(int(leftRaw) * int(rightRaw))
      case "/":
        raw = str(int(leftRaw) / int(rightRaw))
      case _:
        raw = str(int(leftRaw) % int(rightRaw))
    return new.Integer(raw)

  def _equal(self, left: _PymlValueUnion, right: _PymlValueUnion) -> bool:
    leftRaw: str = self._valueText(left)
    rightRaw: str = self._valueText(right)
    match left:
      case new.Integer(_) | new.Float(_):
        match right:
          case new.Integer(_) | new.Float(_):
            return float(leftRaw) == float(rightRaw)
          case _:
            return False
      case _:
        return leftRaw == rightRaw

  def _compare(self, line: _PymlLine, leftText: str, rightText: str, op: str) -> _PymlValueUnion:
    left: _PymlValueUnion = self._expr(line, leftText)
    right: _PymlValueUnion = self._expr(line, rightText)
    equal: bool = self._equal(left, right)
    value: bool = False
    match op:
      case "==":
        value = equal
      case "!=":
        value = not equal
      case _:
        leftRaw: str = self._valueText(left)
        rightRaw: str = self._valueText(right)
        numeric: bool = False
        match left:
          case new.Integer(_) | new.Float(_):
            match right:
              case new.Integer(_) | new.Float(_):
                numeric = True
              case _:
                pass
          case _:
            pass
        if numeric:
          match op:
            case "<":
              value = float(leftRaw) < float(rightRaw)
            case "<=":
              value = float(leftRaw) <= float(rightRaw)
            case ">":
              value = float(leftRaw) > float(rightRaw)
            case _:
              value = float(leftRaw) >= float(rightRaw)
        else:
          match left:
            case new.String(_):
              match right:
                case new.String(_):
                  match op:
                    case "<":
                      value = leftRaw < rightRaw
                    case "<=":
                      value = leftRaw <= rightRaw
                    case ">":
                      value = leftRaw > rightRaw
                    case _:
                      value = leftRaw >= rightRaw
                case _:
                  self._fail(line, "invalid comparison operands")
            case _:
              self._fail(line, "invalid comparison operands")
    return new.Boolean("true" if value else "false")

  def _expr(self, line: _PymlLine, text: str) -> _PymlValueUnion:
    expr: str = text.strip()
    if _pymlOuterParentheses(expr):
      return self._expr(line, expr[1:len(expr) - 1])
    ifMarker: int = expr.find(" if ")
    if ifMarker >= 0:
      elseMarker: int = expr.find(" else ", ifMarker + 4)
      if elseMarker < 0:
        self._fail(line, "ternary expression requires else")
      condition: _PymlValueUnion = self._expr(line, expr[ifMarker + 4:elseMarker])
      if self._truth(condition):
        return self._expr(line, expr[:ifMarker])
      return self._expr(line, expr[elseMarker + 6:])
    orMarker: int = expr.find(" or ")
    if orMarker >= 0:
      left: _PymlValueUnion = self._expr(line, expr[:orMarker])
      if self._truth(left):
        return left
      return self._expr(line, expr[orMarker + 4:])
    andMarker: int = expr.find(" and ")
    if andMarker >= 0:
      left: _PymlValueUnion = self._expr(line, expr[:andMarker])
      if not self._truth(left):
        return left
      return self._expr(line, expr[andMarker + 5:])
    if expr.startsWith("not "):
      value: _PymlValueUnion = self._expr(line, expr[4:])
      return new.Boolean("false" if self._truth(value) else "true")
    compareOps: list[str] = ["==", "!=", "<=", ">=", "<", ">"]
    for compareOp in compareOps:
      compareAt: int = _pymlFindOperator(expr, compareOp)
      if compareAt >= 0:
        return self._compare(line, expr[:compareAt], expr[compareAt + len(compareOp):], compareOp)
    ops: list[str] = ["+", "-", "*", "/", "%"]
    for op in ops:
      at: int = _pymlFindOperator(expr, op)
      if at >= 0:
        return self._binary(line, expr[:at], expr[at + 1:], op)
    if expr.startsWith("len(") and expr.endsWith(")"):
      value: _PymlValueUnion = self._expr(line, expr[4:-1])
      match value:
        case new.Sequence(parts):
          return new.Integer(str(len(parts)))
        case new.Mapping(keys, _):
          return new.Integer(str(len(keys)))
        case new.String(raw):
          return new.Integer(str(len(raw) - 2))
        case _:
          self._fail(line, "len expects collection")
    if expr.startsWith("$") and expr.endsWith(")") and "." in expr:
      dot: int = expr.rfind(".")
      receiver: _PymlValueUnion = self._accessRead(line, expr[:dot])
      method: str = expr[dot + 1:]
      if method not in {"keys()", "values()", "items()"}:
        self._fail(line, "unsupported collection method")
      match receiver:
        case new.Mapping(keys, values):
          parts: list[str] = []
          for i in range(len(keys)):
            if method == "keys()":
              parts.append(keys[i])
            elif method == "values()":
              parts.append(values[i])
            else:
              parts.append("[" + keys[i] + ", " + values[i] + "]")
          return new.Sequence(parts)
        case _:
          self._fail(line, "collection method expects mapping")
    if expr.startsWith("$") and expr.find(" ") < 0 and expr.find("(") < 0:
      return self._accessRead(line, expr)
    if expr.startsWith("$") and expr.endsWith(")") and expr.find("(") >= 2:
      return self._call(line, expr, False)
    if expr.startsWith("f\"") and expr.endsWith('"'):
      body: str = expr[2:-1]
      out: str = ""
      i: int = 0
      while i < len(body):
        if body[i] == ord("{"):
          end: int = body.find("}", i + 1)
          if end < 0:
            self._fail(line, "unterminated f-string")
          name: str = body[i + 1:end].strip()
          part: _PymlValueUnion = self._expr(line, name)
          raw: str = self._valueText(part)
          match part:
            case new.String(_) if len(raw) >= 2:
              raw = raw[1:-1]
            case _:
              pass
          out += raw
          i = end + 1
        else:
          out += body[i]
          i += 1
      return new.String(_pymlQuote(out))
    if expr.startsWith("range(") and expr.endsWith(")"):
      args: list[str] = _pymlSplit(expr[6:-1])
      start: int = 0
      stop: int = 0
      step: int = 1
      argc: int = len(args)
      if argc < 1 or argc > 3:
        self._fail(line, "range expects one to three arguments")
      elif argc == 1:
        stop = int(self._valueText(self._expr(line, args[0])))
      else:
        start = int(self._valueText(self._expr(line, args[0])))
        stop = int(self._valueText(self._expr(line, args[1])))
        if argc == 3:
          step = int(self._valueText(self._expr(line, args[2])))
      if not step:
        self._fail(line, "range step cannot be zero")
      parts: list[str] = []
      for i in range(start, stop, step):
        parts.append(str(i))
      return new.Sequence(parts)
    return self._literal(expr)

  def _emitValue(self, value: _PymlValueUnion, indent: int, out: list[str] @ref):
    for raw in self._valueText(value).splitLines():
      out.append(" " * indent + raw)

  def _runDirectiveBody(self, begin: int, end: int, indent: int, out: list[str] @ref):
    """Run a directive body at its parent indentation and isolate document scope."""
    emitted: list[str] = []
    oldSymbols: dict[str, _PymlValueUnion] = self.symbols
    if not self.runKind:
      self.symbols = oldSymbols.copy()
    self._run(begin, end, indent + 2, emitted)
    if not self.runKind:
      self.symbols = oldSymbols
    for text in emitted:
      out.append(text[2:len(text)])

  def _run(self, begin: int, end: int, indent: int, out: list[str] @ref):
    i: int = begin
    while i < end:
      if self.returned:
        return
      line: _PymlLine = self.lines[i]
      if line.indent != indent:
        i += 1
        continue
      text: str = line.text
      child: int = i + 1
      after: int = self._subtreeEnd(child, indent, end)
      if text.startsWith("@from "):
        if self.runKind or indent:
          self._fail(line, "from import is only allowed at module root")
        if child < after:
          self._fail(line, "from import cannot have body")
        self._importSymbols(line, text)
        i = after
        continue
      if text.startsWith("@def ") and text.endsWith(":"):
        if self.runKind:
          self._fail(line, "nested callable declaration")
        name: str = ""
        params: list[str] = []
        defaults: list[str] = []
        (name, params, defaults) = self._signature(line, text[5:-1].strip())
        if name in self.symbols:
          self._fail(line, "duplicate symbol")
        definition: _PymlValueUnion = new.Def(params, defaults, child, after, indent, self.symbols.copy())
        self.symbols[name] = definition
        i = after
        continue
      if text.startsWith("@inline ") and text.endsWith(":"):
        if self.runKind:
          self._fail(line, "nested callable declaration")
        name: str = ""
        params: list[str] = []
        defaults: list[str] = []
        (name, params, defaults) = self._signature(line, text[8:-1].strip())
        if name in self.symbols:
          self._fail(line, "duplicate symbol")
        definition: _PymlValueUnion = new.Inline(params, defaults, child, after, indent, self.symbols.copy())
        self.symbols[name] = definition
        i = after
        continue
      if text.startsWith("@return "):
        if self.runKind != 1:
          self._fail(line, "return outside scalar function")
        if child < after:
          self._fail(line, "return cannot have body")
        self.resultValue = self._expr(line, text[8:])
        self.returned = True
        return
      if text.startsWith("$"):
        colon: int = _pymlFindColon(text)
        if colon < 0:
          self._fail(line, "invalid variable binding")
        name: str = text[:colon].strip()
        rhs: str = text[colon + 1:len(text)].strip()
        steps: list[str] = self._accessSteps(line, name)
        if child < after and len(steps) != 1:
          self._fail(line, "nested access assignment cannot have body")
        if rhs.startsWith("+="):
          current: _PymlValueUnion = self._accessRead(line, name)
          self._accessWrite(line, name, self._binary(line, self._valueText(current), rhs[2:], "+"))
        elif rhs.startsWith("-="):
          current = self._accessRead(line, name)
          self._accessWrite(line, name, self._binary(line, self._valueText(current), rhs[2:], "-"))
        elif rhs.startsWith("*="):
          current = self._accessRead(line, name)
          self._accessWrite(line, name, self._binary(line, self._valueText(current), rhs[2:], "*"))
        elif rhs.startsWith("/="):
          current = self._accessRead(line, name)
          self._accessWrite(line, name, self._binary(line, self._valueText(current), rhs[2:], "/"))
        elif rhs.startsWith("%="):
          current = self._accessRead(line, name)
          self._accessWrite(line, name, self._binary(line, self._valueText(current), rhs[2:], "%"))
        elif rhs.startsWith("="):
          self._accessWrite(line, name, self._expr(line, rhs[1:]))
        elif rhs:
          self._accessWrite(line, name, self._literal(rhs))
        else:
          self._accessWrite(line, name, self._blockLiteral(child, after, indent))
        i = after
        continue
      if text.startsWith("@if ") and text.endsWith(":"):
        cond: _PymlValueUnion = self._expr(line, text[4:-1])
        matched: bool = self._truth(cond)
        if matched:
          self._runDirectiveBody(child, after, indent, out)
        branch: int = after
        while branch < end and self.lines[branch].indent == indent:
          alternate: _PymlLine = self.lines[branch]
          alternateText: str = alternate.text
          alternateChild: int = branch + 1
          alternateAfter: int = self._subtreeEnd(alternateChild, indent, end)
          if alternateText.startsWith("@elif ") and alternateText.endsWith(":"):
            if not matched:
              alternateCond: _PymlValueUnion = self._expr(alternate, alternateText[6:-1])
              if self._truth(alternateCond):
                self._runDirectiveBody(alternateChild, alternateAfter, indent, out)
                matched = True
            branch = alternateAfter
            continue
          if alternateText == "@else:":
            if not matched:
              self._runDirectiveBody(alternateChild, alternateAfter, indent, out)
              matched = True
            branch = alternateAfter
            break
          break
        i = branch
        continue
      if text.startsWith("@elif ") or text == "@else:":
        self._fail(line, "orphan conditional branch")
      if text.startsWith("@for ") and text.endsWith(":"):
        spec: str = text[5:-1].strip()
        marker: int = spec.find(" in ")
        if marker < 0:
          self._fail(line, "invalid for")
        name: str = spec[:marker].strip()
        names: list[str] = _pymlSplit(name)
        if not names:
          self._fail(line, "invalid for target")
        for targetName in names:
          if not targetName.startsWith("$"):
            self._fail(line, "for target requires $")
        values: _PymlValueUnion = self._expr(line, spec[marker + 4:])
        parts: list[str] = []
        isSequence: bool = False
        match values:
          case new.Sequence(items):
            for item in items:
              parts.append(item)
            isSequence = True
          case _:
            self._fail(line, "for expects sequence")
        if not isSequence:
          self._fail(line, "for expects sequence")
        for raw in parts:
          oldSymbols: dict[str, _PymlValueUnion] = self.symbols
          if not self.runKind:
            self.symbols = oldSymbols.copy()
          if len(names) == 1:
            self.symbols[names[0]] = self._literal(raw)
          else:
            tupleValue: _PymlValueUnion = self._literal(raw)
            match tupleValue:
              case new.Sequence(tuple_parts):
                if len(tuple_parts) != len(names):
                  self._fail(line, "for unpacking arity")
                for j in range(len(names)):
                  self.symbols[names[j]] = self._literal(tuple_parts[j])
              case _:
                self._fail(line, "for unpacking expects sequence")
          self._runDirectiveBody(child, after, indent, out)
          if not self.runKind:
            self.symbols = oldSymbols
        i = after
        continue
      if text.startsWith("@expand "):
        if self.runKind == 1:
          self._fail(line, "scalar function cannot expand container")
        if child < after:
          self._fail(line, "expand cannot have body")
        expandText: str = text[8:].strip()
        value: _PymlValueUnion = new.Null()
        if expandText.startsWith("$") and expandText.endsWith(")"):
          value = self._call(line, expandText, True)
        else:
          value = self._expr(line, expandText)
        block: _PymlValueUnion = self._asBlock(line, value)
        expected: int = self._containerKind(begin, end, indent)
        match block:
          case new.Block(sequence, lines):
            if expected == 1 and sequence:
              self._fail(line, "sequence cannot expand into mapping")
            if expected == 2 and not sequence:
              self._fail(line, "mapping cannot expand into sequence")
            for emitted in lines:
              out.append(" " * indent + emitted)
          case _:
            self._fail(line, "expand expects container")
        i = after
        continue
      colon: int = _pymlFindColon(text)
      if colon >= 0:
        if self.runKind == 1:
          self._fail(line, "scalar function cannot emit YAML")
        key: str = text[:colon].strip()
        rhs: str = text[colon + 1:].strip()
        if key.startsWith("="):
          keyValue: _PymlValueUnion = self._expr(line, key[1:])
          match keyValue:
            case new.Integer(_) | new.Float(_) | new.String(_) | new.Boolean(_) | new.Null():
              key = self._valueText(keyValue)
            case _:
              self._fail(line, "dynamic key must be scalar")
          if len(key) >= 2 and key[0] == ord('"'):
            key = key[1:-1]
        if rhs.startsWith("="):
          rhs = self._valueText(self._expr(line, rhs[1:]))
        out.append(" " * indent + key + ":" + (" " + rhs if rhs else ""))
        if child < after:
          self._run(child, after, indent + 2, out)
        i = after
        continue
      if text.startsWith("- "):
        if self.runKind == 1:
          self._fail(line, "scalar function cannot emit YAML")
        rhs: str = text[2:len(text)].strip()
        if rhs.startsWith("="):
          rhs = self._valueText(self._expr(line, rhs[1:]))
        out.append(" " * indent + "- " + rhs)
        if child < after:
          self._run(child, after, indent + 2, out)
        i = after
        continue
      self._fail(line, "unsupported PyML statement")

  def _foldMappingUpdates(self, out: list[str]) -> list[str]:
    """Fold duplicate mapping keys with dict.update last-write-wins semantics."""
    result: list[str] = []
    i: int = 0
    while i < len(out):
      raw: str = out[i]
      indent: int = _pymlIndent(raw)
      text: str = raw[indent:len(raw)]
      at: int = _pymlFindColon(text)
      if at < 0 or text.startsWith("- "):
        result.append(raw)
        i += 1
        continue
      after: int = i + 1
      while after < len(out) and _pymlIndent(out[after]) > indent:
        after += 1
      key: str = text[:at].strip()
      previous: int = -1
      for j in range(len(result) - 1, -1, -1):
        candidate: str = result[j]
        candidateIndent: int = _pymlIndent(candidate)
        if candidateIndent < indent:
          break
        candidateText: str = candidate[candidateIndent:len(candidate)]
        candidateAt: int = _pymlFindColon(candidateText)
        if candidateIndent == indent and candidateAt >= 0 and not candidateText.startsWith("- ") and candidateText[:candidateAt].strip() == key:
          previous = j
          break
      if previous >= 0:
        removeEnd: int = previous + 1
        while removeEnd < len(result) and _pymlIndent(result[removeEnd]) > indent:
          removeEnd += 1
        kept: list[str] = []
        for j in range(len(result)):
          if j < previous or j >= removeEnd:
            kept.append(result[j])
        result = kept
      result.append(out[i])
      if i + 1 < after:
        children: list[str] = []
        for j in range(i + 1, after):
          children.append(out[j])
        children = self._foldMappingUpdates(children)
        for childLine in children:
          result.append(childLine)
      i = after
    return result

  def expand(self) -> str:
    out: list[str] = []
    self._run(0, len(self.lines), 0, out)
    out = self._foldMappingUpdates(out)
    return "\n".join(out) + ("\n" if out else "")


class Pyml:
  @staticmethod
  def expand(s: str, context: PymlContext = new()) -> str:
    expander: _PymlExpander = new(s, context)
    return expander.expand()

  @staticmethod
  def loads[T](s: str, context: PymlContext = new()) -> T:
    return Yaml.loads[T](Self.expand(s, context))

  @staticmethod
  def load[T](fp: TextIOWrapper, context: PymlContext = new()) -> T:
    return Self.loads[T](fp.read(), context)

  @staticmethod
  def loadString[T](fp: StringIO, context: PymlContext = new()) -> T:
    return Self.loads[T](fp.read(), context)
