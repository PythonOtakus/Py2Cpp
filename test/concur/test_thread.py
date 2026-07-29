"""``py2cpp.concur.thread`` 首版线程/Lock 回归。"""
from py2cpp import *
from py2cpp.concur.thread import (
  Barrier,
  BoundedSemaphore,
  BrokenBarrierError,
  CancelledError,
  Condition,
  Empty,
  Event,
  Full,
  Future,
  Lock,
  Queue,
  RLock,
  Semaphore,
  ShutDown,
  Thread,
  ThreadPool,
  TimeoutError,
  atomic,
)
from py2cpp.system.time import sleep
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@copyable
class Box:
  value: int = 0


_barrier_action_count: atomic[int] = new(0)
_pool_block_started: Event = new()
_pool_block_release: Event = new()
_pool_block_value: atomic[int] = new(0)


def set_box(box: Box) -> None:
  box.value = 42


def hold_lock(lock: Lock, box: Box) -> None:
  lock.acquire()
  box.value = 7
  sleep(0.02)
  lock.release()


def add_many(counter: atomic[int], times: int) -> None:
  for _i in range(times):
    counter.fetch_add(1)


def queue_consume(q: Queue[int], box: Box) -> None:
  box.value = q.get()
  q.task_done()


def queue_delayed_put(q: Queue[int], value: int) -> None:
  sleep(0.02)
  q.put(value)


def registry_worker(ready: Event, release: Event, box: Box) -> None:
  current: Thread = Thread.current
  if current.ident != 0 and current.native_id != 0 and Thread.active_count >= 2:
    box.value = 1
  ready.set()
  release.wait(timeout=1.0)


def rlock_release_from_other(lock: RLock, box: Box) -> None:
  try:
    lock.release()
  except RuntimeError:
    box.value = 1


def rlock_acquire_after_release(lock: RLock, box: Box) -> None:
  lock.acquire()
  box.value = 2
  lock.release()


def condition_waiter(cond: Condition, ready: Event, box: Box) -> None:
  cond.acquire()
  ready.set()
  if cond.wait(timeout=1.0):
    box.value = 11
  cond.release()


def condition_recursive_waiter(cond: Condition, ready: Event, box: Box) -> None:
  cond.acquire()
  cond.acquire()
  ready.set()
  if cond.wait(timeout=1.0):
    box.value = 22
  cond.release()
  cond.release()


def condition_set_flag(cond: Condition, box: Box) -> None:
  cond.acquire()
  box.value = 33
  cond.notify_all()
  cond.release()


def event_waiter(evt: Event, box: Box) -> None:
  if evt.wait(timeout=1.0):
    box.value = 44


def semaphore_waiter(sem: Semaphore, box: Box) -> None:
  sem.acquire()
  box.value = 55
  sem.release()


def barrier_waiter(barrier: Barrier @ref, ready: Event, done: Event, box: Box) -> None:
  ready.set()
  try:
    box.value = barrier.wait(timeout=1.0)
  except BrokenBarrierError:
    box.value = -1
  done.set()


def barrier_rounds_waiter(barrier: Barrier @ref, rounds: int, counter: atomic[int]) -> None:
  for _i in range(rounds):
    barrier.wait(timeout=1.0)
    counter.fetch_add(1)


def barrier_broken_waiter(barrier: Barrier @ref, ready: Event, box: Box) -> None:
  ready.set()
  try:
    barrier.wait(timeout=1.0)
  except BrokenBarrierError:
    box.value = 1


def barrier_global_action() -> None:
  _barrier_action_count.fetch_add(1)


def wait_barrier_waiting(barrier: Barrier @ref, n: int) -> bool:
  for _i in range(1000):
    if barrier.n_waiting == n:
      return True
    sleep(0.001)
  return barrier.n_waiting == n


def pool_return_21() -> int:
  return 21


def pool_return_1() -> int:
  return 1


def pool_return_99() -> int:
  return 99


def pool_block_global() -> int:
  _pool_block_started.set()
  _pool_block_release.wait(timeout=1.0)
  return _pool_block_value.load()


