"""``console.task``：基于 ``concur.process`` 的命令行同步包装（``docs/console.md`` §6）。"""
from ..builtins import *
from ..concur.process import CompletedProcess, DevNull, Pipe, _runWithEnv
from ..io import StringIO
from ..text import str
from ..util.dict import dict
from ..util.list import list
from ..util.memory import strCbuf
from ffi.crt.stdio import pyiFgets, pyiPclose, pyiPopen
from ffi.crt.stdlib import pyiSystem

from .exceptions import TaskExitError, TaskStartError
def consoleSystem(command: str) -> int:
  commandBuf: byte[:] = strCbuf(command, len(command) + 1)
  ccommand: CStr = cast(commandBuf.view.at())
  return pyiSystem(ccommand)


def consolePopenRead(command: str) -> str:
  commandBuf: byte[:] = strCbuf(command, len(command) + 1)
  ccommand: CStr = cast(commandBuf.view.at())
  stream = pyiPopen(ccommand, "r")
  if stream is None:
    raise OSError()
  out: str = ""
  buf: byte[:] = new(4096)
  raw: Pointer[byte] = buf.view.at()
  cbuf: CStr = cast(raw)
  while pyiFgets(cbuf, len(buf), stream) is not None:
    out += str(raw)
  pyiPclose(stream)
  return out


class Console:
  """一站式进程 API；``run`` / ``system`` / ``popen`` 均为静态方法。"""

  @overload
  @staticmethod
  def run(
    args: list[str],
    cwd: str = "",
    env: dict[str, str] | None = None,
    captureOutput: bool = False,
    timeout: float64 = -1.0,
    check: bool = False,
    shell: bool = False,
  ) -> CompletedProcess:
    if shell:
      raise TaskStartError()
    outMode: int = Pipe if captureOutput else 0
    errMode: int = Pipe if captureOutput else 0
    actualEnv: dict[str, str] = {}
    if env is not None:
      actualEnv = env
    done: CompletedProcess = _runWithEnv(args, cwd, actualEnv, 0, outMode, errMode, "", timeout)
    if check and done.returnCode != 0:
      raise TaskExitError(done.args, done.returnCode, done.stdout, done.stderr)
    return done

  @overload
  @staticmethod
  def run(
    args: str,
    cwd: str = "",
    env: dict[str, str] | None = None,
    captureOutput: bool = False,
    timeout: float64 = -1.0,
    check: bool = False,
    shell: bool = True,
  ) -> CompletedProcess:
    if not shell:
      raise TaskStartError()
    empty: list[str] = []
    if captureOutput:
      text: str = consolePopenRead(args)
      result: CompletedProcess = new(empty, 0, text, "")
      if check and result.returnCode != 0:
        raise TaskExitError(empty, result.returnCode, text, "")
      return result
    code: int = consoleSystem(args)
    done: CompletedProcess = new(empty, code, "", "")
    if check and code != 0:
      raise TaskExitError(empty, code, "", "")
    return done

  @staticmethod
  def system(command: str) -> int:
    if not command:
      raise TaskStartError()
    return consoleSystem(command)

  @staticmethod
  def popen(command: str, mode: str = "r") -> StringIO:
    if mode != "r":
      raise TaskStartError()
    text: str = consolePopenRead(command)
    return new(text)
