"""``T @lazy`` 形参：惰性 default、first-touch memo、supplier 透传。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@copyable
@dataclass
class SideEffectCounter:
  n: int = 0


def _lazy_bump(c: SideEffectCounter) -> int:
  c.n += 1
  return c.n


def _wrap_get(d: dict[int, int], key: int, default: int @lazy = None) -> int:
  return d.get(key, default)


def _pick(d: dict[int, int], key: int, default: int @lazy = 77) -> int:
  return d.get(key, default)


def _default_88() -> int:
  return 88


def _pick_factory_default(d: dict[int, int], key: int, default: int @lazy = _default_88()) -> int:
  return d.get(key, default)


class LazyParamSkipDefaultTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    c: SideEffectCounter = new()
    d: dict[int, int] = {10: 100}
    self.assertEqual(d.get(10, _lazy_bump(c)), 100)
    self.assertEqual(c.n, 0)


class LazyParamRunDefaultTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    c: SideEffectCounter = new()
    d: dict[int, int] = {10: 100}
    self.assertEqual(_wrap_get(d, 99, _lazy_bump(c)), 1)
    self.assertEqual(c.n, 1)


class LazyParamLiteralDefaultTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    d: dict[int, int] = {1: 2}
    self.assertEqual(d.get(9, 0), 0)


class LazyParamMissingArgTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    d: dict[int, int] = {1: 2}
    v: int = d.get(9)
    self.assertEqual(v, 0)


class LazyParamForwardTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    c: SideEffectCounter = new()
    d: dict[int, int] = {5: 50}
    self.assertEqual(_wrap_get(d, 5, _lazy_bump(c)), 50)
    self.assertEqual(c.n, 0)
    self.assertEqual(_wrap_get(d, 1, _lazy_bump(c)), 1)
    self.assertEqual(c.n, 1)


class LazyParamNonNoneDefaultTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    d: dict[int, int] = {1: 2}
    self.assertEqual(_pick(d, 9), 77)
    self.assertEqual(_pick(d, 1), 2)
    self.assertEqual(_pick(d, 9, 0), 0)


class LazyParamNonNoneExprDefaultTests(TestCaseMixin):
  _test_tag = 70

  @override
  def test(self):
    d: dict[int, int] = {3: 30}
    self.assertEqual(_pick_factory_default(d, 9), 88)
    self.assertEqual(_pick_factory_default(d, 3), 30)


class LazyParamNonNoneSkipSideEffectTests(TestCaseMixin):
  _test_tag = 80

  @override
  def test(self):
    c: SideEffectCounter = new()
    d: dict[int, int] = {10: 100}
    self.assertEqual(_pick(d, 10, _lazy_bump(c)), 100)
    self.assertEqual(c.n, 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