def pool_raise() -> int:
  raise RuntimeError("pool boom")
  return 0


class TLSBox:
  value: int @thread_local = 0

  def bump(self) -> int:
    self.value += 1
    return self.value


def set_tls_in_worker(box: Box) -> None:
  tls: TLSBox = new()
  TLSBox.value = 100
  box.value = tls.bump()


class ThreadBasicTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    box: Box = new()
    t: Thread = new(lambda: set_box(box))
    self.assertFalse(t.alive)
    t.start()
    self.assertTrue(t.ident != 0)
    self.assertTrue(t.native_id != 0)
    t.join()
    self.assertEqual(box.value, 42)
    self.assertFalse(t.alive)
    t.join()


class ThreadStartErrorTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    box: Box = new()
    t: Thread = new(lambda: set_box(box))
    raised: bool = False
    try:
      t.join()
    except RuntimeError:
      raised = True
    self.assertTrue(raised)
    t.start()
    raised = False
    try:
      t.start()
    except RuntimeError:
      raised = True
    self.assertTrue(raised)
    t.join()
    raised = False
    try:
      bad: Thread = new(lambda: set_box(box), daemon=True)
    except RuntimeError:
      raised = True
    self.assertTrue(raised)


class IdentTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    current: Thread = Thread.current
    self.assertTrue(current.ident != 0)
    self.assertTrue(current.native_id != 0)


class ThreadRegistryTests(TestCaseMixin):
  _test_tag = 35

  @override
  def test(self):
    main: Thread = Thread.main
    current: Thread = Thread.current
    self.assertEqual(main.ident, current.ident)
    self.assertEqual(current.ident, Thread.current.ident)
    self.assertEqual(main.name, "MainThread")
    self.assertTrue(Thread.active_count >= 1)

    found_main: bool = False
    threads: list[Thread] = Thread.actives
    for i in range(len(threads)):
      if threads[i].ident == current.ident:
        found_main = True
    self.assertTrue(found_main)

    ready: Event = new()
    release: Event = new()
    box: Box = new()
    worker: Thread = new(lambda: registry_worker(ready, release, box))
    worker.start()
    self.assertTrue(ready.wait(timeout=1.0))
    self.assertEqual(box.value, 1)
    worker_ident: int64 = worker.ident
    found_worker: bool = False
    worker_threads: list[Thread] = Thread.actives
    for i in range(len(worker_threads)):
      if worker_threads[i].ident == worker_ident:
        found_worker = True
    self.assertTrue(found_worker)
    release.set()
    worker.join()


class LockTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    lock: Lock = new()
    box: Box = new()
    self.assertTrue(lock.acquire())
    self.assertTrue(lock.locked())
    self.assertFalse(lock.acquire(blocking=False))
    t: Thread = new(lambda: hold_lock(lock, box))
    t.start()
    sleep(0.02)
    self.assertEqual(box.value, 0)
    lock.release()
    t.join()
    self.assertEqual(box.value, 7)
    self.assertFalse(lock.locked())
    raised: bool = False
    try:
      lock.release()
    except RuntimeError:
      raised = True
    self.assertTrue(raised)
    raised = False
    try:
      lock.acquire(blocking=False, timeout=0.1)
    except ValueError:
      raised = True
    self.assertTrue(raised)


class AtomicTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    counter: atomic[int] = new(0)
    self.assertEqual(counter.load(), 0)
    self.assertTrue(counter.compare_exchange(0, 5))
    self.assertFalse(counter.compare_exchange(0, 9))
    self.assertEqual(counter.exchange(1), 5)
    self.assertEqual(counter.fetch_add(2), 1)
    self.assertEqual(counter.fetch_sub(1), 3)
    self.assertEqual(counter.load(), 2)

    t1: Thread = new(lambda: add_many(counter, 50))
    t2: Thread = new(lambda: add_many(counter, 50))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    self.assertEqual(counter.load(), 102)


class QueueTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    q: Queue[int] = new(1)
    self.assertFalse(q)
    q.put_nowait(10)
    self.assertEqual(q.qsize(), 1)
    self.assertTrue(q)
    self.assertTrue(q.full())

    raised: bool = False
    try:
      q.put_nowait(20)
    except Full:
      raised = True
    self.assertTrue(raised)

    self.assertEqual(q.get_nowait(), 10)
    q.task_done()
    q.join()
    self.assertFalse(q)

    raised = False
    try:
      q.get_nowait()
    except Empty:
      raised = True
    self.assertTrue(raised)

    box: Box = new()
    t: Thread = new(lambda: queue_consume(q, box))
    t.start()
    sleep(0.02)
    q.put(33)
    q.join()
    t.join()
    self.assertEqual(box.value, 33)

    q.put_nowait(44)
    q.shutdown()
    self.assertEqual(q.get_nowait(), 44)
    q.task_done()
    raised = False
    try:
      q.get_nowait()
    except ShutDown:
      raised = True
    self.assertTrue(raised)

    raised = False
    try:
      q.put_nowait(55)
    except ShutDown:
      raised = True
    self.assertTrue(raised)


class QueueBlockingTests(TestCaseMixin):
  _test_tag = 70

  @override
  def test(self):
    q: Queue[int] = new()
    t: Thread = new(lambda: queue_delayed_put(q, 77))
    t.start()
    self.assertEqual(q.get(timeout=1.0), 77)
    q.task_done()
    q.join()
    t.join()


class ThreadLocalTests(TestCaseMixin):
  _test_tag = 80

  @override
  def test(self):
    tls: TLSBox = new()
    TLSBox.value = 5
    self.assertEqual(tls.bump(), 6)
    self.assertEqual(TLSBox.value, 6)

    box: Box = new()
    t: Thread = new(lambda: set_tls_in_worker(box))
    t.start()
    t.join()
    self.assertEqual(box.value, 101)
    self.assertEqual(TLSBox.value, 6)


class RLockTests(TestCaseMixin):
  _test_tag = 90

  @override
  def test(self):
    lock: RLock = new()
    self.assertTrue(lock.acquire())
    self.assertTrue(lock.acquire())
    self.assertTrue(lock.locked())

    box: Box = new()
    release_thread: Thread = new(lambda: rlock_release_from_other(lock, box))
    release_thread.start()
    release_thread.join()
    self.assertEqual(box.value, 1)

    acquire_thread: Thread = new(lambda: rlock_acquire_after_release(lock, box))
    acquire_thread.start()
    sleep(0.02)
    self.assertEqual(box.value, 1)
    lock.release()
    sleep(0.02)
    self.assertEqual(box.value, 1)
    lock.release()
    acquire_thread.join()
    self.assertEqual(box.value, 2)
    self.assertFalse(lock.locked())

    raised: bool = False
    try:
      lock.release()
    except RuntimeError:
      raised = True
    self.assertTrue(raised)


class ConditionTests(TestCaseMixin):
  _test_tag = 100

  @override
  def test(self):
    cond: Condition = new()
    ready: Event = new()
    box: Box = new()
    waiter: Thread = new(lambda: condition_waiter(cond, ready, box))
    waiter.start()
    self.assertTrue(ready.wait(timeout=1.0))
    cond.acquire()
    cond.notify()
    self.assertEqual(box.value, 0)
    cond.release()
    waiter.join()
    self.assertEqual(box.value, 11)

    # RLock 递归层数经过 wait 后应恢复。
    ready2: Event = new()
    recursive_box: Box = new()
    recursive_waiter: Thread = new(lambda: condition_recursive_waiter(cond, ready2, recursive_box))
    recursive_waiter.start()
    self.assertTrue(ready2.wait(timeout=1.0))
    cond.acquire()
    cond.notify_all()
    cond.release()
    recursive_waiter.join()
    self.assertEqual(recursive_box.value, 22)

    # wait_for 在持锁状态循环等待谓词。
    flag: Box = new()
    cond.acquire()
    setter: Thread = new(lambda: condition_set_flag(cond, flag))
    setter.start()
    self.assertTrue(cond.wait_for(lambda: flag.value == 33, timeout=1.0))
    cond.release()
    setter.join()

    raised: bool = False
    try:
      cond.notify()
    except RuntimeError:
      raised = True
    self.assertTrue(raised)


