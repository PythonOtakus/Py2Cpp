from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
﻿"""``time`` 模块与 ``float64``/``int64`` 标量回归（时钟、``format_duration``、高精度算术）。"""

from py2cpp.system.time import (
  format_duration,
  monotonic,
  perf_counter,
  process_time,
  sleep,
  stopwatch,
  time,
)


class TimeEpochTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    t: float64 = time()
    self.assertTrue(t > 0.0)


class TimeMonotonicTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    a: float64 = monotonic()
    sleep(0.05)
    b: float64 = monotonic()
    self.assertTrue(b >= a)


class TimePerfCounterTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    a: float64 = perf_counter()
    sleep(0.05)
    b: float64 = perf_counter()
    self.assertTrue(b > a)


class TimeProcessTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    self.assertTrue(process_time() >= 0.0)


class TimeSleepNoopTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    sleep(-1.0)
    sleep(0.0)


class TimeFormatDurationTests(TestCaseMixin):
  _test_tag = 45

  @override
  def test(self):
    self.assertEqual(format_duration(2.5), "2.500000s")
    self.assertEqual(format_duration(0.05), "50.000ms")
    self.assertEqual(format_duration(0.00005), "50.000us")
    self.assertEqual(format_duration(0.0000005), "500.000ns")


class TimeStopwatchTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    with stopwatch():
      pass
    with stopwatch("sleep_block"):
      sleep(0.05)
    self.assertTrue(True)


class Int64LiteralTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    n: int64 = 10000000000
    self.assertEqual(n, 10000000000)
    m: int64 = n + 1
    self.assertEqual(m, 10000000001)


class Int64DivModTests(TestCaseMixin):
  _test_tag = 61

  @override
  def test(self):
    a: int64 = 10
    b: int64 = 3
    self.assertEqual(a // b, 3)
    self.assertEqual(a % b, 1)


class Float64ArithmeticTests(TestCaseMixin):
  _test_tag = 62

  @override
  def test(self):
    x: float64 = 1.0 / 3.0
    y: float64 = x * 3.0
    self.assertTrue(y > 0.99)
    self.assertTrue(y < 1.01)


class Scalar64MixedTests(TestCaseMixin):
  _test_tag = 63

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
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
