"""抢占式线程基础设施（Python 3.13 ``threading`` 子集）。

首版提供 ``Thread``、``Lock``、``RLock``、``Condition``、``Event``、
``Semaphore``、``BoundedSemaphore``、``Barrier``、``atomic``、``Queue``、
``Future`` 与 ``ThreadPool``。
``Thread`` 只接受零参数 ``Callable[[], None]`` target，参数请用 owning lambda/绑定方法预先绑定。
daemon 线程在 shutdown manager 完成前显式拒绝。
"""
from ..builtins import *
from ..core.exceptions import Exception, RuntimeError, ValueError
from ..text import str


@enum
class _ThreadPhaseEnum:
  Initial = 0
  Started = 1
  Stopped = 2


@enum
class _BarrierStateEnum:
  Resetting = -1
  Broken = -2
  Filling = 0
  Draining = 1


@enum
class _FutureStateEnum:
  Pending = 0
  Running = 1
  Cancelled = 2
  Finished = 3
  Exception = 4


class EmptyError(Exception):
  """``Queue.getNoWait()`` 或非阻塞/超时 ``get`` 在无元素时抛出。"""

  pass


class FullError(Exception):
  """``Queue.putNoWait()`` 或非阻塞/超时 ``put`` 在队列满时抛出。"""

  pass


class ShutDownError(Exception):
  """``Queue.shutdown()`` 后对队列执行不允许的 ``put`` / ``get`` 时抛出。"""

  pass


class BrokenBarrierError(RuntimeError):
  """``Barrier`` 被 reset/abort/timeout/action 异常打破时抛出。"""

  pass


class CancelledError(Exception):
  """``Future`` 被取消后读取结果时抛出。"""

  pass


class TimeoutError(Exception):
  """``Future.result(timeout)`` 等待超时时抛出。"""

  pass


class InvalidStateError(Exception):
  """``Future`` 状态转换非法时抛出。"""

  pass


class BrokenThreadPoolError(RuntimeError):
  """线程池进入 broken 状态后提交任务时抛出。"""

  pass


@native
@copyable
class atomic[Value]:
  """``std::atomic`` 风格的共享原子值句柄。

  复制 ``atomic[T]`` 共享同一个 native 原子状态，适合被 owning lambda 捕获后跨线程更新。
  首版面向 C++11 ``std::atomic<T>`` 可实例化的标量类型；``fetchAdd`` / ``fetchSub`` 仅用于整数等支持该操作的类型。
  """

  _state: uintptr = 0

  @overload
  def __init__(self): ...

  @overload
  def __init__(self, value: Value): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  @immutable
  def load(self) -> Value:
    """读取当前值。"""
    ...

  def store(self, value: Value) -> None:
    """写入新值。"""
    ...

  def exchange(self, value: Value) -> Value:
    """写入新值并返回旧值。"""
    ...

  def compareExchange(self, expected: Value, desired: Value) -> bool:
    """若当前值等于 ``expected``，写入 ``desired`` 并返回 True。"""
    ...

  def fetchAdd(self, delta: Value) -> Value:
    """原子加；返回修改前的旧值。"""
    ...

  def fetchSub(self, delta: Value) -> Value:
    """原子减；返回修改前的旧值。"""
    ...


@native
@copyable
class Lock(friends=(Condition,)):
  """Python 风格二态 Lock：无 owner，允许跨线程 release。"""

  _state: uintptr = 0

  def __init__(self): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  def acquire(self, blocking: bool = True, timeout: float64 = float.Inf) -> bool:
    """获取锁；``blocking=False`` 且显式 timeout 时抛 ``ValueError``。"""
    ...

  def release(self) -> None:
    """释放锁；未锁定时抛 ``RuntimeError``。"""
    ...

  @immutable
  def locked(self) -> bool:
    """当前是否被锁定。"""
    ...

  def __enter__(self) -> Self:
    """进入 ``with`` 临界区。"""
    ...

  def __exit__(self):
    """离开 ``with`` 临界区。"""
    ...


