"""单线程协作式 ``Task`` 调度（C# ``Task`` 风格：``Task.run`` / ``await Task.sleep`` / ``Task.gather``）。

``period`` 为每帧时长（秒）；``Task.period_count`` 为当前帧计数；``Task.duration = period_count * period``。
``Task.run_thread`` 参考 Python 3.13 ``asyncio.to_thread``，把阻塞 callable 放入 OS 线程并以 ``Task`` 等待结果。
"""
from ..builtins import *
from ..core.exceptions import RuntimeError
from ..core.iter_result import IterResult
from .thread import Future, ThreadPool


_PERIOD_DEFAULT: float64 = 1.0 / 60.0

TASK_CORO: int = 0
TASK_SLEEP: int = 1
TASK_GATHER: int = 2
TASK_THREAD: int = 3
TASK_IO: int = 4

LOOP_TASK_WAIT: int = 0
LOOP_TASK_POLL: int = 1

IO_READ: int = 1
IO_WRITE: int = 2


@copyable
class LoopHandle:
  """协程挂起时交给调度器的句柄（``await Task.*`` 路径）。"""

  kind: int = 0
  target_id: int64 = 0


@dataclass
class _WaitLink:
  target_id: int64 = 0
  waiter_id: int64 = 0


@dataclass
class _TimerEntry:
  wakeup_period: int64 = 0
  task_id: int64 = 0


@dataclass
class _IoWaitEntry:
  task_id: int64 = 0
  handle: int64 = 0
  events: int = 0


@dataclass
class _GatherChildLink:
  gather_slot_id: int64 = 0
  child_index: int64 = 0
  child_id: int64 = 0


@refcount
class _SlotBase(friends=(Scheduler, Task, _TaskAwaitIter)):
  """调度器任务槽基类（``list[_SlotBase]`` 多态池）。"""

  slot_id: int64 = 0
  kind: int = 0
  _done: bool = False

  def mark_done(self) -> None:
    self._done = True

  def is_done(self) -> bool:
    return self._done

  @virtual
  def advance(self) -> IterResult[LoopHandle, None]:
    raise RuntimeError("Task scheduler: slot advance not supported")

  @virtual
  def release_coro(self) -> None:
    pass

  @virtual
  def on_child_done(self, child: Self, child_index: int64) -> None:
    pass


@refcount
class _CoroSlot[R](_SlotBase):
  """协程任务槽：``@property result -> R``。"""

  _coro: Coroutine[LoopHandle, None, R]
  _use_send: bool = False
  _result: R

  def __init__(self, coro: Coroutine[LoopHandle, None, R]):
    self._coro = coro
    self._use_send = False

  @property
  def result(self) -> R:
    return self._result

  @override
  def advance(self) -> IterResult[LoopHandle, None]:
    if self._use_send:
      step: IterResult[LoopHandle, R] = self._coro.send(None)
      if step.done:
        self._result = step.return_value
        return new.Return(None)
      return new.Yield(step.value)
    step = next(self._coro)
    if step.done:
      self._result = step.return_value
      return new.Return(None)
    self._use_send = True
    return new.Yield(step.value)

  @override
  def release_coro(self) -> None:
    _coro_reset(self._coro)
    self._use_send = False


@refcount
class _SleepSlot(_SlotBase):
  """``Task.sleep`` 定时槽（无协程体）。"""


@refcount
class _IoSlot(_SlotBase):
  """``Task.wait_read`` / ``Task.wait_write`` IO 就绪槽（无协程体）。"""


@refcount
class _GatherSlot[U](_SlotBase):
  """``Task.gather`` 聚合槽：``@property result -> list[U]``。"""

  _results: list[U] @optional = []
  _pending: int64 = 0

  @property
  def result(self) -> list[U]:
    return self._results

  def setup(self, results: list[U], pending: int64) -> None:
    self._results = results
    self._pending = pending
    if pending == 0:
      self.mark_done()

  @override
  def on_child_done(self, child: _SlotBase, child_index: int64) -> None:
    self._results[child_index] = _slot_result[U](child)
    self._pending -= 1
    if self._pending == 0:
      self.mark_done()


