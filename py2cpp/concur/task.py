"""单线程协作式 ``Task`` 调度（C# ``Task`` 风格：``Task.run`` / ``await Task.sleep`` / ``Task.gather``）。

``period`` 为每帧时长（秒）；``Task.periodCount`` 为当前帧计数；``Task.duration = periodCount * period``。
``Task.runThread`` 参考 Python 3.13 ``asyncio.to_thread``，把阻塞 callable 放入 OS 线程并以 ``Task`` 等待结果。
"""
from ..builtins import *
from ..core.exceptions import RuntimeError
from ..core.iter_result import IterResult
from .thread import Future, ThreadPool


_PeriodDefault: float64 = 1.0 / 60.0

TaskCoro: int = 0
TaskSleep: int = 1
TaskGather: int = 2
TaskThread: int = 3
TaskIo: int = 4

LoopTaskWait: int = 0
LoopTaskPoll: int = 1

IoRead: int = 1
IoWrite: int = 2


@copyable
class LoopHandle:
  """协程挂起时交给调度器的句柄（``await Task.*`` 路径）。"""

  kind: int = 0
  targetId: int64 = 0


@dataclass
class _WaitLink:
  targetId: int64 = 0
  waiterId: int64 = 0


@dataclass
class _TimerEntry:
  wakeupPeriod: int64 = 0
  taskId: int64 = 0


@dataclass
class _IoWaitEntry:
  taskId: int64 = 0
  handle: int64 = 0
  events: int = 0


@dataclass
class _GatherChildLink:
  gatherSlotId: int64 = 0
  childIndex: int64 = 0
  childId: int64 = 0


@refcount
class _SlotBase(friends=(Scheduler, Task, _TaskAwaitIter)):
  """调度器任务槽基类（``list[_SlotBase]`` 多态池）。"""

  slotId: int64 = 0
  kind: int = 0
  _done: bool = False

  def markDone(self) -> None:
    self._done = True

  def isDone(self) -> bool:
    return self._done

  @virtual
  def advance(self) -> IterResult[LoopHandle, None]:
    raise RuntimeError("Task scheduler: slot advance not supported")

  @virtual
  def releaseCoro(self) -> None:
    pass

  @virtual
  def onChildDone(self, child: Self, childIndex: int64) -> None:
    pass


@refcount
class _CoroSlot[Value](_SlotBase):
  """协程任务槽：``@property result -> R``。"""

  _coro: CoroutineType[LoopHandle, None, Value]
  _useSend: bool = False
  _result: Value

  def __init__(self, coro: CoroutineType[LoopHandle, None, Value]):
    self._coro = coro

  @property
  def result(self) -> Value:
    return self._result

  @override
  def advance(self) -> IterResult[LoopHandle, None]:
    if self._useSend:
      step: IterResult[LoopHandle, Value] = self._coro.send(None)
      if step.done:
        self._result = step.returnValue
        return new.Return(None)
      return new.Yield(step.value)
    step = next(self._coro)
    if step.done:
      self._result = step.returnValue
      return new.Return(None)
    self._useSend = True
    return new.Yield(step.value)

  @override
  def releaseCoro(self) -> None:
    _coroReset(self._coro)
    self._useSend = False


@refcount
class _SleepSlot(_SlotBase):
  """``Task.sleep`` 定时槽（无协程体）。"""


@refcount
class _IoSlot(_SlotBase):
  """``Task.waitRead`` / ``Task.waitWrite`` IO 就绪槽（无协程体）。"""


@refcount
class _GatherSlot[Item](_SlotBase):
  """``Task.gather`` 聚合槽：``@property result -> list[U]``。"""

  _results: list[Item] = []
  _pending: int64 = 0

  @property
  def result(self) -> list[Item]:
    return self._results

  def setup(self, results: list[Item], pending: int64) -> None:
    self._results = results
    self._pending = pending
    if pending == 0:
      self.markDone()

  @override
  def onChildDone(self, child: _SlotBase, childIndex: int64) -> None:
    self._results[childIndex] = _slotResult[Item](child)
    self._pending -= 1
    if self._pending == 0:
      self.markDone()


