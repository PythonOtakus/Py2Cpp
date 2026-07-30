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


_THREAD_INITIAL: int = 0
_THREAD_STARTED: int = 1
_THREAD_STOPPED: int = 2

_BARRIER_RESETTING: int = -1
_BARRIER_BROKEN: int = -2
_BARRIER_FILLING: int = 0
_BARRIER_DRAINING: int = 1

_FUTURE_PENDING: int = 0
_FUTURE_RUNNING: int = 1
_FUTURE_CANCELLED: int = 2
_FUTURE_FINISHED: int = 3
_FUTURE_EXCEPTION: int = 4


@native
def _barrier_no_action() -> None:
  ...


class Empty(Exception):
  """``Queue.get_nowait()`` 或非阻塞/超时 ``get`` 在无元素时抛出。"""

  pass


class Full(Exception):
  """``Queue.put_nowait()`` 或非阻塞/超时 ``put`` 在队列满时抛出。"""

  pass


class ShutDown(Exception):
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


class BrokenThreadPool(RuntimeError):
  """线程池进入 broken 状态后提交任务时抛出。"""

  pass


@native
@copyable
@native_name("PyAtomic")
class atomic[T]:
  """``std::atomic`` 风格的共享原子值句柄。

  复制 ``atomic[T]`` 共享同一个 native 原子状态，适合被 owning lambda 捕获后跨线程更新。
  首版面向 C++11 ``std::atomic<T>`` 可实例化的标量类型；``fetch_add`` / ``fetch_sub`` 仅用于整数等支持该操作的类型。
  """

  _state: uintptr = 0

  @overload
  def __init__(self): ...

  @overload
  def __init__(self, value: T): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  @immutable
  def load(self) -> T:
    """读取当前值。"""
    ...

  def store(self, value: T) -> None:
    """写入新值。"""
    ...

  def exchange(self, value: T) -> T:
    """写入新值并返回旧值。"""
    ...

  def compare_exchange(self, expected: T, desired: T) -> bool:
    """若当前值等于 ``expected``，写入 ``desired`` 并返回 True。"""
    ...

  def fetch_add(self, delta: T) -> T:
    """原子加；返回修改前的旧值。"""
    ...

  def fetch_sub(self, delta: T) -> T:
    """原子减；返回修改前的旧值。"""
    ...


@native
@copyable
@native_name("Py*")
class Lock(friends=(Condition,)):
  """Python 风格二态 Lock：无 owner，允许跨线程 release。"""

  _state: uintptr = 0

  def __init__(self): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  def acquire(self, blocking: bool = True, timeout: float64 = -1.0) -> bool:
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
@native_name("Py*")
class RLock(friends=(Condition,)):
  """Python 风格递归锁：只有 owner 线程可以释放。"""

  _state: uintptr = 0

  def __init__(self): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  def acquire(self, blocking: bool = True, timeout: float64 = -1.0) -> bool:
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
  def _is_owned(self) -> bool:
    """当前线程是否持有锁，供 ``Condition`` 校验。"""
    ...

  def _release_save(self) -> int:
    """完全释放递归锁并返回原递归层数，供 ``Condition.wait`` 使用。"""
    ...

  def _acquire_restore(self, count: int) -> None:
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
@native_name("Py*")
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

  def acquire(self, blocking: bool = True, timeout: float64 = -1.0) -> bool:
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
  def _is_owned(self) -> bool:
    """当前调用者是否持有底锁。"""
    ...

  def wait(self, timeout: float64 = -1.0) -> bool:
    """释放底锁并等待通知；被通知返回 True，超时返回 False。"""
    ...

  def wait_for(self, predicate: Callable[[], bool], timeout: float64 = -1.0) -> bool:
    """在持锁状态循环等待 ``predicate`` 变为 True。"""
    ...

  def notify(self, n: int = 1) -> None:
    """唤醒至多 ``n`` 个等待者；调用者必须持有底锁。"""
    ...

  def notify_all(self) -> None:
    """唤醒所有等待者；调用者必须持有底锁。"""
    ...

  def __enter__(self) -> Self:
    """进入 ``with`` 临界区。"""
    ...

  def __exit__(self):
    """离开 ``with`` 临界区。"""
    ...


