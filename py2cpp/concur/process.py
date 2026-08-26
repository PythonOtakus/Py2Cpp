"""子进程（Python ``multiprocessing.Process`` / ``ProcessPoolExecutor`` 受限子集）。

``Process`` 运行零参数 ``Callable[[], None]``（与 ``Thread`` 同构）。
POSIX 用 ``fork``；Windows 用同映像 ``CreateProcess`` + 函数 RVA（仅无捕获自由函数）。
跨进程同步见 ``ProcessEvent`` / ``SharedMemory`` / ``ProcessChannel``。
外部命令见 ``py2cpp.console.popen``。
"""
from ..builtins import *
from ..core.exceptions import OSError, RuntimeError, ValueError
from ..text import str
from ..util.span import span
from .thread import (
  EmptyError,
  Future,
  Lock,
  Queue,
  ShutDownError,
  Thread,
  TimeoutError,
  atomic,
)
from ffi.windows import (
  PyiErrorAlreadyExists,
  PyiFileMapWrite,
  PyiInfinite,
  PyiPageReadwrite,
  PyiWaitTimeout,
  pyiCloseHandle,
  pyiCreateFileMappingA,
  pyiCreateEventA,
  pyiCreateMutexA,
  pyiCreateSemaphoreA,
  pyiGetLastError,
  pyiMapViewOfFile,
  pyiReleaseMutex,
  pyiReleaseSemaphore,
  pyiResetEvent,
  pyiSetEvent,
  pyiUnmapViewOfFile,
  pyiWaitForSingleObject,
)


@enum
class _ProcessPhaseEnum:
  Initial = 0
  Started = 1
  Stopped = 2


@native
def tryWorker(argc: int, argv: uintptr) -> int:
  """识别 ``--py2cpp-process-exec=`` 时在子进程执行目标并返回退出码；否则返回 ``-1``。"""
  ...


@native
def _processInvoke[Value](fn: Callable[[], Value]) -> Value:
  """在独立子进程中调用 ``fn`` 并回传可平凡拷贝的 ``Value``（含 ``None``）。"""
  ...


@native
@copyable
class _ProcessHandle:
  """OS 子进程句柄（``Process`` 的 native 叶子）。"""

  _state: uintptr = 0

  def __init__(self): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  def start(self, target: Callable[[], None], name: str) -> None: ...

  def join(self, timeout: float64 = float.Inf) -> bool: ...

  def terminate(self) -> None: ...

  def kill(self) -> None: ...

  def close(self) -> None: ...

  @property
  @immutable
  def alive(self) -> bool: ...

  @property
  @immutable
  def pid(self) -> int: ...

  @property
  @immutable
  def exitCode(self) -> int: ...


@copyable
class Process:
  """抢占式 OS 子进程（对齐 ``multiprocessing.Process`` + 本仓 ``Thread``）。

  首版边界：
  - target 必须是 ``Callable[[], None]``；
  - ``daemon=True`` 显式拒绝；
  - Windows 上仅无捕获自由函数可 ``start``；捕获态抛 ``RuntimeError``；
  - ``join(timeout)`` 返回 ``None``，超时后用 ``alive`` 判断。
  """

  _handle: _ProcessHandle
  _target: Callable[[], None]
  _name: str
  _phase: int
  _daemon: bool = False

  def __init__(
    self,
    target: Callable[[], None],
    name: str = "",
    daemon: bool = False,
  ):
    if daemon:
      raise RuntimeError("daemon processes are not supported yet")
    self._target = target
    self._name = name
    self._phase = int(_ProcessPhaseEnum.Initial)

  def start(self) -> None:
    if self._phase != int(_ProcessPhaseEnum.Initial):
      raise RuntimeError("processes can only be started once")
    self._handle.start(self._target, self._name)
    self._phase = int(_ProcessPhaseEnum.Started)

  def run(self) -> None:
    self._target()

  def join(self, timeout: float64 = float.Inf) -> None:
    if self._phase == int(_ProcessPhaseEnum.Initial):
      raise RuntimeError("cannot join process before it is started")
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    finished: bool = self._handle.join(timeout)
    if finished:
      self._phase = int(_ProcessPhaseEnum.Stopped)

  def terminate(self) -> None:
    self._handle.terminate()

  def kill(self) -> None:
    self._handle.kill()

  def close(self) -> None:
    self._handle.close()

  @property
  def name(self) -> str:
    return self._name

  @property
  def daemon(self) -> bool:
    return self._daemon

  @property
  def alive(self) -> bool:
    if self._phase == int(_ProcessPhaseEnum.Initial):
      return False
    return self._handle.alive

  @property
  def pid(self) -> int:
    return self._handle.pid

  @property
  def exitCode(self) -> int:
    return self._handle.exitCode


