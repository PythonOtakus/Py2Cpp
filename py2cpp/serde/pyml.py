"""PyML 配置模板展开器。"""
from ..builtins import *
from ..core.exceptions import Exception, ValueError
from ..io import StringIO, TextIOWrapper
from ..io.file.path import exists, join, realpath
from .json import JsonEncoder
from .yaml import Yaml


class PymlError(Exception):
  pass


@immutable
def _pyml_strip_comment(value: str) -> str:
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
  module_name: str = ""
  module_root: str = ""
  allowed_root: str = ""


@union
class _PymlValue:
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
    closure: dict[str, _PymlValue]

  @variant
  class Inline:
    params: list[str]
    defaults: list[str]
    begin: int
    end: int
    indent: int
    closure: dict[str, _PymlValue]

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
def _pyml_quote(value: str) -> str:
  return JsonEncoder.encode_str(value)


@immutable
def _pyml_indent(line: str) -> int:
  n: int = 0
  for i in range(len(line)):
    if line[i] != ord(" "):
      return n
    n += 1
  return n


@immutable
def _pyml_split(text: str, sep: char = 44) -> list[str]:
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
def _pyml_find_colon(text: str) -> int:
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
def _pyml_find_operator(text: str, op: str) -> int:
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
def _pyml_outer_parentheses(text: str) -> bool:
  if len(text) < 2 or not text.startswith("(") or not text.endswith(")"):
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
  source_name: str = "<string>"
  lines: list[_PymlLine] = []
  symbols: dict[str, _PymlValue] = {}
  returned: bool = False
  result_value: _PymlValue
  run_kind: int = 0
  call_stack: list[str] = []
  context: PymlContext
  # Cache source text, never callable indexes tied to an importing line table.
  # Every importer rebases begin/end into its own line table.
  module_cache: dict[str, str] = {}
  import_stack: list[str] = []

  def __init__(self, source: str, context: PymlContext):
    self.lines = []
    self.symbols = {}
    self.returned = False
    self.result_value = self._literal("null")
    self.run_kind = 0
    self.call_stack = []
    self.context = context
    self.module_cache = {}
    self.import_stack = []
    if context.module_name:
      self.source_name = context.module_name
      self.import_stack.append(context.module_name)
    for raw in source.splitlines():
      clean: str = _pyml_strip_comment(raw.replace("\t", "  "))
      if not clean.strip():
        continue
      self.lines.append(_PymlLine(_pyml_indent(clean), clean.strip(), len(self.lines) + 1))

  def _fail(self, line: _PymlLine, message: str):
    raise PymlError()

  def _subtree_end(self, start: int, indent: int, end: int) -> int:
    i: int = start
    while i < end and self.lines[i].indent > indent:
      i += 1
    return i

  def _module_name(self, line: _PymlLine, spec: str) -> str:
    """将受限的 Python 模块路径解析为规范逻辑模块名。"""
    raw: str = spec.strip()
    if not raw or "\\" in raw or "/" in raw or ":" in raw:
      self._fail(line, "invalid module path")
    dots: int = 0
    while dots < len(raw) and raw[dots] == ord("."):
      dots += 1
    tail: str = raw[dots:]
    if not tail or tail.startswith(".") or tail.endswith(".") or ".." in tail:
      self._fail(line, "invalid module path")
    parts: list[str] = tail.split(".")
    for part in parts:
      if not part or not part.isidentifier():
        self._fail(line, "invalid module path")
    if not dots:
      return tail
    if not self.context.module_name:
      self._fail(line, "relative import requires module context")
    base: list[str] = self.context.module_name.split(".")
    base.pop()
    climb: int = dots - 1
    if climb > len(base):
      self._fail(line, "relative import escapes module root")
    for _ in range(climb):
      base.pop()
    for part in parts:
      base.append(part)
    return ".".join(base)

  def _load_module(self, line: _PymlLine, spec: str) -> dict[str, _PymlValue]:
    name: str = self._module_name(line, spec)
    if name in self.import_stack:
      self._fail(line, "module import cycle")
    if not self.context.module_root:
      self._fail(line, "module import requires module_root")
    path: str = self.context.module_root
    for part in name.split("."):
      path = join(path, part)
    path += ".pyml"
    path = realpath(path)
    if self.context.allowed_root:
      allowed: str = realpath(self.context.allowed_root)
      if path != allowed and not path.startswith(allowed + "\\") and not path.startswith(allowed + "/"):
        self._fail(line, "module import escapes allowed root")
    if not exists(path):
      self._fail(line, "module not found")
    child_context: PymlContext = new(
      module_name=name,
      module_root=self.context.module_root,
      allowed_root=self.context.allowed_root,
    )
    source: str = ""
    if name in self.module_cache:
      source = self.module_cache[name]
    else:
      fp: TextIOWrapper = new(path)
      source = fp.read()
      fp.close()
      self.module_cache[name] = source
    self.import_stack.append(name)
    child: Self = new(source, child_context)
    child.module_cache = self.module_cache
    child.import_stack = self.import_stack
    child.expand()
    self.import_stack.pop()
    offset: int = len(self.lines)
    for child_line in child.lines:
      self.lines.append(child_line)
    exports: dict[str, _PymlValue] = {}
    for export_name in child.symbols:
      export_value: _PymlValue = child.symbols[export_name]
      match export_value:
        case new.Def(p, d, b, e, ind, captured):
          exports[export_name] = _PymlValue.Def(p, d, b + offset, e + offset, ind, captured)
        case new.Inline(p, d, b, e, ind, captured):
          exports[export_name] = _PymlValue.Inline(p, d, b + offset, e + offset, ind, captured)
        case _:
          exports[export_name] = export_value
    return exports

  def _import_symbols(self, line: _PymlLine, text: str):
    marker: int = text.find(" import ")
    if marker < 7:
      self._fail(line, "invalid from import")
    module: dict[str, _PymlValue] = self._load_module(line, text[6:marker].strip())
    requested: str = text[marker + 8:].strip()
    if requested == "*":
      for name in module:
        if name in self.symbols:
          self._fail(line, "import collision")
        self.symbols[name] = module[name]
      return
    for item in _pyml_split(requested):
      words: list[str] = item.split(" as ")
      if len(words) > 2:
        self._fail(line, "invalid import alias")
      source: str = words[0].strip()
      target: str = source
      if len(words) == 2:
        target = words[1].strip()
      if not source.startswith("$") or not target.startswith("$") or source not in module:
        self._fail(line, "invalid import symbol")
      if target in self.symbols:
        self._fail(line, "import collision")
      self.symbols[target] = module[source]

  def _container_kind(self, begin: int, end: int, indent: int) -> int:
    """1=mapping, 2=sequence, 0=尚无法由同级元素推断。"""
    for i in range(begin, end):
      line: _PymlLine = self.lines[i]
      if line.indent != indent:
        continue
      text: str = line.text
      if text.startswith("$") or text.startswith("@if ") or text.startswith("@elif ") or text == "@else:" or text.startswith("@for ") or text.startswith("@expand "):
        continue
      if text.startswith("- "):
        return 2
      if _pyml_find_colon(text) >= 0:
        return 1
    return 0

  def _as_block(self, line: _PymlLine, value: _PymlValue) -> _PymlValue:
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

  def _literal(self, text: str) -> _PymlValue:
    raw: str = text.strip()
    lower: str = raw.lower()
    if lower in {"true", "false"}:
      return new.Boolean(raw)
    if lower in {"null", "~"}:
      return new.Null()
    if raw.startswith("[") and raw.endswith("]"):
      body: str = raw[1:-1].strip()
      parts: list[str] = []
      if body:
        parts = _pyml_split(body)
      return new.Sequence(parts)
    if raw.startswith("{") and raw.endswith("}"):
      body: str = raw[1:-1].strip()
      keys: list[str] = []
      values: list[str] = []
      if body:
        for part in _pyml_split(body):
          at: int = _pyml_find_colon(part)
          if at < 0:
            raise PymlError()
          keys.append(part[:at].strip())
          values.append(part[at + 1:].strip())
      return new.Mapping(keys, values)
    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
      return new.String(raw)
    dot: int = raw.find(".")
    if dot >= 0:
      return new.Float(raw)
    if raw and (raw[0] == ord("-") or (raw[0] >= ord("0") and raw[0] <= ord("9"))):
      return new.Integer(raw)
    return new.String(_pyml_quote(raw))

  def _block_literal(self, begin: int, end: int, parent_indent: int) -> _PymlValue:
    """Preserve an indented YAML variable block as an expression container."""
    kind: int = 0
    for i in range(begin, end):
      line: _PymlLine = self.lines[i]
      if line.indent != parent_indent + 2:
        continue
      if line.text.startswith("- "):
        kind = 2
      elif _pyml_find_colon(line.text) >= 0:
        kind = 1
      else:
        self._fail(line, "invalid block literal")
      break
    if not kind:
      empty_keys: list[str] = []
      empty_values: list[str] = []
      return new.Mapping(empty_keys, empty_values)
    if kind == 2:
      parts: list[str] = []
      i: int = begin
      while i < end:
        line: _PymlLine = self.lines[i]
        if line.indent != parent_indent + 2:
          i += 1
          continue
        if not line.text.startswith("- "):
          self._fail(line, "mixed block literal")
        child: int = i + 1
        after: int = self._subtree_end(child, line.indent, end)
        rhs: str = line.text[2:len(line.text)].strip()
        if child < after:
          if rhs:
            self._fail(line, "sequence item cannot have both value and body")
          rhs = self._value_text(self._block_literal(child, after, line.indent))
        parts.append(rhs if rhs else "null")
        i = after
      return new.Sequence(parts)
    keys: list[str] = []
    values: list[str] = []
    i: int = begin
    while i < end:
      line: _PymlLine = self.lines[i]
      if line.indent != parent_indent + 2:
        i += 1
        continue
      at: int = _pyml_find_colon(line.text)
      if at < 0 or line.text.startswith("- "):
        self._fail(line, "mixed block literal")
      child: int = i + 1
      after: int = self._subtree_end(child, line.indent, end)
      key: str = line.text[:at].strip()
      rhs: str = line.text[at + 1:len(line.text)].strip()
      if child < after:
        if rhs:
          self._fail(line, "mapping item cannot have both value and body")
        rhs = self._value_text(self._block_literal(child, after, line.indent))
      keys.append(key)
      values.append(rhs if rhs else "null")
      i = after
    return new.Mapping(keys, values)

  def _symbol(self, line: _PymlLine, name: str) -> _PymlValue:
    if name not in self.symbols:
      self._fail(line, "undefined " + name)
    return self.symbols[name]

  def _value_text(self, value: _PymlValue) -> str:
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

  def _truth(self, value: _PymlValue) -> bool:
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
    open_at: int = text.find("(")
    if open_at < 2 or not text.endswith(")"):
      self._fail(line, "invalid callable declaration")
    name: str = text[:open_at].strip()
    if not name.startswith("$"):
      self._fail(line, "callable name requires $")
    params: list[str] = []
    defaults: list[str] = []
    body: str = text[open_at + 1:-1].strip()
    if body:
      for part in _pyml_split(body):
        at: int = _pyml_find_colon(part)
        param: str = part.strip()
        default: str = ""
        if at >= 0:
          param = part[:at].strip()
          default = part[at + 1:].strip()
        if not param.startswith("$") or param in params:
          self._fail(line, "invalid callable parameter")
        params.append(param)
        defaults.append(default)
    return (name, params, defaults)

  def _bind_call(self, line: _PymlLine, params: list[str], defaults: list[str], args_text: str) -> dict[str, _PymlValue]:
    bound: dict[str, _PymlValue] = {}
    args: list[str] = []
    if args_text.strip():
      args = _pyml_split(args_text)
    next_pos: int = 0
    for arg in args:
      at: int = _pyml_find_colon(arg)
      if at < 0:
        at = arg.find("=")
      name: str = ""
      value_text: str = arg
      if at >= 0:
        name = arg[:at].strip()
        value_text = arg[at + 1:].strip()
        if not name.startswith("$") or name not in params:
          self._fail(line, "invalid keyword argument")
      else:
        if next_pos >= len(params):
          self._fail(line, "too many arguments")
        name = params[next_pos]
        next_pos += 1
      if name in bound:
        self._fail(line, "duplicate argument")
      bound[name] = self._expr(line, value_text)
    for i in range(len(params)):
      if params[i] not in bound:
        if not defaults[i]:
          self._fail(line, "missing argument")
        default: str = defaults[i]
        if default.startswith("="):
          bound[params[i]] = self._expr(line, default[1:])
        else:
          bound[params[i]] = self._literal(default)
    return bound

  def _call(self, line: _PymlLine, text: str, want_inline: bool) -> _PymlValue:
    open_at: int = text.find("(")
    if open_at < 2 or not text.endswith(")"):
      self._fail(line, "invalid callable invocation")
    name: str = text[:open_at].strip()
    target: _PymlValue = self._symbol(line, name)
    params: list[str] = []
    defaults: list[str] = []
    begin: int = 0
    end: int = 0
    body_indent: int = 0
    closure: dict[str, _PymlValue] = {}
    kind: int = 0
    match target:
      case new.Def(p, d, b, e, ind, captured):
        for item in p:
          params.append(item)
        for item in d:
          defaults.append(item)
        begin = b
        end = e
        body_indent = ind + 2
        closure = captured.copy()
        kind = 1
      case new.Inline(p, d, b, e, ind, captured):
        for item in p:
          params.append(item)
        for item in d:
          defaults.append(item)
        begin = b
        end = e
        body_indent = ind + 2
        closure = captured.copy()
        kind = 2
      case _:
        self._fail(line, "symbol is not callable")
    if (want_inline and kind != 2) or (not want_inline and kind != 1):
      self._fail(line, "invalid callable kind")
    if name in self.call_stack:
      self._fail(line, "recursive callable")
    old_symbols: dict[str, _PymlValue] = self.symbols
    old_returned: bool = self.returned
    old_return: _PymlValue = self.result_value
    old_kind: int = self.run_kind
    args: dict[str, _PymlValue] = self._bind_call(line, params, defaults, text[open_at + 1:-1])
    self.symbols = closure.copy()
    for param in params:
      self.symbols[param] = args[param]
    self.returned = False
    self.result_value = self._literal("null")
    self.run_kind = kind
    self.call_stack.append(name)
    emitted: list[str] = []
    self._run(begin, end, body_indent, emitted)
    self.call_stack.pop()
    result: _PymlValue = new.Null()
    if kind == 1:
      if emitted or not self.returned:
        self._fail(line, "invalid scalar function result")
      result = self.result_value
      match result:
        case new.Sequence(_) | new.Mapping(_) | new.Block(_, _) | new.Def(_, _, _, _, _, _) | new.Inline(_, _, _, _, _, _):
          self._fail(line, "scalar function returned container")
        case _:
          pass
    else:
      if self.returned or not emitted:
        self._fail(line, "invalid inline result")
      normalized: list[str] = []
      for emitted_line in emitted:
        normalized.append(emitted_line[body_indent:])
      first: str = normalized[0].lstrip()
      sequence: bool = first.startswith("- ")
      for emitted_line in normalized:
        is_sequence: bool = emitted_line.lstrip().startswith("- ")
        if len(emitted_line) - len(emitted_line.lstrip()) == 0 and is_sequence != sequence:
          self._fail(line, "mixed inline container")
      result: _PymlValue = new.Block(sequence, normalized)
    self.symbols = old_symbols
    self.returned = old_returned
    self.result_value = old_return
    self.run_kind = old_kind
    return result

  def _binary(self, line: _PymlLine, left_text: str, right_text: str, op: str) -> _PymlValue:
    left: _PymlValue = self._expr(line, left_text)
    right: _PymlValue = self._expr(line, right_text)
    left_raw: str = self._value_text(left)
    right_raw: str = self._value_text(right)
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
    is_string: bool = False
    match left:
      case new.String(_):
        is_string = True
      case _:
        pass
    match right:
      case new.String(_):
        is_string = True
      case _:
        pass
    if is_string:
      if op != "+":
        self._fail(line, "invalid string operator")
      return new.String(_pyml_quote(left_raw[1:-1] + right_raw[1:-1]))
    is_float: bool = False
    match left:
      case new.Float(_):
        is_float = True
      case _:
        pass
    match right:
      case new.Float(_):
        is_float = True
      case _:
        pass
    is_number: bool = False
    match left:
      case new.Integer(_) | new.Float(_):
        match right:
          case new.Integer(_) | new.Float(_):
            is_number = True
          case _:
            pass
      case _:
        pass
    if not is_number:
      self._fail(line, "invalid arithmetic operands")
    if is_float:
      raw: str = ""
      match op:
        case "+":
          raw = str(float(left_raw) + float(right_raw))
        case "-":
          raw = str(float(left_raw) - float(right_raw))
        case "*":
          raw = str(float(left_raw) * float(right_raw))
        case "/":
          raw = str(float(left_raw) / float(right_raw))
        case _:
          raw = str(float(left_raw) % float(right_raw))
      return new.Float(raw)
    raw: str = ""
    match op:
      case "+":
        raw = str(int(left_raw) + int(right_raw))
      case "-":
        raw = str(int(left_raw) - int(right_raw))
      case "*":
        raw = str(int(left_raw) * int(right_raw))
      case "/":
        raw = str(int(left_raw) / int(right_raw))
      case _:
        raw = str(int(left_raw) % int(right_raw))
    return new.Integer(raw)

  def _equal(self, left: _PymlValue, right: _PymlValue) -> bool:
    left_raw: str = self._value_text(left)
    right_raw: str = self._value_text(right)
    match left:
      case new.Integer(_) | new.Float(_):
        match right:
          case new.Integer(_) | new.Float(_):
            return float(left_raw) == float(right_raw)
          case _:
            return False
      case _:
        return left_raw == right_raw

  def _compare(self, line: _PymlLine, left_text: str, right_text: str, op: str) -> _PymlValue:
    left: _PymlValue = self._expr(line, left_text)
    right: _PymlValue = self._expr(line, right_text)
    equal: bool = self._equal(left, right)
    value: bool = False
    match op:
      case "==":
        value = equal
      case "!=":
        value = not equal
      case _:
        left_raw: str = self._value_text(left)
        right_raw: str = self._value_text(right)
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
              value = float(left_raw) < float(right_raw)
            case "<=":
              value = float(left_raw) <= float(right_raw)
            case ">":
              value = float(left_raw) > float(right_raw)
            case _:
              value = float(left_raw) >= float(right_raw)
        else:
          match left:
            case new.String(_):
              match right:
                case new.String(_):
                  match op:
                    case "<":
                      value = left_raw < right_raw
                    case "<=":
                      value = left_raw <= right_raw
                    case ">":
                      value = left_raw > right_raw
                    case _:
                      value = left_raw >= right_raw
                case _:
                  self._fail(line, "invalid comparison operands")
            case _:
              self._fail(line, "invalid comparison operands")
    return new.Boolean("true" if value else "false")

  def _expr(self, line: _PymlLine, text: str) -> _PymlValue:
    expr: str = text.strip()
    if _pyml_outer_parentheses(expr):
      return self._expr(line, expr[1:len(expr) - 1])
    if_marker: int = expr.find(" if ")
    if if_marker >= 0:
      else_marker: int = expr.find(" else ", if_marker + 4)
      if else_marker < 0:
        self._fail(line, "ternary expression requires else")
      condition: _PymlValue = self._expr(line, expr[if_marker + 4:else_marker])
      if self._truth(condition):
        return self._expr(line, expr[:if_marker])
      return self._expr(line, expr[else_marker + 6:])
    or_marker: int = expr.find(" or ")
    if or_marker >= 0:
      left: _PymlValue = self._expr(line, expr[:or_marker])
      if self._truth(left):
        return left
      return self._expr(line, expr[or_marker + 4:])
    and_marker: int = expr.find(" and ")
    if and_marker >= 0:
      left: _PymlValue = self._expr(line, expr[:and_marker])
      if not self._truth(left):
        return left
      return self._expr(line, expr[and_marker + 5:])
    if expr.startswith("not "):
      value: _PymlValue = self._expr(line, expr[4:])
      return new.Boolean("false" if self._truth(value) else "true")
    compare_ops: list[str] = ["==", "!=", "<=", ">=", "<", ">"]
    for compare_op in compare_ops:
      compare_at: int = _pyml_find_operator(expr, compare_op)
      if compare_at >= 0:
        return self._compare(line, expr[:compare_at], expr[compare_at + len(compare_op):], compare_op)
    ops: list[str] = ["+", "-", "*", "/", "%"]
    for op in ops:
      at: int = _pyml_find_operator(expr, op)
      if at >= 0:
        return self._binary(line, expr[:at], expr[at + 1:], op)
    if expr.startswith("len(") and expr.endswith(")"):
      value: _PymlValue = self._expr(line, expr[4:-1])
      match value:
        case new.Sequence(parts):
          return new.Integer(str(len(parts)))
        case new.Mapping(keys, _):
          return new.Integer(str(len(keys)))
        case new.String(raw):
          return new.Integer(str(len(raw) - 2))
        case _:
          self._fail(line, "len expects collection")
    if expr.startswith("$") and expr.endswith("]"):
      bracket: int = expr.rfind("[")
      if bracket > 1:
        target: _PymlValue = self._expr(line, expr[:bracket])
        index: _PymlValue = self._expr(line, expr[bracket + 1:-1])
        key: str = self._value_text(index)
        match index:
          case new.String(raw) if len(raw) >= 2:
            key = raw[1:-1]
          case _:
            pass
        match target:
          case new.Sequence(parts):
            return self._literal(parts[int(key)])
          case new.Mapping(keys, values):
            for i in range(len(keys)):
              map_key: str = keys[i]
              if (map_key.startswith("\"") and map_key.endswith("\"")) or (map_key.startswith("'") and map_key.endswith("'")):
                map_key = map_key[1:-1]
              if map_key == key:
                return self._literal(values[i])
            self._fail(line, "mapping key not found")
          case _:
            self._fail(line, "subscript expects collection")
    if expr.startswith("$") and expr.endswith(")") and "." in expr:
      dot: int = expr.rfind(".")
      receiver: _PymlValue = self._expr(line, expr[:dot])
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
    if expr.startswith("$") and expr.find(" ") < 0 and expr.find("(") < 0:
      return self._symbol(line, expr)
    if expr.startswith("$") and expr.endswith(")") and expr.find("(") >= 2:
      return self._call(line, expr, False)
    if expr.startswith("f\"") and expr.endswith('"'):
      body: str = expr[2:-1]
      out: str = ""
      i: int = 0
      while i < len(body):
        if body[i] == ord("{"):
          end: int = body.find("}", i + 1)
          if end < 0:
            self._fail(line, "unterminated f-string")
          name: str = body[i + 1:end].strip()
          part: _PymlValue = self._expr(line, name)
          raw: str = self._value_text(part)
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
      return new.String(_pyml_quote(out))
    if expr.startswith("range(") and expr.endswith(")"):
      args: list[str] = _pyml_split(expr[6:-1])
      start: int = 0
      stop: int = 0
      step: int = 1
      argc: int = len(args)
      if argc < 1 or argc > 3:
        self._fail(line, "range expects one to three arguments")
      elif argc == 1:
        stop = int(self._value_text(self._expr(line, args[0])))
      else:
        start = int(self._value_text(self._expr(line, args[0])))
        stop = int(self._value_text(self._expr(line, args[1])))
        if argc == 3:
          step = int(self._value_text(self._expr(line, args[2])))
      if not step:
        self._fail(line, "range step cannot be zero")
      parts: list[str] = []
      for i in range(start, stop, step):
        parts.append(str(i))
      return new.Sequence(parts)
    return self._literal(expr)

  def _emit_value(self, value: _PymlValue, indent: int, out: list[str] @ref):
    for raw in self._value_text(value).splitlines():
      out.append(" " * indent + raw)

  def _run_directive_body(self, begin: int, end: int, indent: int, out: list[str] @ref):
    """Run a directive body at its parent indentation and isolate document scope."""
    emitted: list[str] = []
    old_symbols: dict[str, _PymlValue] = self.symbols
    if not self.run_kind:
      self.symbols = old_symbols.copy()
    self._run(begin, end, indent + 2, emitted)
    if not self.run_kind:
      self.symbols = old_symbols
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
      after: int = self._subtree_end(child, indent, end)
      if text.startswith("@from "):
        if self.run_kind or indent:
          self._fail(line, "from import is only allowed at module root")
        if child < after:
          self._fail(line, "from import cannot have body")
        self._import_symbols(line, text)
        i = after
        continue
      if text.startswith("@def ") and text.endswith(":"):
        if self.run_kind:
          self._fail(line, "nested callable declaration")
        name: str = ""
        params: list[str] = []
        defaults: list[str] = []
        (name, params, defaults) = self._signature(line, text[5:-1].strip())
        if name in self.symbols:
          self._fail(line, "duplicate symbol")
        definition: _PymlValue = new.Def(params, defaults, child, after, indent, self.symbols.copy())
        self.symbols[name] = definition
        i = after
        continue
      if text.startswith("@inline ") and text.endswith(":"):
        if self.run_kind:
          self._fail(line, "nested callable declaration")
        name: str = ""
        params: list[str] = []
        defaults: list[str] = []
        (name, params, defaults) = self._signature(line, text[8:-1].strip())
        if name in self.symbols:
          self._fail(line, "duplicate symbol")
        definition: _PymlValue = new.Inline(params, defaults, child, after, indent, self.symbols.copy())
        self.symbols[name] = definition
        i = after
        continue
      if text.startswith("@return "):
        if self.run_kind != 1:
          self._fail(line, "return outside scalar function")
        if child < after:
          self._fail(line, "return cannot have body")
        self.result_value = self._expr(line, text[8:])
        self.returned = True
        return
      if text.startswith("$"):
        colon: int = _pyml_find_colon(text)
        if colon < 0:
          self._fail(line, "invalid variable binding")
        name: str = text[:colon].strip()
        rhs: str = text[colon + 1:len(text)].strip()
        if rhs.startswith("+="):
          current: _PymlValue = self._symbol(line, name)
          self.symbols[name] = self._binary(line, self._value_text(current), rhs[2:], "+")
        elif rhs.startswith("-="):
          current: _PymlValue = self._symbol(line, name)
          self.symbols[name] = self._binary(line, self._value_text(current), rhs[2:], "-")
        elif rhs.startswith("*="):
          current: _PymlValue = self._symbol(line, name)
          self.symbols[name] = self._binary(line, self._value_text(current), rhs[2:], "*")
        elif rhs.startswith("/="):
          current: _PymlValue = self._symbol(line, name)
          self.symbols[name] = self._binary(line, self._value_text(current), rhs[2:], "/")
        elif rhs.startswith("%="):
          current: _PymlValue = self._symbol(line, name)
          self.symbols[name] = self._binary(line, self._value_text(current), rhs[2:], "%")
        elif rhs.startswith("="):
          self.symbols[name] = self._expr(line, rhs[1:])
        elif rhs:
          self.symbols[name] = self._literal(rhs)
        else:
          self.symbols[name] = self._block_literal(child, after, indent)
        i = after
        continue
      if text.startswith("@if ") and text.endswith(":"):
        cond: _PymlValue = self._expr(line, text[4:-1])
        matched: bool = self._truth(cond)
        if matched:
          self._run_directive_body(child, after, indent, out)
        branch: int = after
        while branch < end and self.lines[branch].indent == indent:
          alternate: _PymlLine = self.lines[branch]
          alternate_text: str = alternate.text
          alternate_child: int = branch + 1
          alternate_after: int = self._subtree_end(alternate_child, indent, end)
          if alternate_text.startswith("@elif ") and alternate_text.endswith(":"):
            if not matched:
              alternate_cond: _PymlValue = self._expr(alternate, alternate_text[6:-1])
              if self._truth(alternate_cond):
                self._run_directive_body(alternate_child, alternate_after, indent, out)
                matched = True
            branch = alternate_after
            continue
          if alternate_text == "@else:":
            if not matched:
              self._run_directive_body(alternate_child, alternate_after, indent, out)
              matched = True
            branch = alternate_after
            break
          break
        i = branch
        continue
      if text.startswith("@elif ") or text == "@else:":
        self._fail(line, "orphan conditional branch")
      if text.startswith("@for ") and text.endswith(":"):
        spec: str = text[5:-1].strip()
        marker: int = spec.find(" in ")
        if marker < 0:
          self._fail(line, "invalid for")
        name: str = spec[:marker].strip()
        names: list[str] = _pyml_split(name)
        if not names:
          self._fail(line, "invalid for target")
        for target_name in names:
          if not target_name.startswith("$"):
            self._fail(line, "for target requires $")
        values: _PymlValue = self._expr(line, spec[marker + 4:])
        parts: list[str] = []
        is_sequence: bool = False
        match values:
          case new.Sequence(items):
            for item in items:
              parts.append(item)
            is_sequence = True
          case _:
            self._fail(line, "for expects sequence")
        if not is_sequence:
          self._fail(line, "for expects sequence")
        for raw in parts:
          old_symbols: dict[str, _PymlValue] = self.symbols
          if not self.run_kind:
            self.symbols = old_symbols.copy()
          if len(names) == 1:
            self.symbols[names[0]] = self._literal(raw)
          else:
            tuple_value: _PymlValue = self._literal(raw)
            match tuple_value:
              case new.Sequence(tuple_parts):
                if len(tuple_parts) != len(names):
                  self._fail(line, "for unpacking arity")
                for j in range(len(names)):
                  self.symbols[names[j]] = self._literal(tuple_parts[j])
              case _:
                self._fail(line, "for unpacking expects sequence")
          self._run_directive_body(child, after, indent, out)
          if not self.run_kind:
            self.symbols = old_symbols
        i = after
        continue
      if text.startswith("@expand "):
        if self.run_kind == 1:
          self._fail(line, "scalar function cannot expand container")
        if child < after:
          self._fail(line, "expand cannot have body")
        expand_text: str = text[8:].strip()
        value: _PymlValue = new.Null()
        if expand_text.startswith("$") and expand_text.endswith(")"):
          value = self._call(line, expand_text, True)
        else:
          value = self._expr(line, expand_text)
        block: _PymlValue = self._as_block(line, value)
        expected: int = self._container_kind(begin, end, indent)
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
      colon: int = _pyml_find_colon(text)
      if colon >= 0:
        if self.run_kind == 1:
          self._fail(line, "scalar function cannot emit YAML")
        key: str = text[:colon].strip()
        rhs: str = text[colon + 1:].strip()
        if key.startswith("="):
          key_value: _PymlValue = self._expr(line, key[1:])
          match key_value:
            case new.Integer(_) | new.Float(_) | new.String(_) | new.Boolean(_) | new.Null():
              key = self._value_text(key_value)
            case _:
              self._fail(line, "dynamic key must be scalar")
          if len(key) >= 2 and key[0] == ord('"'):
            key = key[1:-1]
        if rhs.startswith("="):
          rhs = self._value_text(self._expr(line, rhs[1:]))
        out.append(" " * indent + key + ":" + (" " + rhs if rhs else ""))
        if child < after:
          self._run(child, after, indent + 2, out)
        i = after
        continue
      if text.startswith("- "):
        if self.run_kind == 1:
          self._fail(line, "scalar function cannot emit YAML")
        rhs: str = text[2:len(text)].strip()
        if rhs.startswith("="):
          rhs = self._value_text(self._expr(line, rhs[1:]))
        out.append(" " * indent + "- " + rhs)
        if child < after:
          self._run(child, after, indent + 2, out)
        i = after
        continue
      self._fail(line, "unsupported PyML statement")

  def _fold_mapping_updates(self, out: list[str]) -> list[str]:
    """Fold duplicate mapping keys with dict.update last-write-wins semantics."""
    result: list[str] = []
    i: int = 0
    while i < len(out):
      raw: str = out[i]
      indent: int = _pyml_indent(raw)
      text: str = raw[indent:len(raw)]
      at: int = _pyml_find_colon(text)
      if at < 0 or text.startswith("- "):
        result.append(raw)
        i += 1
        continue
      after: int = i + 1
      while after < len(out) and _pyml_indent(out[after]) > indent:
        after += 1
      key: str = text[:at].strip()
      previous: int = -1
      for j in range(len(result) - 1, -1, -1):
        candidate: str = result[j]
        candidate_indent: int = _pyml_indent(candidate)
        if candidate_indent < indent:
          break
        candidate_text: str = candidate[candidate_indent:len(candidate)]
        candidate_at: int = _pyml_find_colon(candidate_text)
        if candidate_indent == indent and candidate_at >= 0 and not candidate_text.startswith("- ") and candidate_text[:candidate_at].strip() == key:
          previous = j
          break
      if previous >= 0:
        remove_end: int = previous + 1
        while remove_end < len(result) and _pyml_indent(result[remove_end]) > indent:
          remove_end += 1
        kept: list[str] = []
        for j in range(len(result)):
          if j < previous or j >= remove_end:
            kept.append(result[j])
        result = kept
      result.append(out[i])
      if i + 1 < after:
        children: list[str] = []
        for j in range(i + 1, after):
          children.append(out[j])
        children = self._fold_mapping_updates(children)
        for child_line in children:
          result.append(child_line)
      i = after
    return result

  def expand(self) -> str:
    out: list[str] = []
    self._run(0, len(self.lines), 0, out)
    out = self._fold_mapping_updates(out)
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
  def load_string[T](fp: StringIO, context: PymlContext = new()) -> T:
    return Self.loads[T](fp.read(), context)