class EventTests(TestCaseMixin):
  _test_tag = 110

  @override
  def test(self):
    evt: Event = new()
    self.assertFalse(evt.is_set())
    self.assertFalse(evt.wait(timeout=0.01))
    evt.set()
    self.assertTrue(evt.is_set())
    self.assertTrue(evt.wait(timeout=0.0))
    evt.clear()
    self.assertFalse(evt.is_set())

    box: Box = new()
    waiter: Thread = new(lambda: event_waiter(evt, box))
    waiter.start()
    sleep(0.02)
    self.assertEqual(box.value, 0)
    evt.set()
    waiter.join()
    self.assertEqual(box.value, 44)


class SemaphoreTests(TestCaseMixin):
  _test_tag = 120

  @override
  def test(self):
    sem: Semaphore = new(1)
    self.assertTrue(sem.acquire())
    self.assertFalse(sem.acquire(blocking=False))

    box: Box = new()
    waiter: Thread = new(lambda: semaphore_waiter(sem, box))
    waiter.start()
    sleep(0.02)
    self.assertEqual(box.value, 0)
    sem.release()
    waiter.join()
    self.assertEqual(box.value, 55)

    raised: bool = False
    try:
      sem.release(0)
    except ValueError:
      raised = True
    self.assertTrue(raised)

    raised = False
    try:
      bad: Semaphore = new(-1)
    except ValueError:
      raised = True
    self.assertTrue(raised)


class BoundedSemaphoreTests(TestCaseMixin):
  _test_tag = 130

  @override
  def test(self):
    sem: BoundedSemaphore = new(1)
    raised: bool = False
    try:
      sem.release()
    except ValueError:
      raised = True
    self.assertTrue(raised)

    self.assertTrue(sem.acquire())
    sem.release()
    raised = False
    try:
      sem.release()
    except ValueError:
      raised = True
    self.assertTrue(raised)


class BarrierTests(TestCaseMixin):
  _test_tag = 140

  @override
  def test(self):
    # Windows 下前序线程测试刚结束时，立刻启动 barrier 双线程轮次偶发触发
    # native thread/condition_variable 清理窗口；短暂让出调度可避免测试竞态。
    sleep(0.01)
    barrier: Barrier = new(2)
    self.assertEqual(barrier.parties, 2)

    ready: Event = new()
    done: Event = new()
    box: Box = new()
    waiter: Thread = new(lambda: barrier_waiter(barrier, ready, done, box))
    waiter.start()
    self.assertTrue(ready.wait(timeout=1.0))
    self.assertTrue(wait_barrier_waiting(barrier, 1))
    main_index: int = barrier.wait(timeout=1.0)
    self.assertTrue(done.wait(timeout=1.0))
    waiter.join()
    self.assertEqual(main_index + box.value, 1)
    self.assertFalse(barrier.broken)
    self.assertEqual(barrier.n_waiting, 0)

    # barrier 可以多轮复用。
    rounds: int = 3
    counter: atomic[int] = new(0)
    loop_waiter: Thread = new(lambda: barrier_rounds_waiter(barrier, rounds, counter))
    loop_waiter.start()
    for _i in range(rounds):
      barrier.wait(timeout=1.0)
    loop_waiter.join()
    self.assertEqual(counter.load(), rounds)

    # action 只由最后到达者执行一次。
    _barrier_action_count.store(0)
    action_barrier: Barrier = new(2, barrier_global_action)
    action_ready: Event = new()
    action_done: Event = new()
    action_box: Box = new()
    action_waiter: Thread = new(lambda: barrier_waiter(action_barrier, action_ready, action_done, action_box))
    action_waiter.start()
    self.assertTrue(action_ready.wait(timeout=1.0))
    self.assertTrue(wait_barrier_waiting(action_barrier, 1))
    action_barrier.wait(timeout=1.0)
    self.assertTrue(action_done.wait(timeout=1.0))
    action_waiter.join()
    self.assertEqual(_barrier_action_count.load(), 1)

    # timeout 会打破 barrier，reset 后恢复可用。
    timeout_barrier: Barrier = new(2)
    raised: bool = False
    try:
      timeout_barrier.wait(timeout=0.01)
    except BrokenBarrierError:
      raised = True
    self.assertTrue(raised)
    self.assertTrue(timeout_barrier.broken)
    timeout_barrier.reset()
    self.assertFalse(timeout_barrier.broken)

    # reset 使当前 waiter 失败，但 barrier 本身回到 filling。
    reset_barrier: Barrier = new(2)
    reset_ready: Event = new()
    reset_box: Box = new()
    reset_waiter: Thread = new(lambda: barrier_broken_waiter(reset_barrier, reset_ready, reset_box))
    reset_waiter.start()
    self.assertTrue(reset_ready.wait(timeout=1.0))
    self.assertTrue(wait_barrier_waiting(reset_barrier, 1))
    reset_barrier.reset()
    reset_waiter.join()
    self.assertEqual(reset_box.value, 1)
    self.assertFalse(reset_barrier.broken)

    # abort 会永久打破 barrier。
    abort_barrier: Barrier = new(2)
    abort_ready: Event = new()
    abort_box: Box = new()
    abort_waiter: Thread = new(lambda: barrier_broken_waiter(abort_barrier, abort_ready, abort_box))
    abort_waiter.start()
    self.assertTrue(abort_ready.wait(timeout=1.0))
    abort_barrier.abort()
    abort_waiter.join()
    self.assertEqual(abort_box.value, 1)
    self.assertTrue(abort_barrier.broken)
    raised = False
    try:
      abort_barrier.wait(timeout=0.01)
    except BrokenBarrierError:
      raised = True
    self.assertTrue(raised)