@native
@copyable
class RLock(friends=(Condition,)):
  """Python 风格递归锁：只有 owner 线程可以释放。"""

  _state: uintptr = 0

  def __init__(self): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  def acquire(self, blocking: bool = True, timeout: float64 = float.Inf) -> bool:
    """获取递归锁；owner 重入时递归层数加一。"""
    ...

  def release(self) -> None:
    """释放一层递归；非 owner 或未锁定时抛 ``RuntimeError``。"""
    ...

  @immutable
  def locked(self) -> bool:
    """当前是否被任意线程持有。"""
    ...

  @immutable
  def _isOwned(self) -> bool:
    """当前线程是否持有锁，供 ``Condition`` 校验。"""
    ...

  def _releaseSave(self) -> int:
    """完全释放递归锁并返回原递归层数，供 ``Condition.wait`` 使用。"""
    ...

  def _acquireRestore(self, count: int) -> None:
    """重新获取递归锁并恢复递归层数，供 ``Condition.wait`` 使用。"""
    ...

  def __enter__(self) -> Self:
    """进入 ``with`` 临界区。"""
    ...

  def __exit__(self):
    """离开 ``with`` 临界区。"""
    ...


@native
@copyable
class Condition:
  """Python 3.13 ``threading.Condition`` 子集，默认使用 ``RLock`` 作为底锁。"""

  _state: uintptr = 0

  @overload
  def __init__(self): ...

  @overload
  def __init__(self, lock: Lock): ...

  @overload
  def __init__(self, lock: RLock): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  def acquire(self, blocking: bool = True, timeout: float64 = float.Inf) -> bool:
    """获取底锁。"""
    ...

  def release(self) -> None:
    """释放底锁。"""
    ...

  @immutable
  def locked(self) -> bool:
    """底锁当前是否被持有。"""
    ...

  @immutable
  def _isOwned(self) -> bool:
    """当前调用者是否持有底锁。"""
    ...

  def wait(self, timeout: float64 = float.Inf) -> bool:
    """释放底锁并等待通知；被通知返回 True，超时返回 False。"""
    ...

  def waitFor(self, predicate: Callable[[], bool], timeout: float64 = float.Inf) -> bool:
    """在持锁状态循环等待 ``predicate`` 变为 True。"""
    ...

  def notify(self, n: int = 1) -> None:
    """唤醒至多 ``n`` 个等待者；调用者必须持有底锁。"""
    ...

  def notifyAll(self) -> None:
    """唤醒所有等待者；调用者必须持有底锁。"""
    ...

  def __enter__(self) -> Self:
    """进入 ``with`` 临界区。"""
    ...

  def __exit__(self):
    """离开 ``with`` 临界区。"""
    ...


@copyable
class Event:
  """Python 3.13 ``threading.Event`` 子集。"""

  _cond: Condition
  _flag: atomic[bool]

  def __init__(self):
    self._cond = new()
    self._flag = new(False)

  @immutable
  def isSet(self) -> bool:
    """事件标志是否已设置。"""
    return self._flag.load()

  def set(self) -> None:
    """设置事件标志并唤醒所有等待者。"""
    self._cond.acquire()
    try:
      self._flag.store(True)
      self._cond.notifyAll()
    finally:
      self._cond.release()

  def clear(self) -> None:
    """清除事件标志。"""
    self._cond.acquire()
    try:
      self._flag.store(False)
    finally:
      self._cond.release()

  def wait(self, timeout: float64 = float.Inf) -> bool:
    """等待事件标志变为 True；超时返回 False。"""
    signaled: bool = True
    self._cond.acquire()
    try:
      if not self._flag.load():
        signaled = self._cond.waitFor(lambda: self._flag.load(), timeout)
    finally:
      self._cond.release()
    return signaled


@copyable
class Semaphore:
  """Python 3.13 ``threading.Semaphore`` 子集。"""

  _cond: Condition
  _value: atomic[int]

  def __init__(self, value: int = 1):
    if value < 0:
      raise ValueError("semaphore initial value must be >= 0")
    self._cond = new()
    self._value = new(value)

  def acquire(self, blocking: bool = True, timeout: float64 = float.Inf) -> bool:
    """计数大于零时递减并返回 True，否则按参数等待。"""
    if not blocking and timeout != float.Inf:
      raise ValueError("can't specify timeout for non-blocking acquire")
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    acquired: bool = False
    self._cond.acquire()
    try:
      if not blocking and self._value.load() <= 0:
        acquired = False
      else:
        if blocking:
          if timeout == float.Inf:
            while self._value.load() <= 0:
              self._cond.wait()
          else:
            ok: bool = self._cond.waitFor(lambda: self._value.load() > 0, timeout)
            if not ok:
              return False
        if self._value.load() > 0:
          self._value.fetchSub(1)
          acquired = True
    finally:
      self._cond.release()
    return acquired

  def release(self, n: int = 1) -> None:
    """释放 ``n`` 个许可并唤醒至多 ``n`` 个等待者。"""
    if n < 1:
      raise ValueError("n must be one or more")
    self._cond.acquire()
    try:
      self._value.fetchAdd(n)
      self._cond.notify(n)
    finally:
      self._cond.release()

  def __enter__(self) -> Self:
    """进入 ``with`` 临界区。"""
    self.acquire()
    return self

  def __exit__(self):
    """离开 ``with`` 临界区。"""
    self.release()