@refcount
class _ThreadSlot[Value](_SlotBase):
  """``Task.runThread`` 线程槽：完成后从 ``Future`` 读取 ``result``。"""

  _future: Future[Value]
  _pool: ThreadPool[Value]

  def __init__(self, future: Future[Value], pool: ThreadPool[Value]):
    self._future = future
    self._pool = pool

  def getResult(self) -> Value:
    return self._future.result(timeout=0.0)

  @override
  def advance(self) -> IterResult[LoopHandle, None]:
    if self._future.done():
      self.markDone()
      return new.Return(None)
    h: LoopHandle = new(kind=LoopTaskPoll, targetId=self.slotId)
    return new.Yield(h)

  @override
  def releaseCoro(self) -> None:
    self._pool.shutdown()


def _makeCoroSlot[Value](coro: CoroutineType[LoopHandle, None, Value]) -> _SlotBase:
  slot: _CoroSlot[Value] = new(coro)
  slot.kind = TaskCoro
  return slot


def _gatherSlotSetup[Item](slot: _SlotBase, results: list[Item], pending: int64) -> None:
  gs: _GatherSlot[Item] @ref = cast(slot)
  gs.setup(results, pending)


def _gatherListResult[Item](slot: _SlotBase) -> list[Item]:
  gs: _GatherSlot[Item] @ref = cast(slot)
  return gs.result


def _slotResult[Value](slot: _SlotBase) -> Value:
  if slot.kind == TaskSleep:
    return None
  if slot.kind == TaskIo:
    return None
  if slot.kind == TaskThread:
    ts: _ThreadSlot[Value] @ref = cast(slot)
    return ts.getResult()
  if Value is list[...]:
    if slot.kind == TaskGather:
      return _gatherListResult[Value.Element](slot)
    cs: _CoroSlot[Value] @ref = cast(slot)
    return cs.result
  else:
    cs: _CoroSlot[Value] @ref = cast(slot)
    return cs.result


@native
@native_name("::py2cpp_concur_task_detail::coro_reset")
def _coroReset[Y, S, Value](coro: CoroutineType[Y, S, Value] @ref) -> None: ...


@native
@native_name("::py2cpp_concur_task_detail::make_coro_slot_from_gen")
def _makeCoroSlotFromGen(gen) -> _SlotBase: ...


@native
@native_name("::py2cpp_concur_task_detail::slot_result_for_coro")
def _slotResultForCoro[Coro](slot: _SlotBase, _coro: Coro): ...


@native
@native_name("::py2cpp_concur_task_detail::io_ready")
def _ioReady(handle: int64, events: int) -> bool: ...

@copyable
class _TaskAwaitIter[Value]:
  """``await task`` → ``yield from task.__await__()``。"""

  ownerId: int64 = 0
  targetId: int64 = 0
  sent: bool = False

  def copyFrom(self, other: Self) -> None:
    self.ownerId = other.ownerId
    self.targetId = other.targetId
    self.sent = other.sent

  def __iter__(self) -> Self:
    return self

  def __await__(self) -> Self:
    return self

  def __next__(self) -> IterResult[LoopHandle, Value]:
    if not self.sent:
      self.sent = True
      h: LoopHandle = new(kind=LoopTaskWait, targetId=self.targetId)
      return new.Yield(h)
    sched: Scheduler @ref = _requireScheduler()
    slot: _SlotBase = sched.slotById(self.targetId)
    if not slot.isDone():
      h: LoopHandle = new(kind=LoopTaskWait, targetId=self.targetId)
      return new.Yield(h)
    return new.Return(_slotResult[Value](slot))

  def send(self, _unused: None) -> IterResult[LoopHandle, Value]:
    return next(self)