class ThreadPoolTests(TestCaseMixin):
  _test_tag = 150

  @override
  def test(self):
    pool: ThreadPool[int] = new(2)
    future: Future[int] = pool.submit(pool_return_21)
    self.assertEqual(future.result(timeout=1.0), 21)
    self.assertTrue(future.done())
    self.assertFalse(future.cancelled())
    self.assertFalse(future.exception(timeout=0.0))
    pool.shutdown()

    raised: bool = False
    try:
      pool.submit(pool_return_1)
    except RuntimeError:
      raised = True
    self.assertTrue(raised)

    # result(timeout) 超时后仍可继续等待最终结果。
    timeout_pool: ThreadPool[int] = new(1)
    _pool_block_started.clear()
    _pool_block_release.clear()
    _pool_block_value.store(5)
    slow: Future[int] = timeout_pool.submit(pool_block_global)
    self.assertTrue(_pool_block_started.wait(timeout=1.0))
    raised = False
    try:
      slow.result(timeout=0.01)
    except TimeoutError:
      raised = True
    self.assertTrue(raised)
    self.assertFalse(slow.cancel())
    _pool_block_release.set()
    self.assertEqual(slow.result(timeout=1.0), 5)
    timeout_pool.shutdown()

    # cancel_futures / cancel 只影响尚未开始的任务。
    cancel_pool: ThreadPool[int] = new(1)
    _pool_block_started.clear()
    _pool_block_release.clear()
    _pool_block_value.store(11)
    first: Future[int] = cancel_pool.submit(pool_block_global)
    self.assertTrue(_pool_block_started.wait(timeout=1.0))
    second: Future[int] = cancel_pool.submit(pool_return_99)
    self.assertTrue(second.cancel())
    _pool_block_release.set()
    self.assertEqual(first.result(timeout=1.0), 11)
    raised = False
    try:
      second.result(timeout=0.0)
    except CancelledError:
      raised = True
    self.assertTrue(raised)
    cancel_pool.shutdown()

    # 任务异常被 Future 标记，result 读取时抛 RuntimeError。
    error_pool: ThreadPool[int] = new(1)
    failed: Future[int] = error_pool.submit(pool_raise)
    raised = False
    try:
      failed.result(timeout=1.0)
    except RuntimeError:
      raised = True
    self.assertTrue(raised)
    self.assertTrue(failed.exception(timeout=0.0))
    error_pool.shutdown()


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