@copyable
@native_name("Py*")
class Event:
  """Python 3.13 ``threading.Event`` 子集。"""

  _cond: Condition
  _flag: atomic[bool]

  def __init__(self):
    self._cond = new()
    self._flag = new(False)

  @immutable
  def is_set(self) -> bool:
    """事件标志是否已设置。"""
    return self._flag.load()

  def set(self) -> None:
    """设置事件标志并唤醒所有等待者。"""
    self._cond.acquire()
    try:
      self._flag.store(True)
      self._cond.notify_all()
    finally:
      self._cond.release()

  def clear(self) -> None:
    """清除事件标志。"""
    self._cond.acquire()
    try:
      self._flag.store(False)
    finally:
      self._cond.release()

  def wait(self, timeout: float64 = -1.0) -> bool:
    """等待事件标志变为 True；超时返回 False。"""
    signaled: bool = True
    self._cond.acquire()
    try:
      if not self._flag.load():
        signaled = self._cond.wait_for(lambda: self._flag.load(), timeout)
    finally:
      self._cond.release()
    return signaled


@copyable
@native_name("Py*")
class Semaphore:
  """Python 3.13 ``threading.Semaphore`` 子集。"""

  _cond: Condition
  _value: atomic[int]

  def __init__(self, value: int = 1):
    if value < 0:
      raise ValueError("semaphore initial value must be >= 0")
    self._cond = new()
    self._value = new(value)

  def acquire(self, blocking: bool = True, timeout: float64 = -1.0) -> bool:
    """计数大于零时递减并返回 True，否则按参数等待。"""
    if not blocking and timeout >= 0.0:
      raise ValueError("can't specify timeout for non-blocking acquire")
    if timeout < -1.0:
      raise ValueError("timeout value must be non-negative")
    acquired: bool = False
    self._cond.acquire()
    try:
      if not blocking and self._value.load() <= 0:
        acquired = False
      else:
        if blocking:
          if timeout < 0.0:
            while self._value.load() <= 0:
              self._cond.wait()
          else:
            ok: bool = self._cond.wait_for(lambda: self._value.load() > 0, timeout)
            if not ok:
              return False
        if self._value.load() > 0:
          self._value.fetch_sub(1)
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
      self._value.fetch_add(n)
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
@native_name("Py*")
class BoundedSemaphore:
  """带上界检查的 ``Semaphore``；过量 ``release`` 抛 ``ValueError``。"""

  _cond: Condition
  _value: atomic[int]
  _initial_value: int = 0

  def __init__(self, value: int = 1):
    if value < 0:
      raise ValueError("semaphore initial value must be >= 0")
    self._cond = new()
    self._value = new(value)
    self._initial_value = value

  def acquire(self, blocking: bool = True, timeout: float64 = -1.0) -> bool:
    """计数大于零时递减并返回 True，否则按参数等待。"""
    if not blocking and timeout >= 0.0:
      raise ValueError("can't specify timeout for non-blocking acquire")
    if timeout < -1.0:
      raise ValueError("timeout value must be non-negative")
    acquired: bool = False
    self._cond.acquire()
    try:
      if not blocking and self._value.load() <= 0:
        acquired = False
      else:
        if blocking:
          if timeout < 0.0:
            while self._value.load() <= 0:
              self._cond.wait()
          else:
            ok: bool = self._cond.wait_for(lambda: self._value.load() > 0, timeout)
            if not ok:
              return False
        if self._value.load() > 0:
          self._value.fetch_sub(1)
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
      if self._value.load() + n > self._initial_value:
        raise ValueError("Semaphore released too many times")
      self._value.fetch_add(n)
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
@native_name("Py*")
class Barrier:
  """Python 3.13 ``threading.Barrier`` 子集，基于 ``Condition`` 组合实现。"""

  _cond: Condition
  _action: Callable[[], None]
  _parties: int = 0
  _count: atomic[int]
  _state: atomic[int]
  _timeout: float64 = -1.0
  _has_action: bool = False

  @overload
  def __init__(self, parties: int):
    if parties < 1:
      raise ValueError("parties must be >= 1")
    self._cond = new()
    self._action = _barrier_no_action
    self._parties = parties
    self._count = new(0)
    self._state = new(_BARRIER_FILLING)
    self._timeout = -1.0
    self._has_action = False

  @overload
  def __init__(self, parties: int, timeout: float64):
    if parties < 1:
      raise ValueError("parties must be >= 1")
    if timeout < -1.0:
      raise ValueError("timeout value must be non-negative")
    self._cond = new()
    self._action = _barrier_no_action
    self._parties = parties
    self._count = new(0)
    self._state = new(_BARRIER_FILLING)
    self._timeout = timeout
    self._has_action = False

  @overload
  def __init__(self, parties: int, action: Callable[[], None]):
    if parties < 1:
      raise ValueError("parties must be >= 1")
    self._cond = new()
    self._action = action
    self._parties = parties
    self._count = new(0)
    self._state = new(_BARRIER_FILLING)
    self._timeout = -1.0
    self._has_action = True

  @overload
  def __init__(self, parties: int, action: Callable[[], None], timeout: float64):
    if parties < 1:
      raise ValueError("parties must be >= 1")
    if timeout < -1.0:
      raise ValueError("timeout value must be non-negative")
    self._cond = new()
    self._action = action
    self._parties = parties
    self._count = new(0)
    self._state = new(_BARRIER_FILLING)
    self._timeout = timeout
    self._has_action = True

  def _enter(self) -> None:
    while self._state.load() in {_BARRIER_DRAINING, _BARRIER_RESETTING}:
      self._cond.wait()
    if self._state.load() == _BARRIER_BROKEN:
      raise BrokenBarrierError()

  def _release(self) -> None:
    try:
      if self._has_action:
        self._action()
      self._state.store(_BARRIER_DRAINING)
      self._cond.notify_all()
    except:
      self._break()
      raise BrokenBarrierError()

  def _wait(self, timeout: float64) -> None:
    if timeout < -1.0:
      raise ValueError("timeout value must be non-negative")
    ok: bool = self._cond.wait_for(lambda: self._state.load() != _BARRIER_FILLING, timeout)
    if not ok:
      self._break()
      raise BrokenBarrierError()
    if self._state.load() < _BARRIER_FILLING:
      raise BrokenBarrierError()

  def _exit(self) -> None:
    if self._count.load() == 0:
      if self._state.load() in {_BARRIER_DRAINING, _BARRIER_RESETTING}:
        self._state.store(_BARRIER_FILLING)
        self._cond.notify_all()

  def _break(self) -> None:
    self._state.store(_BARRIER_BROKEN)
    self._cond.notify_all()

  def wait(self, timeout: float64 = -1.0) -> int:
    """等待一轮 barrier 完成，并返回本轮 ``0..parties-1`` 的 index。"""
    actual_timeout: float64 = timeout
    if actual_timeout < 0.0:
      actual_timeout = self._timeout
    self._cond.acquire()
    try:
      self._enter()
      index: int = self._count.fetch_add(1)
      try:
        if index + 1 == self._parties:
          self._release()
        else:
          self._wait(actual_timeout)
        return index
      finally:
        self._count.fetch_sub(1)
        self._exit()
    finally:
      self._cond.release()
    return 0

  def reset(self) -> None:
    """重置 barrier；当前等待者会收到 ``BrokenBarrierError``。"""
    self._cond.acquire()
    try:
      if self._count.load() > 0:
        if self._state.load() in {_BARRIER_FILLING, _BARRIER_BROKEN}:
          self._state.store(_BARRIER_RESETTING)
        self._cond.notify_all()
      else:
        self._state.store(_BARRIER_FILLING)
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
  def n_waiting(self) -> int:
    waiting: int = 0
    if self._state.load() == _BARRIER_FILLING:
      waiting = self._count.load()
    return waiting

  @property
  def broken(self) -> bool:
    is_broken: bool = False
    is_broken = self._state.load() == _BARRIER_BROKEN
    return is_broken


