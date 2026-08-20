"""``console.parse``：dataclass + ``*ArgMeta`` 声明式 CLI（见 ``docs/console.md`` §4）。

宿主须继承 ``ArgumentParserMixin`` 并标 ``@dataclass``。调用 ``new.parse()`` /
``new.parse(argv)``（赋值处 S06，语义即 ``BuildArgs.parse``）。``parse`` 与
``@staticproperty helpText`` 用 ``Self.iterFields`` / ``getFieldAnnotation`` /
``getFieldType`` / ``getFieldDefault`` 译期展开。首版不含子命令。
"""
from ..builtins import *
from ..io import TextIOWrapper, wrapStd
from ..util.list import list

from . import argv, exit


@annotation
@dataclass
class PosArgMeta:
  """位置参数；字段按声明顺序消费；首版无默认值。"""

  help: str = ""


@annotation
@dataclass
class OptArgMeta:
  """长选项 ``--field-name``；可选 ``short="-x"``；须有默认值或 ``@optional``。"""

  short: str = ""
  help: str = ""
  choices: list[str] @optional = []


@annotation
@dataclass
class FlagArgMeta:
  """布尔 flag；默认 ``False`` → ``--field-name``；``negated=True`` 且默认 ``True`` → ``--no-field-name``。"""

  short: str = ""
  help: str = ""
  negated: bool = False


@copyable
class ArgParserIO:
  """供 mixin ``parse`` 调用的 IO 叶子；类名全局可解析，避免宿主模块看不到 ``exit``。"""

  @staticmethod
  def resolveArgv(args: list[str] | None = None) -> list[str]:
    if args is None:
      full: list[str] = argv()
      if len(full) <= 1:
        empty: list[str] = []
        return empty
      return full[1:]
    return args

  @staticmethod
  def fail(msg: str, usage: str) -> None:
    err: TextIOWrapper = wrapStd(2)
    err.write("error: ")
    err.write(msg)
    err.write("\n")
    err.write(usage)
    err.write("\n")
    err.flush()
    exit(2)

  @staticmethod
  def showHelp(usage: str) -> None:
    err: TextIOWrapper = wrapStd(2)
    err.write(usage)
    err.write("\n")
    err.flush()
    exit(0)


