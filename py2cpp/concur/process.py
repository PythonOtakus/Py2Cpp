"""外部子进程生命周期（Python ``subprocess.Popen`` 的受限子集）。

``Process`` 只启动明确的 ``list[str]`` 参数，不隐式经过 shell。``ProcessPool``
并发调度外部命令；跨进程执行 py2cpp callable 和 worker IPC 不在本模块范围内。
"""
from ..builtins import *
from ..core.exceptions import OSError, RuntimeError, ValueError
from ..util.dict import dict
from ..util.list import list
from ..util.memory import strCbuf
from .thread import Future, ThreadPool
from ffi.windows import (
  PyiErrorAlreadyExists,
  PyiInfinite,
  PyiWaitTimeout,
  pyiCloseHandle,
  pyiCreateEventA,
  pyiCreateMutexA,
  pyiCreateSemaphoreA,
  pyiGetLastError,
  pyiReleaseMutex,
  pyiReleaseSemaphore,
  pyiResetEvent,
  pyiSetEvent,
  pyiWaitForSingleObject,
)

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

_WaitObject0: uint = 0
_WaitAbandoned: uint = 128


@immutable
def _processSyncName(name: str) -> byte[:]:
  if not name:
    raise ValueError("process synchronization name must not be empty")
  return strCbuf(name, len(name) + 1)


@immutable
def _processWait(handle: uintptr, timeout: float64) -> bool:
  if timeout < -1.0:
    raise ValueError("timeout value must be non-negative")
  millis: uint = PyiInfinite
  if timeout >= 0.0:
    millis = uint(timeout * 1000.0)
  result: uint = pyiWaitForSingleObject(handle, millis)
  if result in {_WaitObject0, _WaitAbandoned}:
    return True
  if result == PyiWaitTimeout:
    return False
  raise OSError()


@uncopyable
class ProcessEvent:
  """Windows 命名事件：可由独立进程按同一 ``name`` 共享。"""

  _handle: uintptr = 0
  name: str = ""
  created: bool = False

  def __init__(self, name: str, initial: bool = False):
    buf: byte[:] = _processSyncName(name)
    handle: uintptr = pyiCreateEventA(None, 1, int(initial), buf.view.at(0))
    if handle == 0:
      raise OSError()
    self._handle = handle
    self.name = name
    self.created = pyiGetLastError() != PyiErrorAlreadyExists

  def __del__(self):
    if self._handle != 0:
      pyiCloseHandle(self._handle)
      self._handle = 0

  @immutable
  def isSet(self) -> bool:
    return _processWait(self._handle, 0.0)

  def set(self) -> None:
    if pyiSetEvent(self._handle) == 0:
      raise OSError()

  def clear(self) -> None:
    if pyiResetEvent(self._handle) == 0:
      raise OSError()

  def wait(self, timeout: float64 = -1.0) -> bool:
    return _processWait(self._handle, timeout)


@uncopyable
class ProcessMutex:
  """Windows 命名递归 mutex：同一 ``name`` 可跨进程互斥。"""

  _handle: uintptr = 0
  name: str = ""
  created: bool = False

  def __init__(self, name: str):
    buf: byte[:] = _processSyncName(name)
    handle: uintptr = pyiCreateMutexA(None, 0, buf.view.at(0))
    if handle == 0:
      raise OSError()
    self._handle = handle
    self.name = name
    self.created = pyiGetLastError() != PyiErrorAlreadyExists

  def __del__(self):
    if self._handle != 0:
      pyiCloseHandle(self._handle)
      self._handle = 0

  def acquire(self, blocking: bool = True, timeout: float64 = -1.0) -> bool:
    if not blocking and timeout >= 0.0:
      raise ValueError("can't specify timeout for non-blocking acquire")
    if not blocking:
      return _processWait(self._handle, 0.0)
    return _processWait(self._handle, timeout)

  def release(self) -> None:
    if pyiReleaseMutex(self._handle) == 0:
      raise RuntimeError("cannot release an un-acquired ProcessMutex")

  def __enter__(self) -> Self:
    self.acquire()
    return self

  def __exit__(self):
    self.release()


@uncopyable
class ProcessSemaphore:
  """Windows 命名信号量：许可计数由同一名称的所有进程共享。"""

  _handle: uintptr = 0
  name: str = ""
  created: bool = False

  def __init__(self, name: str, value: int = 1, maximum: int = 2147483647):
    if value < 0 or maximum <= 0 or value > maximum:
      raise ValueError("invalid process semaphore value or maximum")
    buf: byte[:] = _processSyncName(name)
    handle: uintptr = pyiCreateSemaphoreA(None, value, maximum, buf.view.at(0))
    if handle == 0:
      raise OSError()
    self._handle = handle
    self.name = name
    self.created = pyiGetLastError() != PyiErrorAlreadyExists

  def __del__(self):
    if self._handle != 0:
      pyiCloseHandle(self._handle)
      self._handle = 0

  def acquire(self, blocking: bool = True, timeout: float64 = -1.0) -> bool:
    if not blocking and timeout >= 0.0:
      raise ValueError("can't specify timeout for non-blocking acquire")
    if not blocking:
      return _processWait(self._handle, 0.0)
    return _processWait(self._handle, timeout)

  def release(self, n: int = 1) -> None:
    if n < 1:
      raise ValueError("n must be one or more")
    if pyiReleaseSemaphore(self._handle, n, None) == 0:
      raise ValueError("ProcessSemaphore released too many times")

  def __enter__(self) -> Self:
    self.acquire()
    return self

  def __exit__(self):
    self.release()