@refcount
class Future[R]:
  """``concurrent.futures.Future`` 的静态类型子集。"""

  cond: Condition = new()
  state: atomic[int] = new(_FUTURE_PENDING)
  result_value: R

  def cancel(self) -> bool:
    cancelled: bool = False
    self.cond.acquire()
    try:
      state: int = self.state.load()
      if state == _FUTURE_PENDING:
        self.state.store(_FUTURE_CANCELLED)
        self.cond.notify_all()
        cancelled = True
      else:
        cancelled = state == _FUTURE_CANCELLED
    finally:
      self.cond.release()
    return cancelled

  @immutable
  def cancelled(self) -> bool:
    return self.state.load() == _FUTURE_CANCELLED

  @immutable
  def running(self) -> bool:
    return self.state.load() == _FUTURE_RUNNING

  @immutable
  def done(self) -> bool:
    return self.state.load() >= _FUTURE_CANCELLED

  def set_running_or_notify_cancel(self) -> bool:
    should_run: bool = False
    self.cond.acquire()
    try:
      state: int = self.state.load()
      if state == _FUTURE_CANCELLED:
        self.cond.notify_all()
        should_run = False
      elif state == _FUTURE_PENDING:
        self.state.store(_FUTURE_RUNNING)
        should_run = True
      else:
        raise InvalidStateError()
    finally:
      self.cond.release()
    return should_run

  def set_result(self, result: R) -> None:
    self.cond.acquire()
    try:
      state: int = self.state.load()
      if state not in {_FUTURE_RUNNING, _FUTURE_PENDING}:
        raise InvalidStateError()
      self.result_value = result
      self.state.store(_FUTURE_FINISHED)
      self.cond.notify_all()
    finally:
      self.cond.release()

  def set_exception(self) -> None:
    self.cond.acquire()
    try:
      state: int = self.state.load()
      if state not in {_FUTURE_RUNNING, _FUTURE_PENDING}:
        raise InvalidStateError()
      self.state.store(_FUTURE_EXCEPTION)
      self.cond.notify_all()
    finally:
      self.cond.release()

  def result(self, timeout: float64 = -1.0) -> R:
    if timeout < -1.0:
      raise ValueError("timeout value must be non-negative")
    self.cond.acquire()
    try:
      if self.state.load() < _FUTURE_CANCELLED:
        ok: bool = self.cond.wait_for(lambda: self.state.load() >= _FUTURE_CANCELLED, timeout)
        if not ok:
          raise TimeoutError()
      state: int = self.state.load()
      if state == _FUTURE_CANCELLED:
        raise CancelledError()
      if state == _FUTURE_EXCEPTION:
        raise RuntimeError("Future task raised")
      return self.result_value
    finally:
      self.cond.release()
    return self.result_value

  def exception(self, timeout: float64 = -1.0) -> bool:
    """首版返回是否保存了任务异常；完整异常对象 type-erasure 后续补齐。"""
    if timeout < -1.0:
      raise ValueError("timeout value must be non-negative")
    self.cond.acquire()
    try:
      if self.state.load() < _FUTURE_CANCELLED:
        ok: bool = self.cond.wait_for(lambda: self.state.load() >= _FUTURE_CANCELLED, timeout)
        if not ok:
          raise TimeoutError()
      state: int = self.state.load()
      if state == _FUTURE_CANCELLED:
        raise CancelledError()
      return state == _FUTURE_EXCEPTION
    finally:
      self.cond.release()
    return False


