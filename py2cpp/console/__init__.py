"""``py2cpp.console`` 包根：标准流、argv/exit、终端能力与常用再导出。

设计见 ``docs/console.md``。标准流经 ``io.wrapStd`` 绑定，``owns=False``。
``Console`` / ``Task`` / ``Logger`` 仅从子模块导入，不在此再导出。
"""
from ..builtins import *
from ..io import TextIOWrapper, wrapStd
from ..system.environ import environ
from ..util.list import list
from ffi.crt.stdlib import pyiExit
from ffi.windows.shellapi import pyiCommandLineToArgvW
from ffi.windows import (
  PyiConsoleScreenBufferInfo,
  PyiCpUtf8,
  pyiGetCommandLineW,
  pyiGetConsoleScreenBufferInfo,
  pyiGetStdHandle,
  pyiLocalFree,
  pyiWideCharToMultiByte,
)

_StdOutputHandle: uint = 4294967285


@copyable
class ColorOverride:
  """``-1``=未设置；``0``=禁用；``1``=启用。供颜色探测共用。"""

  value: int = -1


_colorOverride: ColorOverride = new()


def _colorOverrideGet() -> int:
  return _colorOverride.value


def _colorOverrideSet(value: int) -> None:
  _colorOverride.value = value


@immutable
def argv() -> list[str]:
  """返回进程参数，包含 ``argv[0]``。"""
  out: list[str] = []
  argc: int = 0
  wargv: Pointer[Pointer[uint16]] = pyiCommandLineToArgvW(cast[utf16ptr](pyiGetCommandLineW()), id(argc))
  if wargv is None:
    return out
  for i in range(argc):
    n: int = pyiWideCharToMultiByte(PyiCpUtf8, 0, cast[utf16ptr](wargv[i]), -1, None, 0, None, None)
    if n <= 1:
      out.append("")
    else:
      data: byte[:] = new(n)
      outp: utf8ptr = cast(data.view.at())
      pyiWideCharToMultiByte(PyiCpUtf8, 0, cast[utf16ptr](wargv[i]), -1, outp, n, None, None)
      out.append(str.fromSpanUtf8(data.view[:n - 1]))
  h: uintptr = cast(wargv)
  pyiLocalFree(h)
  return out


def exit(code: int = 0) -> None:
  """结束当前进程。"""
  pyiExit(code)


@immutable
def terminalSize() -> (int, int):
  """返回 ``(columns, rows)``；不可用时为 ``(80, 24)``。"""
  info: PyiConsoleScreenBufferInfo = new()
  h: uintptr = pyiGetStdHandle(_StdOutputHandle)
  if h != uintptr(-1) and pyiGetConsoleScreenBufferInfo(h, id(info)):
    cols: int = int(info.srWindow.right - info.srWindow.left + 1)
    rows: int = int(info.srWindow.bottom - info.srWindow.top + 1)
    if cols < 1:
      cols = 80
    if rows < 1:
      rows = 24
    return (cols, rows)
  return (80, 24)


stdin: TextIOWrapper = wrapStd(0)
stdout: TextIOWrapper = wrapStd(1)
stderr: TextIOWrapper = wrapStd(2)


def setColorEnabled(enabled: bool) -> None:
  """显式启用/禁用颜色（优先于环境变量与 TTY 探测）。"""
  if enabled:
    _colorOverrideSet(1)
  else:
    _colorOverrideSet(0)


def supportsColor() -> bool:
  """``setColorEnabled`` → ``NO_COLOR`` → ``FORCE_COLOR`` → ``stdout.isAtty``。

  首版不接受 ``stream`` 参数：``TextIOWrapper`` 不可拷贝，无法安全放进 ``Optional``。
  """
  ov: int = _colorOverrideGet()
  if ov == 0:
    return False
  if ov == 1:
    return True
  if "NO_COLOR" in environ:
    return False
  if "FORCE_COLOR" in environ:
    return True
  return wrapStd(1).isAtty

from .exceptions import (
  ArgumentError,
  ConsoleError,
  RenderError,
  TaskError,
  TaskExitError,
  TaskStartError,
  TaskTimeoutError,
)
from .parse import ArgumentParserMixin, FlagArgMeta, OptArgMeta, PosArgMeta