@copyable
class _ProcessWorkItem[Value]:
  future: Future[Value]
  fn: Callable[[], Value]

  @overload
  def __init__(self):
    self.future = new()

  @overload
  def __init__(self, future: Future[Value], fn: Callable[[], Value]):
    self.future = future
    self.fn = fn


@refcount
class ProcessPool[Value]:
  """静态类型进程池：每任务新建一个 ``Process``（``max_tasks_per_child=1``）。

  用 ``ThreadPool`` 作 launcher 限流；``Value`` 首版限平凡可拷贝标量与 ``None``。
  """

  lock: Lock = new()
  workQueue: Queue[_ProcessWorkItem[Value]] = new()
  launchers: list[Thread] = []
  maxWorkers: int
  threadNamePrefix: str
  shutdownFlag: atomic[bool] = new(False)
  broken: atomic[bool] = new(False)
  threadCounter: atomic[int] = new(0)

  def __init__(self, maxWorkers: int = 4, threadNamePrefix: str = "ProcessPool"):
    if maxWorkers <= 0:
      raise ValueError("maxWorkers must be positive")
    self.maxWorkers = maxWorkers
    self.threadNamePrefix = threadNamePrefix

  def submit(self, fn: Callable[[], Value]) -> Future[Value]:
    future: Future[Value] = new()
    self.lock.acquire()
    try:
      if self.broken.load():
        raise RuntimeError("cannot schedule new futures after pool is broken")
      if self.shutdownFlag.load():
        raise RuntimeError("cannot schedule new futures after shutdown")
      self.workQueue.put(_ProcessWorkItem[Value](future, fn))
      self._adjustLauncherCount()
    finally:
      self.lock.release()
    return future

  def map(self, fns: list[Callable[[], Value]]) -> list[Value]:
    futures: list[Future[Value]] = []
    for i in range(len(fns)):
      futures.append(self.submit(fns[i]))
    out: list[Value] = []
    for i in range(len(futures)):
      out.append(futures[i].result(timeout=float.Inf))
    return out

  def shutdown(self, wait: bool = True, cancelFutures: bool = False) -> None:
    threads: list[Thread] = []
    self.lock.acquire()
    try:
      self.shutdownFlag.store(True)
      if cancelFutures:
        while True:
          try:
            item: _ProcessWorkItem[Value] = self.workQueue.getNoWait()
            item.future.cancel()
            self.workQueue.taskDone()
          except EmptyError:
            break
      self.workQueue.shutdown()
      for i in range(len(self.launchers)):
        threads.append(self.launchers[i])
    finally:
      self.lock.release()
    if wait:
      for i in range(len(threads)):
        threads[i].join()

  def __enter__(self) -> Self:
    return self

  def __exit__(self):
    self.shutdown()

  def _adjustLauncherCount(self) -> None:
    if len(self.launchers) >= self.maxWorkers:
      return
    index: int = self.threadCounter.fetchAdd(1)
    name: str = self.threadNamePrefix + "_" + str(index)
    worker: Thread = new(lambda: self._worker(), name)
    worker.start()
    self.launchers.append(worker)

  def _worker(self) -> None:
    while True:
      try:
        item: _ProcessWorkItem[Value] = self.workQueue.get()
        self._runItem(item)
      except ShutDownError:
        return

  def _runItem(self, item: _ProcessWorkItem[Value]) -> None:
    try:
      if item.future.setRunningOrNotifyCancel():
        try:
          result: Value = _processInvoke[Value](item.fn)
          item.future.setResult(result)
        except:
          item.future.setException()
    finally:
      self.workQueue.taskDone()