@native
@copyable
@native_name("Py*")
class Queue[T]:
  """Python 3.13 ``queue.Queue`` 子集：多生产者、多消费者 FIFO 阻塞队列。"""

  _state: uintptr = 0

  def __init__(self, maxsize: int = 0): ...

  def __del__(self): ...

  def __copy__(self, other: Self): ...

  @immutable
  def qsize(self) -> int:
    """返回近似队列长度。"""
    ...

  @immutable
  def __bool__(self) -> bool:
    """队列当前是否非空。"""
    ...

  @immutable
  def full(self) -> bool:
    """队列当前是否已达到 ``maxsize``。"""
    ...

  def put(self, item: T, block: bool = True, timeout: float64 = -1.0) -> None:
    """入队；满队列按 ``block`` / ``timeout`` 等待，失败抛 ``Full``。"""
    ...

  def put_nowait(self, item: T) -> None:
    """等价于 ``put(item, block=False)``。"""
    ...

  def get(self, block: bool = True, timeout: float64 = -1.0) -> T:
    """出队；空队列按 ``block`` / ``timeout`` 等待，失败抛 ``Empty``。"""
    ...

  def get_nowait(self) -> T:
    """等价于 ``get(block=False)``。"""
    ...

  def task_done(self) -> None:
    """声明一个由 ``get`` 取出的任务处理完成。"""
    ...

  def join(self) -> None:
    """阻塞直到所有已 ``put`` 的任务都被 ``task_done`` 确认。"""
    ...

  def shutdown(self, immediate: bool = False) -> None:
    """关闭队列；关闭后 ``put`` 抛 ``ShutDown``，空队列 ``get`` 抛 ``ShutDown``。"""
    ...


