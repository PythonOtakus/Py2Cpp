"""进程 argv / exit / 终端尺寸（``ffi`` 组合；供 ``console`` 包根与 ``parse`` 使用）。"""
from ..builtins import *
from ..util.list import list
from ffi.crt.stdlib import pyiExit, pyiFree, pyiMalloc
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

_StdOutputHandle: uint = 4294967285

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


@immutable
def nativeArgv() -> list[str]:
  """进程参数（含 ``argv[0]``）。"""
  out: list[str] = []
  argc: int = 0
  wargv: Pointer[Pointer[uint]] = pyiCommandLineToArgvW(pyiGetCommandLineW(), id(argc))
  if wargv is None:
    return out
  for i in range(argc):
    n: int = pyiWideCharToMultiByte(PyiCpUtf8, 0, wargv[i], -1, None, 0, None, None)
    if n <= 1:
      out.append("")
    else:
      buf: uintptr = pyiMalloc(n)
      if buf == 0:
        out.append("")
      else:
        p: Pointer[byte] = cast(buf)
        pyiWideCharToMultiByte(PyiCpUtf8, 0, wargv[i], -1, p, n, None, None)
        out.append(str(p))
        pyiFree(buf)
  h: uintptr = cast(wargv)
  pyiLocalFree(h)
  return out


def nativeExit(code: int = 0) -> None:
  """结束进程。"""
  pyiExit(code)


@immutable
def nativeTerminalSize() -> (int, int):
  """``(columns, rows)``；不可用时 ``(80, 24)``。"""
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
