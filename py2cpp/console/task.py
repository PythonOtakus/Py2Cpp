"""``console.task``：外部进程、管道与后台命令（``docs/console.md`` §6）。"""
from ..builtins import *
from ..io import StringIO
from ..text import str
from ..util.list import list
from ..util.dict import dict

from .exceptions import TaskExitError, TaskStartError


Pipe: int = -1
DevNull: int = -2


@dataclass(frozen=True)
class CompletedTask:
  args: list[str]
  returnCode: int
  stdout: str
  stderr: str


@native
@uncopyable
class ProcessTask:
  """低层进程对象；参数为 ``list[str]``（不经 shell）。"""

  _state: uintptr = 0

  def __init__(
    self,
    args: list[str],
    cwd: str = "",
    env: dict[str, str] | None = None,
    stdin: int = 0,
    stdout: int = 0,
    stderr: int = 0,
  ):
    ...

  def __del__(self): ...

  def start(self) -> None: ...

  def poll(self) -> int: ...

  def wait(self, timeout: float64 = -1.0) -> int: ...

  def terminate(self) -> None: ...

  def kill(self) -> None: ...

  def communicate(self, input: str = "", timeout: float64 = -1.0) -> CompletedTask: ...

  @property
  @immutable
  def returnCode(self) -> int: ...

  @property
  @immutable
  def pid(self) -> int: ...


@native
@global_call("py_*")
def consoleSystem(command: str) -> int:
  ...


@native
@global_call("py_*")
def consolePopenRead(command: str) -> str:
  ...


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
  ) -> CompletedTask:
    if shell:
      raise TaskStartError()
    outMode: int = Pipe if captureOutput else 0
    errMode: int = Pipe if captureOutput else 0
    e: dict[str, str] = {}
    if env is not None:
      e = env
    task: ProcessTask = new(args, cwd, e, 0, outMode, errMode)
    task.start()
    done: CompletedTask = task.communicate("", timeout)
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
  ) -> CompletedTask:
    if not shell:
      raise TaskStartError()
    empty: list[str] = []
    if captureOutput:
      text: str = consolePopenRead(args)
      result: CompletedTask = new(empty, 0, text, "")
      if check and result.returnCode != 0:
        raise TaskExitError(empty, result.returnCode, text, "")
      return result
    code: int = consoleSystem(args)
    done: CompletedTask = new(empty, code, "", "")
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
