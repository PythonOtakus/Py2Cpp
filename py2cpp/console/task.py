"""``console.task``：基于 ``console.popen`` 的命令行同步包装（``docs/console.md`` §6）。"""
from ..builtins import *
from ..io import StringIO
from ..text import str
from ..util.dict import dict
from ..util.list import list
from .exceptions import TaskExitError, TaskStartError
from .popen import CompletedProcess, DevNull, Pipe, Popen, _runShell, _runWithEnv, _shellPopenRead, _shellSystem


class Console:
  """一站式进程 API；``run`` / ``system`` / ``popen`` 均为静态方法。"""

  @overload
  @staticmethod
  def run(
    args: list[str],
    cwd: str = "",
    env: dict[str, str] | None = None,
    captureOutput: bool = False,
    timeout: float64 = float.Inf,
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
    timeout: float64 = float.Inf,
    check: bool = False,
    shell: bool = True,
  ) -> CompletedProcess:
    if not shell:
      raise TaskStartError()
    if captureOutput:
      result: CompletedProcess = _runShell(args, captureOutput=True)
      if check and result.returnCode != 0:
        raise TaskExitError(result.args, result.returnCode, result.stdout, result.stderr)
      return result
    done: CompletedProcess = _runShell(args)
    if check and done.returnCode != 0:
      raise TaskExitError(done.args, done.returnCode, done.stdout, done.stderr)
    return done

  @staticmethod
  def system(command: str) -> int:
    if not command:
      raise TaskStartError()
    return _shellSystem(command)

  @staticmethod
  def popen(command: str, mode: str = "r") -> StringIO:
    if mode != "r":
      raise TaskStartError()
    result: CompletedProcess = _shellPopenRead(command)
    return new(result.stdout)