@copyable
class BoundedSemaphore:
  """带上界检查的 ``Semaphore``；过量 ``release`` 抛 ``ValueError``。"""

  _cond: Condition
  _value: atomic[int]
  _initialValue: int

  def __init__(self, value: int = 1):
    if value < 0:
      raise ValueError("semaphore initial value must be >= 0")
    self._cond = new()
    self._value = new(value)
    self._initialValue = value

  def acquire(self, blocking: bool = True, timeout: float64 = float.Inf) -> bool:
    """计数大于零时递减并返回 True，否则按参数等待。"""
    if not blocking and timeout != float.Inf:
      raise ValueError("can't specify timeout for non-blocking acquire")
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    acquired: bool = False
    self._cond.acquire()
    try:
      if not blocking and self._value.load() <= 0:
        acquired = False
      else:
        if blocking:
          if timeout == float.Inf:
            while self._value.load() <= 0:
              self._cond.wait()
          else:
            ok: bool = self._cond.waitFor(lambda: self._value.load() > 0, timeout)
            if not ok:
              return False
        if self._value.load() > 0:
          self._value.fetchSub(1)
          acquired = True
    finally:
      self._cond.release()
    return acquired

  def release(self, n: int = 1) -> None:
    """释放 ``n`` 个许可；超过初值时抛 ``ValueError`` 且状态不变。"""
    if n < 1:
      raise ValueError("n must be one or more")
    self._cond.acquire()
    try:
      if self._value.load() + n > self._initialValue:
        raise ValueError("Semaphore released too many times")
      self._value.fetchAdd(n)
      self._cond.notify(n)
    finally:
      self._cond.release()

  def __enter__(self) -> Self:
    """进入 ``with`` 临界区。"""
    self.acquire()
    return self

  def __exit__(self):
    """离开 ``with`` 临界区。"""
    self.release()


@copyable
class Barrier:
  """Python 3.13 ``threading.Barrier`` 子集，基于 ``Condition`` 组合实现。"""

  _cond: Condition
  _action: Callable[[], None]
  _parties: int
  _count: atomic[int]
  _state: atomic[int]
  _timeout: float64

  @overload
  def __init__(self, parties: int, timeout: float64 = float64.Inf):
    self.__init__(parties, new(), timeout)

  @overload
  def __init__(self, parties: int, action: Callable[[], None], timeout: float64 = float64.Inf):
    if parties < 1:
      raise ValueError("parties must be >= 1")
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    self._cond = new()
    self._action = action
    self._parties = parties
    self._count = new(0)
    self._state = new(int(_BarrierStateEnum.Filling))
    self._timeout = timeout

  def _enter(self) -> None:
    while self._state.load() in {int(_BarrierStateEnum.Draining), int(_BarrierStateEnum.Resetting)}:
      self._cond.wait()
    if self._state.load() == int(_BarrierStateEnum.Broken):
      raise BrokenBarrierError()

  def _release(self) -> None:
    try:
      self._action()
      self._state.store(int(_BarrierStateEnum.Draining))
      self._cond.notifyAll()
    except:
      self._break()
      raise BrokenBarrierError()

  def _wait(self, timeout: float64) -> None:
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    ok: bool = self._cond.waitFor(lambda: self._state.load() != int(_BarrierStateEnum.Filling), timeout)
    if not ok:
      self._break()
      raise BrokenBarrierError()
    if self._state.load() < int(_BarrierStateEnum.Filling):
      raise BrokenBarrierError()

  def _exit(self) -> None:
    if self._count.load() == 0:
      if self._state.load() in {int(_BarrierStateEnum.Draining), int(_BarrierStateEnum.Resetting)}:
        self._state.store(int(_BarrierStateEnum.Filling))
        self._cond.notifyAll()

  def _break(self) -> None:
    self._state.store(int(_BarrierStateEnum.Broken))
    self._cond.notifyAll()

  def wait(self, timeout: float64 = float64.Inf) -> int:
    """等待一轮 barrier 完成，并返回本轮 ``0..parties-1`` 的 index。"""
    actualTimeout: float64 = timeout
    if actualTimeout == float64.Inf:
      actualTimeout = self._timeout
    self._cond.acquire()
    try:
      self._enter()
      index: int = self._count.fetchAdd(1)
      try:
        if index + 1 == self._parties:
          self._release()
        else:
          self._wait(actualTimeout)
        return index
      finally:
        self._count.fetchSub(1)
        self._exit()
    finally:
      self._cond.release()
    return 0

  def reset(self) -> None:
    """重置 barrier；当前等待者会收到 ``BrokenBarrierError``。"""
    self._cond.acquire()
    try:
      if self._count.load() > 0:
        if self._state.load() in {int(_BarrierStateEnum.Filling), int(_BarrierStateEnum.Broken)}:
          self._state.store(int(_BarrierStateEnum.Resetting))
        self._cond.notifyAll()
      else:
        self._state.store(int(_BarrierStateEnum.Filling))
    finally:
      self._cond.release()

  def abort(self) -> None:
    """永久打破 barrier；后续 ``wait`` 直接抛 ``BrokenBarrierError``。"""
    self._cond.acquire()
    try:
      self._break()
    finally:
      self._cond.release()

  @property
  def parties(self) -> int:
    return self._parties

  @property
  def nWaiting(self) -> int:
    waiting: int = 0
    if self._state.load() == int(_BarrierStateEnum.Filling):
      waiting = self._count.load()
    return waiting

  @property
  def broken(self) -> bool:
    isBroken: bool = False
    isBroken = self._state.load() == int(_BarrierStateEnum.Broken)
    return isBroken


