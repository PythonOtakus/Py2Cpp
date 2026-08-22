"""``Console`` 核心实现（标准流 / argv / exit / 终端 / 进程）。"""
from ..builtins import *
from ..core.exceptions import OSError
from ..io import StringIO, TextIO
from ..system.environ import environ
from ..text import str
from ..util.dict import dict
from ..util.list import list
from ffi.crt.stdio import PyiIobuf, pyiAcrtIobFunc, pyiFgets, pyiPclose, pyiPopen
from ffi.crt.stdlib import pyiExit, pyiSystem
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

from .exceptions import TaskExitError, TaskStartError
from .popen import Pipe, Popen, ProcessResult

_StdOutputHandle: uint = 4294967285


@copyable
class ColorOverride:
  """``-1``=未设置；``0``=禁用；``1``=启用。"""

  value: int = -1


_colorOverride: ColorOverride = new()


def _finishProcessResult(result: ProcessResult, check: bool) -> ProcessResult:
  if check and result.returnCode != 0:
    raise TaskExitError(result.args, result.returnCode, result.stdout, result.stderr)
  return result


def _shellReadOutput(command: str) -> (str, int):
  out: str = ""
  with command.useUtf8() as ccommand:
    stream = pyiPopen(ccommand, "r")
    if stream is None:
      raise OSError()
    data: byte[:] = new(4096)
    raw: Pointer[byte] = data.view.at()
    carray: utf8ptr = cast(raw)
    while pyiFgets(carray, len(data), stream) is not None:
      out += str(raw)
    code: int = pyiPclose(stream)
  return (out, code)


class Console:
  """标准流、进程参数、终端能力与一站式外部命令 API。"""

  @staticmethod
  @immutable
  def stdio(fd: int) -> TextIO:
    """绑定标准流：``0``=stdin、``1``=stdout、``2``=stderr；始终 ``owns=False``。"""
    p: Pointer[PyiIobuf] = pyiAcrtIobFunc(uint(fd))
    h: uintptr = cast(p)
    return new(h, False)

  @staticproperty
  @immutable
  def stdin() -> TextIO:
    return Self.stdio(0)

  @staticproperty
  @immutable
  def stdout() -> TextIO:
    return Self.stdio(1)

  @staticproperty
  @immutable
  def stderr() -> TextIO:
    return Self.stdio(2)

  @staticproperty
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

  @staticmethod
  def exit(code: int = 0) -> None:
    """结束当前进程。"""
    pyiExit(code)

  @staticmethod
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

  @staticmethod
  @immutable
  def colorfulFor(isAtty: bool) -> bool:
    """显式覆盖 → 环境变量 → ``isAtty``（供 ``colorful`` 与 ``render`` 按流探测）。"""
    ov: int = _colorOverride.value
    if ov == 0:
      return False
    if ov == 1:
      return True
    if "NO_COLOR" in environ:
      return False
    if "FORCE_COLOR" in environ:
      return True
    return isAtty

  @staticproperty
  def colorful() -> bool:
    """是否启用 ANSI 颜色：赋值显式开/关；读取时再综合环境变量与 ``stdout`` TTY。"""
    return Self.colorfulFor(Self.stdout.isAtty)

  @staticproperty.setter
  def colorful(enabled: bool) -> None:
    if enabled:
      _colorOverride.value = 1
    else:
      _colorOverride.value = 0

  @staticmethod
  def run(
    args: list[str],
    cwd: str = "",
    env: dict[str, str] | None = None,
    captureOutput: bool = False,
    timeout: float64 = float.Inf,
    check: bool = False,
  ) -> ProcessResult:
    outMode: int = Pipe if captureOutput else 0
    errMode: int = Pipe if captureOutput else 0
    actualEnv: dict[str, str] = {}
    if env is not None:
      actualEnv = env
    process: Popen = new(args, cwd, actualEnv, 0, outMode, errMode)
    process.start()
    done: ProcessResult = process.communicate("", timeout)
    return _finishProcessResult(done, check)

  @staticmethod
  def runShell(command: str, captureOutput: bool = False, check: bool = False) -> ProcessResult:
    emptyArgs: list[str] = []
    result: ProcessResult = new(0, "", "")
    if captureOutput:
      out: str = ""
      code: int = 0
      out, code = _shellReadOutput(command)
      result = new(code, out, "")
    else:
      result = new(Self.system(command), "", "")
    result.args = emptyArgs
    return _finishProcessResult(result, check)

  @staticmethod
  def system(command: str) -> int:
    if not command:
      raise TaskStartError()
    with command.useUtf8() as ccommand:
      return pyiSystem(ccommand)

  @staticmethod
  def popen(command: str, mode: str = "r") -> StringIO:
    if mode != "r":
      raise TaskStartError()
    out: str = ""
    _: int = 0
    out, _ = _shellReadOutput(command)
    return new(out)
