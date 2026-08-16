"""``console.parse``：dataclass + ``*ArgMeta`` 声明式 CLI（见 ``docs/console.md`` §4）。

``ArgumentParserMixin.parse[T]()`` 由译期 pass 展开为 ``T.parse(...)``；带 ``*ArgMeta`` 的
``@dataclass`` 会注入 ``parse`` 静态方法，并混入本 mixin（``helpText`` 等）。首版不含子命令。
"""
from ..builtins import *
from ..io import TextIOWrapper, wrapStd
from ..util.list import list

from .native_sys import nativeArgv, nativeExit


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
  """供 mixin / 注入 ``parse`` 调用的 IO 叶子；类名全局可解析，避免宿主模块看不到 ``nativeExit``。"""

  @staticmethod
  def resolveArgv(argv: list[str] | None = None) -> list[str]:
    if argv is None:
      full: list[str] = nativeArgv()
      if len(full) <= 1:
        empty: list[str] = []
        return empty
      return full[1:]
    return argv

  @staticmethod
  def fail(msg: str, usage: str) -> None:
    err: TextIOWrapper = wrapStd(2)
    err.write("error: ")
    err.write(msg)
    err.write("\n")
    err.write(usage)
    err.write("\n")
    err.flush()
    nativeExit(2)

  @staticmethod
  def showHelp(usage: str) -> None:
    err: TextIOWrapper = wrapStd(2)
    err.write(usage)
    err.write("\n")
    err.flush()
    nativeExit(0)


@mixin
class ArgumentParserMixin:
  """参数 dataclass 的混入基类；带 Meta 的宿主由 pass 注入 ``parse``。

  调用方使用 ``ArgumentParserMixin.parse[BuildArgs]()``（译期改写为 ``BuildArgs.parse()``）。
  ``helpText`` 用 ``Self.iterFields`` + ``getFieldAnnotation`` 展开。
  """

  @staticmethod
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
  def parse(argv: list[str] = None) -> Self:
    """由 ``expand_argument_parser`` 在带 Meta 的 dataclass 上生成实现；此处为占位。"""
    raise NotImplementedError
