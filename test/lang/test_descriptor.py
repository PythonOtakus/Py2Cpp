"""``@descriptor`` 内联到宿主类：占位 ``...``、构造期绑定、校验逻辑。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@descriptor
class PlainValueVar:
  def __get__(self):
    ...

  def __set__(self, value: int):
    ...


@descriptor
class ClampedIntVar:
  def __init__(self, lo: int, hi: int):
    self._lo = lo
    self._hi = hi

  def __get__(self):
    ...

  def __set__(self, value: int):
    if value < self._lo or value > self._hi:
      raise ValueError("out of range")
    self.__value__ = value


@descriptor
class OffsetValueVar:
  def __init__(self, base: int):
    self._base = base

  def __get__(self) -> int:
    return self._base + self.__value__

  def __set__(self, value: int):
    self.__value__ = value


class HostPlain:
  score: int @PlainValueVar() = 0


class HostClamped:
  level: int @ClampedIntVar(0, 10) = 0


class HostOffset:
  value: int @OffsetValueVar(100) = 50


class PlainDescriptorTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    # PlainValueVar：``...`` 展开为读写 ``score__value``
    box: HostPlain = new()
    self.assertEqual(box.score, 0)
    box.score = 5
    self.assertEqual(box.score, 5)


class ClampedDescriptorTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    # ClampedIntVar(0,10)：界内读写；边界 0 / 10
    row: HostClamped = new()
    row.level = 7
    self.assertEqual(row.level, 7)
    row.level = 0
    self.assertEqual(row.level, 0)
    row.level = 10
    self.assertEqual(row.level, 10)


class OffsetDescriptorTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    # OffsetValueVar(100) + 默认存储 50：读为 base + value__value；写入后 100+3
    item: HostOffset = new()
    self.assertEqual(item.value, 150)
    item.value = 3
    self.assertEqual(item.value, 103)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