@refcount
class Future[Value]:
  """``concurrent.futures.Future`` 的静态类型子集。"""

  cond: Condition = new()
  state: atomic[int] = new(int(_FutureStateEnum.Pending))
  resultValue: Value

  def cancel(self) -> bool:
    cancelled: bool = False
    self.cond.acquire()
    try:
      state: int = self.state.load()
      if state == int(_FutureStateEnum.Pending):
        self.state.store(int(_FutureStateEnum.Cancelled))
        self.cond.notifyAll()
        cancelled = True
      else:
        cancelled = state == int(_FutureStateEnum.Cancelled)
    finally:
      self.cond.release()
    return cancelled

  @immutable
  def cancelled(self) -> bool:
    return self.state.load() == int(_FutureStateEnum.Cancelled)

  @immutable
  def running(self) -> bool:
    return self.state.load() == int(_FutureStateEnum.Running)

  @immutable
  def done(self) -> bool:
    return self.state.load() >= int(_FutureStateEnum.Cancelled)

  def setRunningOrNotifyCancel(self) -> bool:
    shouldRun: bool = False
    self.cond.acquire()
    try:
      state: int = self.state.load()
      if state == int(_FutureStateEnum.Cancelled):
        self.cond.notifyAll()
        shouldRun = False
      elif state == int(_FutureStateEnum.Pending):
        self.state.store(int(_FutureStateEnum.Running))
        shouldRun = True
      else:
        raise InvalidStateError()
    finally:
      self.cond.release()
    return shouldRun

  def setResult(self, result: Value) -> None:
    self.cond.acquire()
    try:
      state: int = self.state.load()
      if state not in {int(_FutureStateEnum.Running), int(_FutureStateEnum.Pending)}:
        raise InvalidStateError()
      self.resultValue = result
      self.state.store(int(_FutureStateEnum.Finished))
      self.cond.notifyAll()
    finally:
      self.cond.release()

  def setException(self) -> None:
    self.cond.acquire()
    try:
      state: int = self.state.load()
      if state not in {int(_FutureStateEnum.Running), int(_FutureStateEnum.Pending)}:
        raise InvalidStateError()
      self.state.store(int(_FutureStateEnum.Exception))
      self.cond.notifyAll()
    finally:
      self.cond.release()

  def result(self, timeout: float64 = float.Inf) -> Value:
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    self.cond.acquire()
    try:
      if self.state.load() < int(_FutureStateEnum.Cancelled):
        ok: bool = self.cond.waitFor(lambda: self.state.load() >= int(_FutureStateEnum.Cancelled), timeout)
        if not ok:
          raise TimeoutError()
      state: int = self.state.load()
      if state == int(_FutureStateEnum.Cancelled):
        raise CancelledError()
      if state == int(_FutureStateEnum.Exception):
        raise RuntimeError("Future task raised")
      return self.resultValue
    finally:
      self.cond.release()
    return self.resultValue

  def exception(self, timeout: float64 = float.Inf) -> bool:
    """首版返回是否保存了任务异常；完整异常对象 type-erasure 后续补齐。"""
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    self.cond.acquire()
    try:
      if self.state.load() < int(_FutureStateEnum.Cancelled):
        ok: bool = self.cond.waitFor(lambda: self.state.load() >= int(_FutureStateEnum.Cancelled), timeout)
        if not ok:
          raise TimeoutError()
      state: int = self.state.load()
      if state == int(_FutureStateEnum.Cancelled):
        raise CancelledError()
      return state == int(_FutureStateEnum.Exception)
    finally:
      self.cond.release()
    return False