_WaitObject0: uint = 0
_WaitAbandoned: uint = 128


@immutable
def _processWait(handle: uintptr, timeout: float64) -> bool:
  if timeout < 0.0:
    raise ValueError("timeout value must be non-negative")
  millis: uint = PyiInfinite
  if timeout != float.Inf:
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

  _handle: uintptr
  name: str
  created: bool

  def __init__(self, name: str, initial: bool = False):
    if not name:
      raise ValueError("process synchronization name must not be empty")
    with name.useUtf8() as cname:
      handle: uintptr = pyiCreateEventA(None, 1, int(initial), cname)
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

  def wait(self, timeout: float64 = float.Inf) -> bool:
    return _processWait(self._handle, timeout)


@uncopyable
class ProcessMutex:
  """Windows 命名递归 mutex：同一 ``name`` 可跨进程互斥。"""

  _handle: uintptr
  name: str
  created: bool

  def __init__(self, name: str):
    if not name:
      raise ValueError("process synchronization name must not be empty")
    with name.useUtf8() as cname:
      handle: uintptr = pyiCreateMutexA(None, 0, cname)
    if handle == 0:
      raise OSError()
    self._handle = handle
    self.name = name
    self.created = pyiGetLastError() != PyiErrorAlreadyExists

  def __del__(self):
    if self._handle != 0:
      pyiCloseHandle(self._handle)
      self._handle = 0

  def acquire(self, blocking: bool = True, timeout: float64 = float.Inf) -> bool:
    if not blocking and timeout != float.Inf:
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

  _handle: uintptr
  name: str
  created: bool

  def __init__(self, name: str, value: int = 1, maximum: int = 2147483647):
    if value < 0 or maximum <= 0 or value > maximum:
      raise ValueError("invalid process semaphore value or maximum")
    if not name:
      raise ValueError("process synchronization name must not be empty")
    with name.useUtf8() as cname:
      handle: uintptr = pyiCreateSemaphoreA(None, value, maximum, cname)
    if handle == 0:
      raise OSError()
    self._handle = handle
    self.name = name
    self.created = pyiGetLastError() != PyiErrorAlreadyExists

  def __del__(self):
    if self._handle != 0:
      pyiCloseHandle(self._handle)
      self._handle = 0

  def acquire(self, blocking: bool = True, timeout: float64 = float.Inf) -> bool:
    if not blocking and timeout != float.Inf:
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


@uncopyable
class SharedMemory:
  """Windows 命名共享内存；同名参与者须传入相同的 ``size``。"""

  _handle: uintptr
  _address: uintptr
  name: str
  size: int
  created: bool

  def __init__(self, name: str, size: int):
    if size <= 0:
      raise ValueError("shared memory size must be positive")
    if not name:
      raise ValueError("process synchronization name must not be empty")
    invalidHandle: int = -1
    fileHandle: uintptr = cast(invalidHandle)
    with name.useUtf8() as cname:
      handle: uintptr = pyiCreateFileMappingA(
        fileHandle,
        None,
        PyiPageReadwrite,
        0,
        uint(size),
        cname,
      )
    if handle == 0:
      raise OSError()
    address: uintptr = pyiMapViewOfFile(handle, PyiFileMapWrite, 0, 0, uint64(size))
    if address == 0:
      pyiCloseHandle(handle)
      raise OSError()
    self._handle = handle
    self._address = address
    self.name = name
    self.size = size
    self.created = pyiGetLastError() != PyiErrorAlreadyExists

  def __del__(self):
    self.close()

  def close(self) -> None:
    if self._address != 0:
      pyiUnmapViewOfFile(self._address)
      self._address = 0
    if self._handle != 0:
      pyiCloseHandle(self._handle)
      self._handle = 0

  @property
  @immutable
  def view(self) -> span[byte]:
    if self._address == 0:
      raise RuntimeError("shared memory is closed")
    data: Pointer[byte] = cast(self._address)
    return new(data, self.size)


