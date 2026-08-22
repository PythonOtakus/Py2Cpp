"""``py2cpp.console`` 异常层级（见 ``docs/console.md`` §7）。"""
from ..builtins import *
from ..text import str
from ..util.list import list


class ConsoleError(Exception):
  pass


class ArgumentError(ConsoleError):
  pass


class RenderError(ConsoleError):
  pass


class TaskError(ConsoleError):
  pass


class TaskStartError(TaskError):
  pass


class TaskTimeoutError(TaskError):
  pass


@dataclass
class TaskExitError(TaskError):
  """``check=True`` 且退出码非零；字段与 ``ProcessResult`` 对齐（避免 ``console`` 循环导入）。"""

  args: list[str]
  returnCode: int = 0
  stdout: str = ""
  stderr: str = ""