@copyable
class Scheduler(friends=(Task, _TaskAwaitIter)):
  period: float64
  periodCount: int64 = 0
  _ready: list[int64]
  _slots: list[_SlotBase]
  _waitLinks: list[_WaitLink]
  _timers: list[_TimerEntry]
  _ioWaits: list[_IoWaitEntry]
  _gatherLinks: list[_GatherChildLink]

  def __repr__(self) -> str:
    return "<Scheduler>"

  def __init__(self, period: float64 = 0.0):
    self.period = period
    self._ready = []
    self._slots = []
    self._waitLinks = []
    self._timers = []
    self._ioWaits = []
    self._gatherLinks = []

  def slotById(self, taskId: int64) -> _SlotBase:
    n: int64 = len(self._slots)
    for i in range(n):
      slot: _SlotBase = self._slots[i]
      if slot.slotId == taskId:
        return slot
    raise RuntimeError(f"Task scheduler: unknown task id {taskId}")

  def dropAllSlots(self) -> None:
    n: int64 = len(self._slots)
    for i in range(n):
      slot: _SlotBase = self._slots[i]
      slot.releaseCoro()
    self._slots.clear()
    self._gatherLinks.clear()
    self._ioWaits.clear()

  def _slotDoneById(self, taskId: int64) -> bool:
    s: _SlotBase = self.slotById(taskId)
    return s.isDone()

  def _enqueue(self, taskId: int64) -> None:
    self._ready.append(taskId)

  def _registerSlot(self, slot: _SlotBase) -> None:
    self._slots.append(slot)

  def _addWait(self, waiterId: int64, targetId: int64) -> None:
    link: _WaitLink = new(targetId=targetId, waiterId=waiterId)
    self._waitLinks.append(link)
    target: _SlotBase = self.slotById(targetId)
    if target.isDone():
      self._enqueue(waiterId)

  def _registerTimer(self, taskId: int64, wakeupPeriod: int64) -> None:
    entry: _TimerEntry = new(wakeupPeriod=wakeupPeriod, taskId=taskId)
    self._timers.append(entry)
    if wakeupPeriod <= self.periodCount:
      t: _SlotBase = self.slotById(taskId)
      if t.kind == TaskSleep:
        t.markDone()
        self._finishSlot(t)
      else:
        self._enqueue(taskId)

  def _registerIo(self, taskId: int64, handle: int64, events: int) -> None:
    entry: _IoWaitEntry = new(taskId=taskId, handle=handle, events=events)
    self._ioWaits.append(entry)
    if _ioReady(handle, events):
      t: _SlotBase = self.slotById(taskId)
      if t.kind == TaskIo and not t.isDone():
        t.markDone()
        self._finishSlot(t)

  def _registerGatherChild(
    self,
    gatherSlotId: int64,
    childIndex: int64,
    childId: int64,
  ) -> None:
    link: _GatherChildLink = new(gatherSlotId=gatherSlotId, childIndex=childIndex, childId=childId)
    self._gatherLinks.append(link)

  def _wakeWaiters(self, targetId: int64) -> None:
    keep: list[_WaitLink] = []
    for i in range(len(self._waitLinks)):
      link: _WaitLink = self._waitLinks[i]
      if link.targetId == targetId:
        self._enqueue(link.waiterId)
      else:
        keep.append(link)
    self._waitLinks = keep

  def _finishSlot(self, slot: _SlotBase) -> None:
    self._wakeWaiters(slot.slotId)
    if slot.kind == TaskGather:
      return
    for i in range(len(self._gatherLinks)):
      link: _GatherChildLink = self._gatherLinks[i]
      if link.childId != slot.slotId:
        continue
      parent: _SlotBase = self.slotById(link.gatherSlotId)
      parent.onChildDone(slot, link.childIndex)
      if parent.isDone():
        self._finishSlot(parent)

  def _fireTimers(self) -> None:
    keep: list[_TimerEntry] = []
    for i in range(len(self._timers)):
      entry: _TimerEntry = self._timers[i]
      if entry.wakeupPeriod <= self.periodCount:
        t: _SlotBase = self.slotById(entry.taskId)
        if t.kind == TaskSleep and not t.isDone():
          t.markDone()
          self._finishSlot(t)
        else:
          if not t.isDone():
            self._enqueue(entry.taskId)
      else:
        keep.append(entry)
    self._timers = keep

  def _fireIo(self) -> None:
    keep: list[_IoWaitEntry] = []
    for i in range(len(self._ioWaits)):
      entry: _IoWaitEntry = self._ioWaits[i]
      t: _SlotBase = self.slotById(entry.taskId)
      if t.isDone():
        continue
      if _ioReady(entry.handle, entry.events):
        if t.kind == TaskIo:
          t.markDone()
          self._finishSlot(t)
        else:
          self._enqueue(entry.taskId)
      else:
        keep.append(entry)
    self._ioWaits = keep

  def _tick(self) -> None:
    self.periodCount += 1
    self._fireIo()
    self._fireTimers()

  def _dispatchHandle(self, slot: _SlotBase, handle: LoopHandle) -> None:
    if handle.kind == LoopTaskWait:
      self._addWait(slot.slotId, handle.targetId)
      return
    if handle.kind == LoopTaskPoll:
      self._registerTimer(handle.targetId, self.periodCount + 1)
      return
    raise RuntimeError("Task scheduler: unknown loop handle kind")

  def pump(self) -> None:
    self._runOnce()

  def _runOnce(self) -> None:
    if not self._ready:
      self._tick()
      return
    taskId: int64 = self._ready.pop(0)
    slot: _SlotBase = self.slotById(taskId)
    if slot.isDone():
      return
    if slot.kind not in {TaskCoro, TaskThread}:
      return
    step: IterResult[LoopHandle, None] = slot.advance()
    if step.done:
      slot.markDone()
      self._finishSlot(slot)
    else:
      self._dispatchHandle(slot, step.value)

  def _secsToPeriods(self, secs: float64) -> int64:
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
  haveScheduler: bool = False
  scheduler: Scheduler = new()
  nextTaskId: int64 = 1

  def __repr__(self) -> str:
    return f"_SchedState(haveScheduler={self.haveScheduler}, nextTaskId={self.nextTaskId})"


