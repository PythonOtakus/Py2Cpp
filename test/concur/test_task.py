"""``Task.run`` / ``Task.sleep`` / ``Task.create`` / ``Task.gather`` / ``Task.periodCount``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.concur.task import Task, LoopHandle
from py2cpp.concur.thread import Thread


_bufEntries: list[int] = []


async def tickLog(tag: int) -> int:
  _bufEntries.append(tag)
  await Task.sleep(0)
  _bufEntries.append(tag + 100)
  return tag


async def sleepTwoPeriods() -> int64:
  await Task.sleep(0.001)
  return Task.periodCount


async def gatherTwo() -> list[int]:
  a: Task[int] = Task.create(tickLog(1))
  b: Task[int] = Task.create(tickLog(2))
  return await Task.gather(a, b)


async def durationAfterTicks() -> float64:
  await Task.sleep(0)
  await Task.sleep(0)
  return Task.duration


def threadReturn123() -> int:
  return 123


def threadWorkerNotMain() -> int:
  current: Thread = Thread.current
  main: Thread = Thread.main
  if current.ident not in {0, main.ident}:
    return 1
  return 0


async def runThreadValue() -> int:
  return await Task.runThread(threadReturn123)


async def runThreadIdentity() -> int:
  return await Task.runThread(threadWorkerNotMain)


class TaskSleepZeroTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    _bufEntries.clear()
    Task.run(tickLog(1))
    self.assertEqual(len(_bufEntries), 2)
    self.assertEqual(_bufEntries[0], 1)
    self.assertEqual(_bufEntries[1], 101)


class TaskGatherTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    _bufEntries.clear()
    out: list[int] = Task.run(gatherTwo())
    self.assertEqual(len(out), 2)
    self.assertEqual(out[0], 1)
    self.assertEqual(out[1], 2)
    self.assertEqual(_bufEntries[0], 1)
    self.assertEqual(_bufEntries[1], 2)
    self.assertEqual(_bufEntries[2], 101)
    self.assertEqual(_bufEntries[3], 102)


class TaskPeriodCountTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    period: float64 = 0.01
    n: int64 = Task.run(sleepTwoPeriods(), period=period)
    self.assertEqual(n, 1)


class TaskDurationTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    period: float64 = 0.05
    d: float64 = Task.run(durationAfterTicks(), period=period)
    self.assertEqual(d, period * 2.0)


class TaskMultiRunTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    _bufEntries.clear()
    for _ in range(3):
      v: int = Task.run(tickLog(7))
      self.assertEqual(v, 7)
    self.assertEqual(len(_bufEntries), 6)


class TaskRunThreadTests(TestCaseMixin):
  _testTag = 6

  @override
  def test(self):
    self.assertEqual(Task.run(runThreadValue()), 123)
    self.assertEqual(Task.run(runThreadIdentity()), 1)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