@native
@copyable
@native_name("Py*")
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
  def active_count() -> int:
    """返回当前活动线程数量。"""
    ...

  @staticproperty
  @immutable
  def actives() -> list[Self]:
    """返回当前活动线程句柄快照。"""
    ...

  def join(self, timeout: float64 = -1.0) -> bool:
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
  def native_id(self) -> int64:
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
  _phase: int = 0
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
    self._phase = _THREAD_INITIAL
    self._daemon = False

  @staticmethod
  def from_handle(handle: _ThreadHandle) -> Self:
    thread: Self = new(_barrier_no_action)
    thread._handle = handle
    thread._name = handle.name
    thread._phase = _THREAD_STARTED
    thread._daemon = handle.daemon
    return thread

  @staticproperty
  @immutable
  def actives() -> list[Self]:
    handles: list[_ThreadHandle] = _ThreadHandle.actives
    threads: list[Self] = []
    for i in range(len(handles)):
      thread: Self = new.from_handle(handles[i])
      threads.append(thread)
    return threads

  @staticproperty
  @immutable
  def current() -> Self:
    """返回当前线程的 ``Thread`` 包装。"""
    return new.from_handle(_ThreadHandle.current)

  @staticproperty
  @immutable
  def main() -> Self:
    """返回主线程的 ``Thread`` 包装。"""
    return new.from_handle(_ThreadHandle.main)

  @staticproperty
  @immutable
  def active_count() -> int:
    """返回当前活动线程数量。"""
    return _ThreadHandle.active_count

  def start(self) -> None:
    if self._phase != _THREAD_INITIAL:
      raise RuntimeError("threads can only be started once")
    self._handle.start(self._target, self._name, self._daemon)
    self._phase = _THREAD_STARTED

  def run(self) -> None:
    self._target()

  def join(self, timeout: float64 = -1.0) -> None:
    if self._phase == _THREAD_INITIAL:
      raise RuntimeError("cannot join thread before it is started")
    current: Self = new.current
    if current.ident == self.ident:
      raise RuntimeError("cannot join current thread")
    wait_timeout: float64 = timeout
    if wait_timeout < 0.0:
      wait_timeout = -1.0
    finished: bool = self._handle.join(wait_timeout)
    if finished:
      self._phase = _THREAD_STOPPED

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
  def native_id(self) -> int64:
    return self._handle.native_id

  @property
  def alive(self) -> bool:
    if self._phase == _THREAD_INITIAL:
      return False
    return self._handle.alive


@copyable
class _WorkItem[R]:
  future: Future[R]
  fn: Callable[[], R]

  @overload
  def __init__(self):
    self.future = new()

  @overload
  def __init__(self, future: Future[R], fn: Callable[[], R]):
    self.future = future
    self.fn = fn


@refcount
class ThreadPool[R]:
  """静态类型线程池：一个池处理同一返回类型 ``R`` 的零参数任务。"""

  lock: Lock = new()
  work_queue: Queue[_WorkItem[R]] = new()
  threads: list[Thread] = []
  max_workers: int = 0
  thread_name_prefix: str
  shutdown_flag: atomic[bool] = new(False)
  broken: atomic[bool] = new(False)
  thread_counter: atomic[int] = new(0)

  def __init__(self, max_workers: int = 4, thread_name_prefix: str = "ThreadPool"):
    self.max_workers = max_workers
    self.thread_name_prefix = thread_name_prefix

  def submit(self, fn: Callable[[], R]) -> Future[R]:
    future: Future[R] = new()
    self.lock.acquire()
    try:
      if self.broken.load():
        raise BrokenThreadPool()
      if self.shutdown_flag.load():
        raise RuntimeError("cannot schedule new futures after shutdown")
      item: _WorkItem[R] = new(future, fn)
      self.work_queue.put(item)
      self._adjust_thread_count()
    finally:
      self.lock.release()
    return future

  def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
    threads: list[Thread] = []
    self.lock.acquire()
    try:
      self.shutdown_flag.store(True)
      if cancel_futures:
        while True:
          try:
            item: _WorkItem[R] = self.work_queue.get_nowait()
            item.future.cancel()
            self.work_queue.task_done()
          except Empty:
            break
      self.work_queue.shutdown()
      for i in range(len(self.threads)):
        threads.append(self.threads[i])
    finally:
      self.lock.release()
    if wait:
      for i in range(len(threads)):
        threads[i].join()

  def _adjust_thread_count(self) -> None:
    if len(self.threads) >= self.max_workers:
      return
    index: int = self.thread_counter.fetch_add(1)
    name: str = self.thread_name_prefix + "_" + str(index)
    worker: Thread = new(lambda: self._worker(), name)
    worker.start()
    self.threads.append(worker)

  def _worker(self) -> None:
    while True:
      try:
        item: _WorkItem[R] = self.work_queue.get()
        self._run_item(item)
      except ShutDown:
        return

  def _run_item(self, item: _WorkItem[R]) -> None:
    try:
      if item.future.set_running_or_notify_cancel():
        try:
          result: R = item.fn()
          item.future.set_result(result)
        except:
          item.future.set_exception()
    finally:
      self.work_queue.task_done()
