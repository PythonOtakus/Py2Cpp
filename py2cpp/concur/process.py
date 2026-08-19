"""外部子进程生命周期（Python ``subprocess.Popen`` 的受限子集）。

``Process`` 只启动明确的 ``list[str]`` 参数，不隐式经过 shell。``ProcessPool``
并发调度外部命令；跨进程执行 py2cpp callable 和 worker IPC 不在本模块范围内。
"""
from ..builtins import *
from ..util.dict import dict
from ..util.list import list
from .thread import Future, ThreadPool


Pipe: int = -1
DevNull: int = -2


@copyable
class CompletedProcess:
  """已结束子进程的参数、退出码和已捕获输出。"""

  args: list[str] = []
  returnCode: int = 0
  stdout: str = ""
  stderr: str = ""

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
class Process:
  """外部子进程句柄。

  ``args`` 不经 shell 解析；``stdout`` / ``stderr`` 可使用 ``Pipe`` 或 ``DevNull``。
  进程实例不可复制，必须由创建者显式 ``wait``、``communicate`` 或终止。
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

  def wait(self, timeout: float64 = -1.0) -> int:
    """等待退出并返回退出码；超时抛 ``RuntimeError``。"""
    ...

  def terminate(self) -> None: ...

  def kill(self) -> None: ...

  def communicate(self, input: str = "", timeout: float64 = -1.0) -> CompletedProcess: ...

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
  process: Process = new(args, cwd, env, stdin, stdout, stderr)
  process.start()
  return process.communicate(input, timeout)

@uncopyable
class ProcessPool:
  """受限并发的外部命令池。

  pool worker 仅调度，实际工作仍由独立 OS 子进程完成。任务参数为明确的
  ``list[str]``，不支持将 py2cpp callable 序列化到子进程。
  """

  _pool: ThreadPool[CompletedProcess]

  def __init__(self, maxWorkers: int = 4):
    if maxWorkers <= 0:
      raise ValueError("maxWorkers must be positive")
    self._pool = new(maxWorkers, "ProcessPool")

  def submit(
    self,
    args: list[str],
    cwd: str = "",
    env: dict[str, str] | None = None,
    stdin: int = 0,
    stdout: int = -1,
    stderr: int = -1,
    input: str = "",
    timeout: float64 = -1.0,
  ) -> Future[CompletedProcess]:
    """提交一个外部命令；默认捕获 stdout/stderr。"""
    actualEnv: dict[str, str] = {}
    if env is not None:
      actualEnv = env
    return self._pool.submit(
      lambda: _runWithEnv(args, cwd, actualEnv, stdin, stdout, stderr, input, timeout),
    )

  def map(
    self,
    commands: list[list[str]],
    timeout: float64 = -1.0,
  ) -> list[CompletedProcess]:
    """并发运行命令并按输入顺序返回结果。"""
    futures: list[Future[CompletedProcess]] = []
    for i in range(len(commands)):
      futures.append(self.submit(commands[i], timeout=timeout))
    out: list[CompletedProcess] = []
    for i in range(len(futures)):
      out.append(futures[i].result(timeout=-1.0))
    return out

  def shutdown(self, wait: bool = True, cancelFutures: bool = False) -> None:
    """停止接受新任务，并可选等待已提交任务完成。"""
    self._pool.shutdown(wait, cancelFutures)
  def __enter__(self) -> Self:
    return self

  def __exit__(self):
    self.shutdown()