@refcount
class _ThreadSlot[R](_SlotBase):
  """``Task.run_thread`` 线程槽：完成后从 ``Future`` 读取 ``result``。"""

  _future: Future[R]
  _pool: ThreadPool[R]

  def __init__(self, future: Future[R], pool: ThreadPool[R]):
    self._future = future
    self._pool = pool

  def get_result(self) -> R:
    return self._future.result(timeout=0.0)

  @override
  def advance(self) -> IterResult[LoopHandle, None]:
    if self._future.done():
      self.mark_done()
      return new.Return(None)
    h: LoopHandle = new()
    h.kind = LOOP_TASK_POLL
    h.target_id = self.slot_id
    return new.Yield(h)

  @override
  def release_coro(self) -> None:
    self._pool.shutdown()


def _make_coro_slot[R](coro: Coroutine[LoopHandle, None, R]) -> _SlotBase:
  slot: _CoroSlot[R] = new(coro)
  slot.kind = TASK_CORO
  return slot


def _gather_slot_setup[U](slot: _SlotBase, results: list[U], pending: int64) -> None:
  gs: _GatherSlot[U] @ref = cast(slot)
  gs.setup(results, pending)


def _gather_list_result[U](slot: _SlotBase) -> list[U]:
  gs: _GatherSlot[U] @ref = cast(slot)
  return gs.result.copy()


def _slot_result[T](slot: _SlotBase) -> T:
  if slot.kind == TASK_SLEEP:
    return None
  if slot.kind == TASK_IO:
    return None
  if slot.kind == TASK_THREAD:
    ts: _ThreadSlot[T] @ref = cast(slot)
    return ts.get_result()
  if T is list[...]:
    if slot.kind == TASK_GATHER:
      return _gather_list_result[T.Element](slot)
    cs: _CoroSlot[T] @ref = cast(slot)
    return cs.result.copy()
  else:
    cs: _CoroSlot[T] @ref = cast(slot)
    return cs.result


@native
@native_name("::py2cpp_concur_task_detail::coro_reset")
def _coro_reset[Y, S, R](coro: Coroutine[Y, S, R] @ref) -> None: ...


@native
@native_name("::py2cpp_concur_task_detail::make_coro_slot_from_gen")
def _make_coro_slot_from_gen(gen) -> _SlotBase: ...


@native
@native_name("::py2cpp_concur_task_detail::slot_result_for_coro")
def _slot_result_for_coro[Coro](slot: _SlotBase, _coro: Coro): ...


@native
@native_name("::py2cpp_concur_task_detail::io_ready")
def _io_ready(handle: int64, events: int) -> bool: ...

@copyable
class _TaskAwaitIter[T]:
  """``await task`` → ``yield from task.__await__()``。"""

  owner_id: int64 = 0
  target_id: int64 = 0
  sent: bool = False

  def copy_from(self, other: Self) -> None:
    self.owner_id = other.owner_id
    self.target_id = other.target_id
    self.sent = other.sent

  def __iter__(self) -> Self:
    return self

  def __await__(self) -> Self:
    return self

  def __next__(self) -> IterResult[LoopHandle, T]:
    if not self.sent:
      self.sent = True
      h: LoopHandle = new()
      h.kind = LOOP_TASK_WAIT
      h.target_id = self.target_id
      return new.Yield(h)
    sched: Scheduler @ref = _require_scheduler()
    slot: _SlotBase = sched.slot_by_id(self.target_id)
    if not slot.is_done():
      h: LoopHandle = new()
      h.kind = LOOP_TASK_WAIT
      h.target_id = self.target_id
      return new.Yield(h)
    return new.Return(_slot_result[T](slot))

  def send(self, _unused: None) -> IterResult[LoopHandle, T]:
    return next(self)