_sched: _SchedState = new()


def _requireScheduler() -> Scheduler @ref:
  if not _sched.haveScheduler:
    raise RuntimeError("Task: no running scheduler (use Task.run)")
  return _sched.scheduler


def _allocTaskId() -> int64:
  tid: int64 = _sched.nextTaskId
  _sched.nextTaskId += 1
  return tid


@copyable
class Task[Value](friends=(Scheduler,)):
  """协作式任务句柄；静态 API 对齐 C# ``Task``。"""

  taskId: int64 = 0

  def _slot(self) -> _SlotBase:
    sched: Scheduler @ref = _requireScheduler()
    return sched.slotById(self.taskId)

  @property
  def done(self) -> bool:
    s: _SlotBase = self._slot()
    return s.isDone()

  def result(self) -> Value:
    if not self.done:
      raise RuntimeError("Task.result: task is not done")
    slot: _SlotBase = self._slot()
    return _slotResult[Value](slot)

  def __await__(self) -> _TaskAwaitIter[Value]:
    it: _TaskAwaitIter[Value] = new()
    it.ownerId = self.taskId
    it.targetId = self.taskId
    return it

  @staticmethod
  def _wakeupPeriod(secs: float64) -> int64:
    sched: Scheduler @ref = _requireScheduler()
    extra: int64 = sched._secsToPeriods(secs)
    return sched.periodCount + extra

  @staticmethod
  @immutable
  def run[Coro](main: Coro, period: float64 = 0.016666666666666666):
    """运行 ``main`` 直至完成并返回其 ``return`` 值。"""
    if _sched.haveScheduler:
      raise RuntimeError("Task.run: already running")
    sched: Scheduler @ref = _sched.scheduler
    sched.period = period
    sched.periodCount = 0
    sched._ready.clear()
    sched._waitLinks.clear()
    sched._timers.clear()
    sched._ioWaits.clear()
    sched._gatherLinks.clear()
    sched.dropAllSlots()
    _sched.nextTaskId = 1
    _sched.haveScheduler = True
    rootSlot: _SlotBase = _makeCoroSlotFromGen(main)
    rootSlot.slotId = _allocTaskId()
    rootId: int64 = rootSlot.slotId
    sched._registerSlot(rootSlot)
    sched._enqueue(rootId)
    while not sched._slotDoneById(rootId):
      sched.pump()
    _sched.haveScheduler = False
    root: _SlotBase = sched.slotById(rootId)
    root.releaseCoro()
    return _slotResultForCoro[Coro](root, main)

  @staticmethod
  def create[Y, S, Result](coro: CoroutineType[Y, S, Result]) -> Task[Result]:
    sched: Scheduler @ref = _requireScheduler()
    slot: _SlotBase = _makeCoroSlot(coro)
    tid: int64 = _allocTaskId()
    slot.slotId = tid
    sched._registerSlot(slot)
    sched._enqueue(tid)
    return new(taskId=tid)

  @staticmethod
  def runThread(fn: Callable[[], Value]) -> Self:
    """在线程中运行阻塞 callable，并返回可 ``await`` 的 ``Task[T]``。"""
    sched: Scheduler @ref = _requireScheduler()
    pool: ThreadPool[Value] = new(1, "Task.runThread")
    future: Future[Value] = pool.submit(fn)
    slot: _ThreadSlot[Value] = new(future, pool)
    tid: int64 = _allocTaskId()
    slot.slotId = tid
    slot.kind = TaskThread
    sched._registerSlot(slot)
    sched._enqueue(tid)
    return new(taskId=tid)

  @staticmethod
  def waitRead(handle: int64) -> Task[None]:
    sched: Scheduler @ref = _requireScheduler()
    slot: _IoSlot = new()
    tid: int64 = _allocTaskId()
    slot.slotId = tid
    slot.kind = TaskIo
    sched._registerSlot(slot)
    sched._registerIo(tid, handle, IoRead)
    return new(taskId=tid)

  @staticmethod
  def waitWrite(handle: int64) -> Task[None]:
    sched: Scheduler @ref = _requireScheduler()
    slot: _IoSlot = new()
    tid: int64 = _allocTaskId()
    slot.slotId = tid
    slot.kind = TaskIo
    sched._registerSlot(slot)
    sched._registerIo(tid, handle, IoWrite)
    return new(taskId=tid)

  @staticmethod
  def sleep(secs: float64) -> Task[None]:
    sched: Scheduler @ref = _requireScheduler()
    slot: _SleepSlot = new()
    tid: int64 = _allocTaskId()
    slot.slotId = tid
    slot.kind = TaskSleep
    sched._registerSlot(slot)
    wakeup: int64 = Self._wakeupPeriod(secs)
    sched._registerTimer(tid, wakeup)
    return new(taskId=tid)

  @staticmethod
  def gather[Item](*tasks: Task[Item][:]) -> Task[list[Item]]:
    sched: Scheduler @ref = _requireScheduler()
    n: int64 = len(tasks)
    slot: _GatherSlot[Item] = new()
    gid: int64 = _allocTaskId()
    slot.slotId = gid
    slot.kind = TaskGather
    sched._registerSlot(slot)
    results: list[Item] = []
    pending: int64 = 0
    placeholder: Item = new()
    for i in range(n):
      child: Task[Item] = tasks[i]
      childSlot: _SlotBase = sched.slotById(child.taskId)
      if childSlot.isDone():
        results.append(_slotResult[Item](childSlot))
      else:
        results.append(placeholder)
        pending += 1
    _gatherSlotSetup[Item](sched.slotById(gid), results, pending)
    for i in range(n):
      child: Task[Item] = tasks[i]
      sched._registerGatherChild(gid, i, child.taskId)
    return new(taskId=gid)

  @staticproperty
  @immutable
  def periodCount() -> int64:
    if not _sched.haveScheduler:
      return 0
    return _requireScheduler().periodCount

  @staticproperty
  @immutable
  def duration() -> float64:
    if not _sched.haveScheduler:
      return 0.0
    sched: Scheduler @ref = _requireScheduler()
    pc: int64 = sched.periodCount
    return float64(pc) * sched.period


type TaskPayloadOf[Value, _R = ...] = _R if Value is Task[_R] else Value

type GatherElemOf[Value, _U = ...] = (
  _U if Value is list[_U]
  else _U if Value is Task[list[_U]]
  else Value
)