@native
@copyable
class Queue[Element]:
  """Python 3.13 ``queue.Queue`` 子集：多生产者、多消费者 FIFO 阻塞队列。"""

  _state: uintptr = 0

  def __init__(self, maxSize: int = 0): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  @immutable
  def __len__(self) -> int:
    """返回近似队列长度（对应 CPython ``qsize``）。"""
    ...

  @immutable
  def __bool__(self) -> bool:
    """队列当前是否非空。"""
    ...

  @immutable
  def full(self) -> bool:
    """队列当前是否已达到 ``maxSize``。"""
    ...

  def put(self, item: Element, block: bool = True, timeout: float64 = float.Inf) -> None:
    """入队；满队列按 ``block`` / ``timeout`` 等待，失败抛 ``FullError``。"""
    ...

  def putNoWait(self, item: Element) -> None:
    """等价于 ``put(item, block=False)``。"""
    ...

  def get(self, block: bool = True, timeout: float64 = float.Inf) -> Element:
    """出队；空队列按 ``block`` / ``timeout`` 等待，失败抛 ``EmptyError``。"""
    ...

  def getNoWait(self) -> Element:
    """等价于 ``get(block=False)``。"""
    ...

  def taskDone(self) -> None:
    """声明一个由 ``get`` 取出的任务处理完成。"""
    ...

  def join(self) -> None:
    """阻塞直到所有已 ``put`` 的任务都被 ``taskDone`` 确认。"""
    ...

  def shutdown(self, immediate: bool = False) -> None:
    """关闭队列；关闭后 ``put`` 抛 ``ShutDownError``，空队列 ``get`` 抛 ``ShutDownError``。"""
    ...


@native
@copyable
class _ThreadHandle:
  """native thread state 句柄；公共状态机由 ``Thread`` 包装。"""

  _state: uintptr = 0

  def __init__(self): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  def start(self, target: Callable[[], None], name: str, daemon: bool) -> None:
    """启动 native 线程并复制 owning callable 到 worker state。"""
    ...

  @staticproperty
  @immutable
  def current() -> Self:
    """返回当前线程的 native 句柄。"""
    ...

  @staticproperty
  @immutable
  def main() -> Self:
    """返回主线程的 native 句柄。"""
    ...

  @staticproperty
  @immutable
  def activeCount() -> int:
    """返回当前活动线程数量。"""
    ...

  @staticproperty
  @immutable
  def actives() -> list[Self]:
    """返回当前活动线程句柄快照。"""
    ...

  def join(self, timeout: float64 = float.Inf) -> bool:
    """等待线程结束；返回是否已结束。"""
    ...

  @property
  @immutable
  def alive(self) -> bool:
    """线程是否仍在运行。"""
    ...

  @property
  @immutable
  def ident(self) -> int64:
    """运行时线程 cookie；未启动为 0。"""
    ...

  @property
  @immutable
  def nativeId(self) -> int64:
    """平台 native thread id；未启动为 0。"""
    ...

  @property
  @immutable
  def name(self) -> str:
    """线程名。"""
    ...

  @property
  @immutable
  def daemon(self) -> bool:
    """线程是否为 daemon。"""
    ...


