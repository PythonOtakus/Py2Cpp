"""进程 argv / exit / 终端尺寸（native 叶子；供 ``console`` 包根与 ``parse`` 使用）。"""
from ..builtins import *
from ..util.list import list
from ffi.crt.stdlib import pyiExit
from ffi.windows.shellapi import pyiCommandLineToArgvW
from ffi.windows.windows import (
  PyiConsoleScreenBufferInfo,
  PyiCpUtf8,
  pyiGetCommandLineW,
  pyiGetConsoleScreenBufferInfo,
  pyiGetStdHandle,
  pyiLocalFree,
  pyiWideCharToMultiByte,
)

@copyable
class ColorOverride:
  """``-1``=未设置；``0``=禁用；``1``=启用。供 ``supportsColor`` / ``paint`` 共用。"""

  value: int = -1


_colorOverride: ColorOverride = new()


def colorOverrideGet() -> int:
  """读取颜色覆盖（``-1``/``0``/``1``）。"""
  return _colorOverride.value


def colorOverrideSet(value: int) -> None:
  """写入颜色覆盖。"""
  _colorOverride.value = value


@native
@global_call("py_*")
def nativeArgv() -> list[str]:
  """进程参数（含 ``argv[0]``）。"""
  ...


def nativeExit(code: int = 0) -> None:
  """结束进程。"""
  pyiExit(code)


@native
@global_call("py_*")
def nativeTerminalSize() -> (int, int):
  """``(columns, rows)``；不可用时 ``(80, 24)``。"""
  ...