@copyable
class Scheduler(friends=(Task, _TaskAwaitIter)):
  period: float64 = 0.0
  period_count: int64 = 0
  _ready: list[int64] = []
  _slots: list[_SlotBase] = []
  _wait_links: list[_WaitLink] = []
  _timers: list[_TimerEntry] = []
  _io_waits: list[_IoWaitEntry] = []
  _gather_links: list[_GatherChildLink] = []

  def __repr__(self) -> str:
    return "<Scheduler>"

  def __init__(self, period: float64 = 0.0):
    self.period = period
    self.period_count = 0
    self._ready = []
    self._slots = []
    self._wait_links = []
    self._timers = []
    self._io_waits = []
    self._gather_links = []

  def slot_by_id(self, task_id: int64) -> _SlotBase:
    n: int64 = len(self._slots)
    for i in range(n):
      slot: _SlotBase = self._slots[i]
      if slot.slot_id == task_id:
        return slot
    raise RuntimeError(f"Task scheduler: unknown task id {task_id}")

  def drop_all_slots(self) -> None:
    n: int64 = len(self._slots)
    for i in range(n):
      slot: _SlotBase = self._slots[i]
      slot.release_coro()
    self._slots.clear()
    self._gather_links.clear()
    self._io_waits.clear()

  def _slot_done_by_id(self, task_id: int64) -> bool:
    s: _SlotBase = self.slot_by_id(task_id)
    return s.is_done()

  def _enqueue(self, task_id: int64) -> None:
    self._ready.append(task_id)

  def _register_slot(self, slot: _SlotBase) -> None:
    self._slots.append(slot)

  def _add_wait(self, waiter_id: int64, target_id: int64) -> None:
    link: _WaitLink = new()
    link.target_id = target_id
    link.waiter_id = waiter_id
    self._wait_links.append(link)
    target: _SlotBase = self.slot_by_id(target_id)
    if target.is_done():
      self._enqueue(waiter_id)

  def _register_timer(self, task_id: int64, wakeup_period: int64) -> None:
    entry: _TimerEntry = new()
    entry.wakeup_period = wakeup_period
    entry.task_id = task_id
    self._timers.append(entry)
    if wakeup_period <= self.period_count:
      t: _SlotBase = self.slot_by_id(task_id)
      if t.kind == TASK_SLEEP:
        t.mark_done()
        self._finish_slot(t)
      else:
        self._enqueue(task_id)

  def _register_io(self, task_id: int64, handle: int64, events: int) -> None:
    entry: _IoWaitEntry = new()
    entry.task_id = task_id
    entry.handle = handle
    entry.events = events
    self._io_waits.append(entry)
    if _io_ready(handle, events):
      t: _SlotBase = self.slot_by_id(task_id)
      if t.kind == TASK_IO and not t.is_done():
        t.mark_done()
        self._finish_slot(t)

  def _register_gather_child(
    self,
    gather_slot_id: int64,
    child_index: int64,
    child_id: int64,
  ) -> None:
    link: _GatherChildLink = new()
    link.gather_slot_id = gather_slot_id
    link.child_index = child_index
    link.child_id = child_id
    self._gather_links.append(link)

  def _wake_waiters(self, target_id: int64) -> None:
    keep: list[_WaitLink] = []
    for i in range(len(self._wait_links)):
      link: _WaitLink = self._wait_links[i]
      if link.target_id == target_id:
        self._enqueue(link.waiter_id)
      else:
        keep.append(link)
    self._wait_links = keep

  def _finish_slot(self, slot: _SlotBase) -> None:
    self._wake_waiters(slot.slot_id)
    if slot.kind == TASK_GATHER:
      return
    for i in range(len(self._gather_links)):
      link: _GatherChildLink = self._gather_links[i]
      if link.child_id != slot.slot_id:
        continue
      parent: _SlotBase = self.slot_by_id(link.gather_slot_id)
      parent.on_child_done(slot, link.child_index)
      if parent.is_done():
        self._finish_slot(parent)

  def _fire_timers(self) -> None:
    keep: list[_TimerEntry] = []
    for i in range(len(self._timers)):
      entry: _TimerEntry = self._timers[i]
      if entry.wakeup_period <= self.period_count:
        t: _SlotBase = self.slot_by_id(entry.task_id)
        if t.kind == TASK_SLEEP and not t.is_done():
          t.mark_done()
          self._finish_slot(t)
        else:
          if not t.is_done():
            self._enqueue(entry.task_id)
      else:
        keep.append(entry)
    self._timers = keep

  def _fire_io(self) -> None:
    keep: list[_IoWaitEntry] = []
    for i in range(len(self._io_waits)):
      entry: _IoWaitEntry = self._io_waits[i]
      t: _SlotBase = self.slot_by_id(entry.task_id)
      if t.is_done():
        continue
      if _io_ready(entry.handle, entry.events):
        if t.kind == TASK_IO:
          t.mark_done()
          self._finish_slot(t)
        else:
          self._enqueue(entry.task_id)
      else:
        keep.append(entry)
    self._io_waits = keep

  def _tick(self) -> None:
    self.period_count += 1
    self._fire_io()
    self._fire_timers()

  def _dispatch_handle(self, slot: _SlotBase, handle: LoopHandle) -> None:
    if handle.kind == LOOP_TASK_WAIT:
      self._add_wait(slot.slot_id, handle.target_id)
      return
    if handle.kind == LOOP_TASK_POLL:
      self._register_timer(handle.target_id, self.period_count + 1)
      return
    raise RuntimeError("Task scheduler: unknown loop handle kind")

  def pump(self) -> None:
    self._run_once()

  def _run_once(self) -> None:
    if not self._ready:
      self._tick()
      return
    task_id: int64 = self._ready.pop(0)
    slot: _SlotBase = self.slot_by_id(task_id)
    if slot.is_done():
      return
    if slot.kind not in {TASK_CORO, TASK_THREAD}:
      return
    step: IterResult[LoopHandle, None] = slot.advance()
    if step.done:
      slot.mark_done()
      self._finish_slot(slot)
    else:
      self._dispatch_handle(slot, step.value)

  def _secs_to_periods(self, secs: float64) -> int64:
    if secs <= 0.0:
      return 1
    n: float64 = secs / self.period
    periods: int64 = int(n)
    if float64(periods) < n:
      periods += 1
    if periods < 1:
      periods = 1
    return periods


