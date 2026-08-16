from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
﻿"""``time`` 模块与 ``float64``/``int64`` 标量回归（时钟、``formatDuration``、高精度算术）。"""

from py2cpp.system.time import (
  formatDuration,
  monotonic,
  perfCounter,
  processTime,
  sleep,
  stopwatch,
  time,
)


class TimeEpochTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    t: float64 = time()
    self.assertTrue(t > 0.0)


class TimeMonotonicTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    a: float64 = monotonic()
    sleep(0.05)
    b: float64 = monotonic()
    self.assertTrue(b >= a)


class TimePerfCounterTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    a: float64 = perfCounter()
    sleep(0.05)
    b: float64 = perfCounter()
    self.assertTrue(b > a)


class TimeProcessTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    self.assertTrue(processTime() >= 0.0)


class TimeSleepNoopTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    sleep(-1.0)
    sleep(0.0)


class TimeFormatDurationTests(TestCaseMixin):
  _testTag = 45

  @override
  def test(self):
    self.assertEqual(formatDuration(2.5), "2.500000s")
    self.assertEqual(formatDuration(0.05), "50.000ms")
    self.assertEqual(formatDuration(0.00005), "50.000us")
    self.assertEqual(formatDuration(0.0000005), "500.000ns")


class TimeStopwatchTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    with stopwatch():
      pass
    with stopwatch("sleep_block"):
      sleep(0.05)
    self.assertTrue(True)


class Int64LiteralTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    n: int64 = 10000000000
    self.assertEqual(n, 10000000000)
    m: int64 = n + 1
    self.assertEqual(m, 10000000001)


class Int64DivModTests(TestCaseMixin):
  _testTag = 61

  @override
  def test(self):
    a: int64 = 10
    b: int64 = 3
    self.assertEqual(a // b, 3)
    self.assertEqual(a % b, 1)


class Float64ArithmeticTests(TestCaseMixin):
  _testTag = 62

  @override
  def test(self):
    x: float64 = 1.0 / 3.0
    y: float64 = x * 3.0
    self.assertTrue(y > 0.99)
    self.assertTrue(y < 1.01)


class Scalar64MixedTests(TestCaseMixin):
  _testTag = 63

  @override
  def test(self):
    i: int = 5
    n: int64 = 10000000000
    q: int64 = i + n
    self.assertEqual(q, 10000000005)
    f: float = 0.5
    d: float64 = 2.0
    r: float64 = f * d
    self.assertTrue(r > 0.99)
    self.assertTrue(r < 1.01)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
