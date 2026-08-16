"""``@mixin``：实例字段/方法内联、混入 ``static const``、``TestCaseMixin`` 发现顺序。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Base:
  def baseId(self) -> int:
    return 1


@mixin
class IncMixin:
  n: int = 0

  def inc(self) -> None:
    self.n += 1


class Host(IncMixin, Base):
  pass


class TaggedLow(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    self.assertEqual(self._testTag, 5)


class TaggedHigh(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    self.assertEqual(self._testTag, 50)


class MixinMethodTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    h: Host = new()
    self.assertEqual(h.baseId(), 1)
    h.inc()
    self.assertEqual(h.n, 1)


class MixinConstOverrideTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    # ``main`` 按 ``_testTag`` 升序跑用例：本类(2) 在 TaggedLow(5) 之前
    self.assertEqual(self._testTag, 2)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
