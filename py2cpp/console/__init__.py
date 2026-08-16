"""``py2cpp.console`` 包根：标准流、argv/exit、终端能力与常用再导出。

设计见 ``docs/console.md``。标准流经 ``io.wrapStd`` 绑定，``owns=False``。
``Console`` / ``Task`` / ``Logger`` 仅从子模块导入，不在此再导出。
"""
from ..builtins import *
from ..io import TextIOWrapper, wrapStd
from ..system.environ import environ
from ..util.list import list

from .exceptions import (
  ArgumentError,
  ConsoleError,
  RenderError,
  TaskError,
  TaskExitError,
  TaskStartError,
  TaskTimeoutError,
)
from .native_sys import (
  colorOverrideGet,
  colorOverrideSet,
  nativeArgv,
  nativeExit,
  nativeTerminalSize,
)
from .parse import ArgumentParserMixin, FlagArgMeta, OptArgMeta, PosArgMeta
from .render import Progress

stdin: TextIOWrapper = wrapStd(0)
stdout: TextIOWrapper = wrapStd(1)
stderr: TextIOWrapper = wrapStd(2)

argv: list[str] = nativeArgv()


def exit(code: int = 0) -> None:
  """结束进程（转发 ``nativeExit``）。"""
  nativeExit(code)


def terminalSize() -> (int, int):
  """``(columns, rows)``；不可用时 ``(80, 24)``。"""
  return nativeTerminalSize()


def setColorEnabled(enabled: bool) -> None:
  """显式启用/禁用颜色（优先于环境变量与 TTY 探测）。"""
  if enabled:
    colorOverrideSet(1)
  else:
    colorOverrideSet(0)


def supportsColor() -> bool:
  """``setColorEnabled`` → ``NO_COLOR`` → ``FORCE_COLOR`` → ``stdout.isAtty``。

  首版不接受 ``stream`` 参数：``TextIOWrapper`` 不可拷贝，无法安全放进 ``Optional``。
  """
  ov: int = colorOverrideGet()
  if ov == 0:
    return False
  if ov == 1:
    return True
  if "NO_COLOR" in environ:
    return False
  if "FORCE_COLOR" in environ:
    return True
  return wrapStd(1).isAtty
