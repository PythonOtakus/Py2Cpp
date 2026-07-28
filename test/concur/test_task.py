"""``Task.run`` / ``Task.sleep`` / ``Task.create`` / ``Task.gather`` / ``Task.period_count``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.concur.task import Task, LoopHandle
from py2cpp.concur.thread import Thread


_buf_entries: list[int] = []


async def tick_log(tag: int) -> int:
  _buf_entries.append(tag)
  await Task.sleep(0)
  _buf_entries.append(tag + 100)
  return tag


async def sleep_two_periods() -> int64:
  await Task.sleep(0.001)
  return Task.period_count


async def gather_two() -> list[int]:
  a: Task[int] = Task.create(tick_log(1))
  b: Task[int] = Task.create(tick_log(2))
  return await Task.gather(a, b)


async def duration_after_ticks() -> float64:
  await Task.sleep(0)
  await Task.sleep(0)
  return Task.duration


def thread_return_123() -> int:
  return 123


def thread_worker_not_main() -> int:
  current: Thread = Thread.current
  main: Thread = Thread.main
  if current.ident not in {0, main.ident}:
    return 1
  return 0


async def run_thread_value() -> int:
  return await Task.run_thread(thread_return_123)


async def run_thread_identity() -> int:
  return await Task.run_thread(thread_worker_not_main)


class TaskSleepZeroTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    _buf_entries.clear()
    Task.run(tick_log(1))
    self.assertEqual(len(_buf_entries), 2)
    self.assertEqual(_buf_entries[0], 1)
    self.assertEqual(_buf_entries[1], 101)


class TaskGatherTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    _buf_entries.clear()
    out: list[int] = Task.run(gather_two())
    self.assertEqual(len(out), 2)
    self.assertEqual(out[0], 1)
    self.assertEqual(out[1], 2)
    self.assertEqual(_buf_entries[0], 1)
    self.assertEqual(_buf_entries[1], 2)
    self.assertEqual(_buf_entries[2], 101)
    self.assertEqual(_buf_entries[3], 102)


class TaskPeriodCountTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    period: float64 = 0.01
    n: int64 = Task.run(sleep_two_periods(), period=period)
    self.assertEqual(n, 1)


class TaskDurationTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    period: float64 = 0.05
    d: float64 = Task.run(duration_after_ticks(), period=period)
    self.assertEqual(d, period * 2.0)


class TaskMultiRunTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    _buf_entries.clear()
    for _ in range(3):
      v: int = Task.run(tick_log(7))
      self.assertEqual(v, 7)
    self.assertEqual(len(_buf_entries), 6)


class TaskRunThreadTests(TestCaseMixin):
  _test_tag = 6

  @override
  def test(self):
    self.assertEqual(Task.run(run_thread_value()), 123)
    self.assertEqual(Task.run(run_thread_identity()), 1)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
