"""函数形参 / 返回类型 ``T @Desc(...)``：内联 ``__set__`` 校验。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


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


@descriptor
class ReplaceIfBadVar:
  def __init__(self, lo: int, hi: int, bad: int):
    self._lo = lo
    self._hi = hi
    self._bad = bad

  def __get__(self):
    ...

  def __set__(self, value: int):
    if value < self._lo or value > self._hi:
      self.__value__ = self._bad


def clampedId(x: int @ClampedIntVar(0, 100)) -> int @ClampedIntVar(0, 100):
  return x + 1


class Service:
  @staticmethod
  def pick(n: int @ClampedIntVar(1, 5)) -> int @ClampedIntVar(1, 5):
    return n * 2

  def store(self, v: int @ReplaceIfBadVar(0, 9, -1)) -> None:
    self._v = v

  def level(self) -> int:
    return self._v

  _v: int = 0


class FuncDescriptorParamTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(clampedId(10), 11)
    self.assertEqual(clampedId(50), 51)


class FuncDescriptorReturnValidateTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    # 返回路径同样走 ClampedIntVar(0,100)；越界在译器单测中断言 throw
    self.assertEqual(clampedId(99), 100)


class FuncDescriptorStaticTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    self.assertEqual(Service.pick(2), 4)


class FuncDescriptorReplaceTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    svc: Service = new()
    svc.store(99)
    self.assertEqual(svc.level(), -1)
    svc.store(3)
    self.assertEqual(svc.level(), 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
