"""外部子进程（Python ``subprocess.Popen`` 受限子集）。

``Popen`` 只启动明确的 ``list[str]`` 参数，不隐式经过 shell。
"""
from ..builtins import *
from ..core.exceptions import OSError, RuntimeError, ValueError
from ..util.dict import dict
from ..util.list import list
from ffi.crt.stdio import pyiFgets, pyiPclose, pyiPopen
from ffi.crt.stdlib import pyiSystem

Pipe: int = -1
DevNull: int = -2


@copyable
class CompletedProcess:
  """已结束子进程的参数、退出码和已捕获输出。"""

  args: list[str]
  returnCode: int
  stdout: str
  stderr: str

  @overload
  def __init__(self):
    self.args = []
    self.returnCode = 0
    self.stdout = ""
    self.stderr = ""

  @overload
  def __init__(self, args: list[str], returnCode: int, stdout: str, stderr: str):
    self.args = args
    self.returnCode = returnCode
    self.stdout = stdout
    self.stderr = stderr


@native
@uncopyable
class Popen:
  """外部子进程句柄（对齐 ``subprocess.Popen`` 子集）。

  ``args`` 不经 shell 解析；``stdout`` / ``stderr`` 可使用 ``Pipe`` 或 ``DevNull``。
  """

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

  def poll(self) -> int:
    """返回退出码；尚未结束或未启动时返回 ``-1``。"""
    ...

  def wait(self, timeout: float64 = float.Inf) -> int:
    """等待退出并返回退出码；超时抛 ``RuntimeError``。"""
    ...

  def terminate(self) -> None: ...

  def kill(self) -> None: ...

  def communicate(self, input: str = "", timeout: float64 = float.Inf) -> CompletedProcess: ...

  @property
  @immutable
  def returnCode(self) -> int:
    """已结束时的退出码，否则为 ``-1``。"""
    ...

  @property
  @immutable
  def pid(self) -> int:
    """已启动进程的 ID，否则为 ``-1``。"""
    ...

  @property
  @immutable
  def running(self) -> bool:
    """进程是否已启动且尚未退出。"""
    ...

  def __enter__(self) -> Self: ...

  def __exit__(self): ...


@overload
def run(args: list[str]) -> CompletedProcess:
  """同步运行一个命令，并默认捕获 stdout/stderr。"""
  env: dict[str, str] = {}
  return _runWithEnv(args, "", env, 0, -1, -1, "", -1.0)


def _runWithEnv(
  args: list[str],
  cwd: str,
  env: dict[str, str],
  stdin: int,
  stdout: int,
  stderr: int,
  input: str,
  timeout: float64,
) -> CompletedProcess:
  """同步运行一个外部命令并返回已收集结果。"""
  process: Popen = new(args, cwd, env, stdin, stdout, stderr)
  process.start()
  return process.communicate(input, timeout)


def _shellSystem(command: str) -> int:
  """通过系统 shell 运行命令并返回退出码。"""
  with command.useUtf8() as ccommand:
    return pyiSystem(ccommand)


def _shellPopenRead(command: str) -> CompletedProcess:
  """通过系统 shell 运行命令，读取 stdout，并保留真实退出码。"""
  out: str = ""
  code: int = 0
  with command.useUtf8() as ccommand:
    stream = pyiPopen(ccommand, "r")
    if stream is None:
      raise OSError()
    data: byte[:] = new(4096)
    raw: Pointer[byte] = data.view.at()
    carray: utf8ptr = cast(raw)
    while pyiFgets(carray, len(data), stream) is not None:
      out += str(raw)
    code = pyiPclose(stream)
  args: list[str] = []
  return new(args, code, out, "")


def _runShell(command: str, captureOutput: bool = False) -> CompletedProcess:
  """运行显式 shell 命令；仅供上层兼容 API 复用。"""
  if captureOutput:
    return _shellPopenRead(command)
  args: list[str] = []
  return new(args, _shellSystem(command), "", "")