_ChannelHeaderSize: int = 4


@uncopyable
class ProcessChannel:
  """单槽命名字节通道：跨进程发送/接收一条不超过 ``capacity`` 的消息。"""

  _memory: Pointer[SharedMemory]
  _mutex: Pointer[ProcessMutex]
  _empty: Pointer[ProcessSemaphore]
  _ready: Pointer[ProcessSemaphore]
  capacity: int
  name: str
  created: bool

  def __init__(self, name: str, capacity: int):
    if capacity <= 0:
      raise ValueError("process channel capacity must be positive")
    self._memory = alloc[SharedMemory]()
    init(self._memory, name + "-memory", _ChannelHeaderSize + capacity)
    self._mutex = alloc[ProcessMutex]()
    init(self._mutex, name + "-mutex")
    self._empty = alloc[ProcessSemaphore]()
    init(self._empty, name + "-empty", 1, 1)
    self._ready = alloc[ProcessSemaphore]()
    init(self._ready, name + "-ready", 0, 1)
    self.capacity = capacity
    self.name = name
    self.created = self._memory.created
    initLock: ProcessMutex = new(name + "-init")
    initLock.acquire()
    try:
      if self.created:
        view: span[byte] = self._memory.view
        for i in range(_ChannelHeaderSize):
          view[i] = 0
    finally:
      initLock.release()

  def __del__(self):
    self.close()

  def close(self) -> None:
    if self._memory != None:
      self._memory.close()
      destroy(self._memory)
      free(self._memory)
      self._memory = None
    if self._mutex != None:
      destroy(self._mutex)
      free(self._mutex)
      self._mutex = None
    if self._empty != None:
      destroy(self._empty)
      free(self._empty)
      self._empty = None
    if self._ready != None:
      destroy(self._ready)
      free(self._ready)
      self._ready = None

  def send(self, data: byte[:], timeout: float64 = float.Inf) -> None:
    if len(data) > self.capacity:
      raise ValueError("process channel message exceeds capacity")
    if not self._empty.acquire(timeout=timeout):
      raise TimeoutError()
    published: bool = False
    try:
      self._mutex.acquire()
      try:
        view: span[byte] = self._memory.view
        n: int = len(data)
        view[0] = n & 255
        view[1] = (n >> 8) & 255
        view[2] = (n >> 16) & 255
        view[3] = (n >> 24) & 255
        for i in range(n):
          view[_ChannelHeaderSize + i] = data[i]
      finally:
        self._mutex.release()
      self._ready.release()
      published = True
    finally:
      if not published:
        self._empty.release()

  def receive(self, timeout: float64 = float.Inf) -> byte[:]:
    if not self._ready.acquire(timeout=timeout):
      raise TimeoutError()
    try:
      self._mutex.acquire()
      try:
        view: span[byte] = self._memory.view
        n: int = int(view[0]) | (int(view[1]) << 8) | (int(view[2]) << 16) | (int(view[3]) << 24)
        if n < 0 or n > self.capacity:
          raise RuntimeError("invalid process channel message length")
        out: byte[:] = new(n)
        for i in range(n):
          out[i] = view[_ChannelHeaderSize + i]
        return out
      finally:
        self._mutex.release()
    finally:
      self._empty.release()
