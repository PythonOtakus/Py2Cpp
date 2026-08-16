"""``T @lazy`` 形参：惰性 default、first-touch memo、supplier 透传。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@copyable
@dataclass
class SideEffectCounter:
  n: int = 0


def _lazyBump(c: SideEffectCounter) -> int:
  c.n += 1
  return c.n


def _wrapGet(d: dict[int, int], key: int, default: int @lazy = None) -> int:
  return d.get(key, default)


def _pick(d: dict[int, int], key: int, default: int @lazy = 77) -> int:
  return d.get(key, default)


def _default88() -> int:
  return 88


def _pickFactoryDefault(d: dict[int, int], key: int, default: int @lazy = _default88()) -> int:
  return d.get(key, default)


class LazyParamSkipDefaultTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    c: SideEffectCounter = new()
    d: dict[int, int] = {10: 100}
    self.assertEqual(d.get(10, _lazyBump(c)), 100)
    self.assertEqual(c.n, 0)


class LazyParamRunDefaultTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    c: SideEffectCounter = new()
    d: dict[int, int] = {10: 100}
    self.assertEqual(_wrapGet(d, 99, _lazyBump(c)), 1)
    self.assertEqual(c.n, 1)


class LazyParamLiteralDefaultTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    d: dict[int, int] = {1: 2}
    self.assertEqual(d.get(9, 0), 0)


class LazyParamMissingArgTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    d: dict[int, int] = {1: 2}
    v: int = d.get(9)
    self.assertEqual(v, 0)


class LazyParamForwardTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    c: SideEffectCounter = new()
    d: dict[int, int] = {5: 50}
    self.assertEqual(_wrapGet(d, 5, _lazyBump(c)), 50)
    self.assertEqual(c.n, 0)
    self.assertEqual(_wrapGet(d, 1, _lazyBump(c)), 1)
    self.assertEqual(c.n, 1)


class LazyParamNonNoneDefaultTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    d: dict[int, int] = {1: 2}
    self.assertEqual(_pick(d, 9), 77)
    self.assertEqual(_pick(d, 1), 2)
    self.assertEqual(_pick(d, 9, 0), 0)


class LazyParamNonNoneExprDefaultTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    d: dict[int, int] = {3: 30}
    self.assertEqual(_pickFactoryDefault(d, 9), 88)
    self.assertEqual(_pickFactoryDefault(d, 3), 30)


class LazyParamNonNoneSkipSideEffectTests(TestCaseMixin):
  _testTag = 80

  @override
  def test(self):
    c: SideEffectCounter = new()
    d: dict[int, int] = {10: 100}
    self.assertEqual(_pick(d, 10, _lazyBump(c)), 100)
    self.assertEqual(c.n, 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