@dataclass(eq=False, repr=False)
class _SchedState:
  have_scheduler: bool = False
  scheduler: Scheduler = new()
  next_task_id: int64 = 1

  def __repr__(self) -> str:
    return f"_SchedState(have_scheduler={self.have_scheduler}, next_task_id={self.next_task_id})"


_sched: _SchedState = new()


def _require_scheduler() -> Scheduler @ref:
  if not _sched.have_scheduler:
    raise RuntimeError("Task: no running scheduler (use Task.run)")
  return _sched.scheduler


def _alloc_task_id() -> int64:
  tid: int64 = _sched.next_task_id
  _sched.next_task_id += 1
  return tid


@copyable
class Task[T](friends=(Scheduler,)):
  """协作式任务句柄；静态 API 对齐 C# ``Task``。"""

  task_id: int64 = 0

  def _slot(self) -> _SlotBase:
    sched: Scheduler @ref = _require_scheduler()
    return sched.slot_by_id(self.task_id)

  @property
  def done(self) -> bool:
    s: _SlotBase = self._slot()
    return s.is_done()

  def result(self) -> T:
    if not self.done:
      raise RuntimeError("Task.result: task is not done")
    slot: _SlotBase = self._slot()
    return _slot_result[T](slot)

  def __await__(self) -> _TaskAwaitIter[T]:
    it: _TaskAwaitIter[T] = new()
    it.owner_id = self.task_id
    it.target_id = self.task_id
    return it

  @staticmethod
  def _wakeup_period(secs: float64) -> int64:
    sched: Scheduler @ref = _require_scheduler()
    extra: int64 = sched._secs_to_periods(secs)
    return sched.period_count + extra

  @staticmethod
  @immutable
  def run[Coro](main: Coro, period: float64 = 0.016666666666666666):
    """运行 ``main`` 直至完成并返回其 ``return`` 值。"""
    if _sched.have_scheduler:
      raise RuntimeError("Task.run: already running")
    sched: Scheduler @ref = _sched.scheduler
    sched.period = period
    sched.period_count = 0
    sched._ready.clear()
    sched._wait_links.clear()
    sched._timers.clear()
    sched._io_waits.clear()
    sched._gather_links.clear()
    sched.drop_all_slots()
    _sched.next_task_id = 1
    _sched.have_scheduler = True
    root_slot: _SlotBase = _make_coro_slot_from_gen(main)
    root_slot.slot_id = _alloc_task_id()
    root_id: int64 = root_slot.slot_id
    sched._register_slot(root_slot)
    sched._enqueue(root_id)
    while not sched._slot_done_by_id(root_id):
      sched.pump()
    _sched.have_scheduler = False
    root: _SlotBase = sched.slot_by_id(root_id)
    root.release_coro()
    return _slot_result_for_coro[Coro](root, main)

  @staticmethod
  def create[Y, S, R](coro: Coroutine[Y, S, R]) -> Task[R]:
    sched: Scheduler @ref = _require_scheduler()
    slot: _SlotBase = _make_coro_slot(coro)
    tid: int64 = _alloc_task_id()
    slot.slot_id = tid
    sched._register_slot(slot)
    sched._enqueue(tid)
    t: Task[R] = new()
    t.task_id = tid
    return t

  @staticmethod
  def run_thread(fn: Callable[[], T]) -> Self:
    """在线程中运行阻塞 callable，并返回可 ``await`` 的 ``Task[T]``。"""
    sched: Scheduler @ref = _require_scheduler()
    pool: ThreadPool[T] = new(1, "Task.run_thread")
    future: Future[T] = pool.submit(fn)
    slot: _ThreadSlot[T] = new(future, pool)
    tid: int64 = _alloc_task_id()
    slot.slot_id = tid
    slot.kind = TASK_THREAD
    sched._register_slot(slot)
    sched._enqueue(tid)
    t: Self = new()
    t.task_id = tid
    return t

  @staticmethod
  def wait_read(handle: int64) -> Task[None]:
    sched: Scheduler @ref = _require_scheduler()
    slot: _IoSlot = new()
    tid: int64 = _alloc_task_id()
    slot.slot_id = tid
    slot.kind = TASK_IO
    sched._register_slot(slot)
    sched._register_io(tid, handle, IO_READ)
    t: Task[None] = new()
    t.task_id = tid
    return t

  @staticmethod
  def wait_write(handle: int64) -> Task[None]:
    sched: Scheduler @ref = _require_scheduler()
    slot: _IoSlot = new()
    tid: int64 = _alloc_task_id()
    slot.slot_id = tid
    slot.kind = TASK_IO
    sched._register_slot(slot)
    sched._register_io(tid, handle, IO_WRITE)
    t: Task[None] = new()
    t.task_id = tid
    return t

  @staticmethod
  def sleep(secs: float64) -> Task[None]:
    sched: Scheduler @ref = _require_scheduler()
    slot: _SleepSlot = new()
    tid: int64 = _alloc_task_id()
    slot.slot_id = tid
    slot.kind = TASK_SLEEP
    sched._register_slot(slot)
    wakeup: int64 = Self._wakeup_period(secs)
    sched._register_timer(tid, wakeup)
    t: Task[None] = new()
    t.task_id = tid
    return t

  @staticmethod
  def gather[U](*tasks: Task[U][:]) -> Task[list[U]]:
    sched: Scheduler @ref = _require_scheduler()
    n: int64 = len(tasks)
    slot: _GatherSlot[U] = new()
    gid: int64 = _alloc_task_id()
    slot.slot_id = gid
    slot.kind = TASK_GATHER
    sched._register_slot(slot)
    results: list[U] = []
    pending: int64 = 0
    placeholder: U = new()
    for i in range(n):
      child: Task[U] = tasks[i]
      child_slot: _SlotBase = sched.slot_by_id(child.task_id)
      if child_slot.is_done():
        results.append(_slot_result[U](child_slot))
      else:
        results.append(placeholder)
        pending += 1
    _gather_slot_setup[U](sched.slot_by_id(gid), results, pending)
    for i in range(n):
      child: Task[U] = tasks[i]
      sched._register_gather_child(gid, i, child.task_id)
    t: Task[list[U]] = new()
    t.task_id = gid
    return t

  @staticproperty
  @immutable
  def period_count() -> int64:
    if not _sched.have_scheduler:
      return 0
    return _require_scheduler().period_count

  @staticproperty
  @immutable
  def duration() -> float64:
    if not _sched.have_scheduler:
      return 0.0
    sched: Scheduler @ref = _require_scheduler()
    pc: int64 = sched.period_count
    return float64(pc) * sched.period


type TaskPayloadOf[T, _R = ...] = _R if T is Task[_R] else T

type GatherElemOf[T, _U = ...] = (
  _U if T is list[_U]
  else _U if T is Task[list[_U]]
  else T
)