@copyable
class Thread:
  """抢占式 OS 线程。

  首版边界：
  - target 必须是 ``Callable[[], None]``；
  - ``daemon=True`` 显式拒绝；
  - ``join(timeout)`` 返回 ``None``，超时后用 ``alive`` 判断。
  """

  _handle: _ThreadHandle
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
      raise RuntimeError("daemon threads are not supported yet")
    self._handle = new()
    self._target = target
    self._name = name
    self._phase = int(_ThreadPhaseEnum.Initial)

  @staticmethod
  def fromHandle(handle: _ThreadHandle) -> Self:
    thread: Self = new(new())
    thread._handle = handle
    thread._name = handle.name
    thread._phase = int(_ThreadPhaseEnum.Started)
    thread._daemon = handle.daemon
    return thread

  @staticproperty
  @immutable
  def actives() -> list[Self]:
    handles: list[_ThreadHandle] = _ThreadHandle.actives
    threads: list[Self] = []
    for i in range(len(handles)):
      threads.append(Self.fromHandle(handles[i]))
    return threads

  @staticproperty
  @immutable
  def current() -> Self:
    """返回当前线程的 ``Thread`` 包装。"""
    return new.fromHandle(_ThreadHandle.current)

  @staticproperty
  @immutable
  def main() -> Self:
    """返回主线程的 ``Thread`` 包装。"""
    return new.fromHandle(_ThreadHandle.main)

  @staticproperty
  @immutable
  def activeCount() -> int:
    """返回当前活动线程数量。"""
    return _ThreadHandle.activeCount

  def start(self) -> None:
    if self._phase != int(_ThreadPhaseEnum.Initial):
      raise RuntimeError("threads can only be started once")
    self._handle.start(self._target, self._name, self._daemon)
    self._phase = int(_ThreadPhaseEnum.Started)

  def run(self) -> None:
    self._target()

  def join(self, timeout: float64 = float.Inf) -> None:
    if self._phase == int(_ThreadPhaseEnum.Initial):
      raise RuntimeError("cannot join thread before it is started")
    current: Self = new.current
    if current.ident == self.ident:
      raise RuntimeError("cannot join current thread")
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    finished: bool = self._handle.join(timeout)
    if finished:
      self._phase = int(_ThreadPhaseEnum.Stopped)

  @property
  def name(self) -> str:
    return self._name

  @property
  def daemon(self) -> bool:
    return self._daemon

  @property
  def ident(self) -> int64:
    return self._handle.ident

  @property
  def nativeId(self) -> int64:
    return self._handle.nativeId

  @property
  def alive(self) -> bool:
    if self._phase == int(_ThreadPhaseEnum.Initial):
      return False
    return self._handle.alive


@copyable
class _WorkItem[Value]:
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
class ThreadPool[Value]:
  """静态类型线程池：一个池处理同一返回类型 ``R`` 的零参数任务。"""

  lock: Lock = new()
  workQueue: Queue[_WorkItem[Value]] = new()
  threads: list[Thread] = []
  maxWorkers: int
  threadNamePrefix: str
  shutdownFlag: atomic[bool] = new(False)
  broken: atomic[bool] = new(False)
  threadCounter: atomic[int] = new(0)

  def __init__(self, maxWorkers: int = 4, threadNamePrefix: str = "ThreadPool"):
    self.maxWorkers = maxWorkers
    self.threadNamePrefix = threadNamePrefix

  def submit(self, fn: Callable[[], Value]) -> Future[Value]:
    future: Future[Value] = new()
    self.lock.acquire()
    try:
      if self.broken.load():
        raise BrokenThreadPoolError()
      if self.shutdownFlag.load():
        raise RuntimeError("cannot schedule new futures after shutdown")
      self.workQueue.put(_WorkItem[Value](future, fn))
      self._adjustThreadCount()
    finally:
      self.lock.release()
    return future

  def shutdown(self, wait: bool = True, cancelFutures: bool = False) -> None:
    threads: list[Thread] = []
    self.lock.acquire()
    try:
      self.shutdownFlag.store(True)
      if cancelFutures:
        while True:
          try:
            item: _WorkItem[Value] = self.workQueue.getNoWait()
            item.future.cancel()
            self.workQueue.taskDone()
          except EmptyError:
            break
      self.workQueue.shutdown()
      for i in range(len(self.threads)):
        threads.append(self.threads[i])
    finally:
      self.lock.release()
    if wait:
      for i in range(len(threads)):
        threads[i].join()

  def _adjustThreadCount(self) -> None:
    if len(self.threads) >= self.maxWorkers:
      return
    index: int = self.threadCounter.fetchAdd(1)
    name: str = self.threadNamePrefix + "_" + str(index)
    worker: Thread = new(lambda: self._worker(), name)
    worker.start()
    self.threads.append(worker)

  def _worker(self) -> None:
    while True:
      try:
        item: _WorkItem[Value] = self.workQueue.get()
        self._runItem(item)
      except ShutDownError:
        return

  def _runItem(self, item: _WorkItem[Value]) -> None:
    try:
      if item.future.setRunningOrNotifyCancel():
        try:
          result: Value = item.fn()
          item.future.setResult(result)
        except:
          item.future.setException()
    finally:
      self.workQueue.taskDone()