@mixin
class ArgumentParserMixin:
  """参数 dataclass 的混入基类；``parse`` / ``helpText`` 由字段 ``*ArgMeta`` 译期展开。"""

  @staticproperty
  @immutable
  def helpText() -> str:
    usage: str = "usage: " + Self.__name__
    for field in Self.iterFields():
      pos = Self.getFieldAnnotation[PosArgMeta](field)
      opt = Self.getFieldAnnotation[OptArgMeta](field)
      flag = Self.getFieldAnnotation[FlagArgMeta](field)
      kebab: str = field.replace("_", "-")
      if pos is not None:
        usage += " <" + field + ">"
      elif opt is not None:
        usage += " [--" + kebab + " VALUE]"
      elif flag is not None:
        if flag.negated:
          usage += " [--no-" + kebab + "]"
        else:
          usage += " [--" + kebab + "]"
    return usage

  @staticmethod
  def _initResult() -> Self:
    vs: VarStack = new()
    for field in Self.iterFields():
      if Self.getFieldDefault(field) is not None:
        vs.push(Self.getFieldDefault(field))
      elif Self.getFieldType(field) is int:
        vs.push(0)
      elif Self.getFieldType(field) is int64:
        vs.push(0)
      elif Self.getFieldType(field) is bool:
        vs.push(False)
      elif Self.getFieldType(field) is float:
        vs.push(0.0)
      elif Self.getFieldType(field) is float64:
        vs.push(0.0)
      else:
        vs.push("")
    return new(*vs)

  @staticmethod
  def _countPos() -> int:
    n: int = 0
    for field in Self.iterFields():
      pos = Self.getFieldAnnotation[PosArgMeta](field)
      if pos is not None:
        n += 1
    return n

  @staticmethod
  def _setFlag(result: Self, key: str) -> bool:
    for field in Self.iterFields():
      flag = Self.getFieldAnnotation[FlagArgMeta](field)
      if flag is not None:
        kebab: str = field.replace("_", "-")
        longTok: str = "--" + kebab
        if flag.negated:
          longTok = "--no-" + kebab
        if key == longTok:
          setattr(result, field, not flag.negated)
          return True
        if flag.short != "":
          if key == flag.short:
            setattr(result, field, not flag.negated)
            return True
    return False

  @staticmethod
  def _setOpt(
    result: Self,
    key: str,
    raw: str,
    hasRaw: bool,
    fromEq: bool,
    usage: str,
  ) -> int:
    for field in Self.iterFields():
      opt = Self.getFieldAnnotation[OptArgMeta](field)
      if opt is not None:
        kebab: str = field.replace("_", "-")
        matched: bool = key == "--" + kebab
        if opt.short != "":
          if key == opt.short:
            matched = True
        if matched:
          if not hasRaw:
            ArgParserIO.fail("missing value for --" + kebab, usage)
          if opt.choices:
            if raw not in opt.choices:
              ArgParserIO.fail("invalid choice for --" + kebab + ": " + raw, usage)
          if Self.getFieldType(field) is int:
            setattr(result, field, int(raw))
          elif Self.getFieldType(field) is int64:
            setattr(result, field, int(raw))
          elif Self.getFieldType(field) is float:
            setattr(result, field, float(raw))
          elif Self.getFieldType(field) is float64:
            setattr(result, field, float(raw))
          else:
            setattr(result, field, raw)
          if fromEq:
            return 2
          return 1
    return 0

  @staticmethod
  def _setComboChar(result: Self, ch: str) -> bool:
    for field in Self.iterFields():
      flag = Self.getFieldAnnotation[FlagArgMeta](field)
      if flag is not None:
        if flag.short != "":
          want: str = flag.short[1:]
          if ch == want:
            setattr(result, field, not flag.negated)
            return True
    return False

  @staticmethod
  def _takePos(result: Self, tok: str, posI: int) -> int:
    posCur: int = 0
    newI: int = posI
    used: bool = False
    for field in Self.iterFields():
      pos = Self.getFieldAnnotation[PosArgMeta](field)
      if pos is not None:
        if posI == posCur:
          if Self.getFieldType(field) is int:
            setattr(result, field, int(tok))
          elif Self.getFieldType(field) is int64:
            setattr(result, field, int(tok))
          elif Self.getFieldType(field) is float:
            setattr(result, field, float(tok))
          elif Self.getFieldType(field) is float64:
            setattr(result, field, float(tok))
          else:
            setattr(result, field, tok)
          used = True
          newI = posI + 1
        posCur += 1
    if used:
      return newI
    return -1

  @staticmethod
  def parse(argv: list[str] | None = None) -> Self:
    result: Self = new._initResult()
    args: list[str] = ArgParserIO.resolveArgv(argv)
    usage: str = Self.helpText
    n: int = len(args)
    posN: int = Self._countPos()
    posI: int = 0
    optsDone: bool = False
    skipNext: bool = False
    for i in range(n):
      if skipNext:
        skipNext = False
        continue
      tok: str = args[i]
      if (not optsDone) and tok == "--":
        optsDone = True
        continue
      if (not optsDone) and tok in {"--help", "-h"}:
        ArgParserIO.showHelp(usage)
      if (not optsDone) and tok.startsWith("-") and tok != "-":
        key: str = tok
        raw: str = ""
        hasRaw: bool = False
        fromEq: bool = False
        before, sep, after = tok.partition("=")
        if sep == "=":
          key = before
          raw = after
          hasRaw = True
          fromEq = True
        elif (i + 1) < n:
          nxt: str = args[i + 1]
          takeVal: bool = (not nxt.startsWith("-")) or nxt == "-"
          if (not takeVal) and len(nxt) >= 2:
            dch: str = nxt[1:2]
            if "0" <= dch <= "9":
              takeVal = True
          if takeVal:
            raw = nxt
            hasRaw = True
        if Self._setFlag(result, key):
          continue
        optSt: int = Self._setOpt(result, key, raw, hasRaw, fromEq, usage)
        if optSt != 0:
          if optSt == 1:
            skipNext = True
          continue
        if (not tok.startsWith("--")) and len(tok) > 2 and (not fromEq):
          comboOk: bool = True
          for k in range(1, len(tok)):
            ch: str = tok[k:k + 1]
            if not Self._setComboChar(result, ch):
              comboOk = False
          if comboOk:
            continue
        ArgParserIO.fail("unknown option " + tok, usage)
      taken: int = Self._takePos(result, tok, posI)
      if taken < 0:
        ArgParserIO.fail("unexpected positional " + tok, usage)
      posI = taken
    if posI < posN:
      ArgParserIO.fail("missing positional argument", usage)
    return result
