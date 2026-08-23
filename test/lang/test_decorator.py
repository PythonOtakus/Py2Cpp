from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
"""``@decorator`` 与 ``@context`` 回归。"""


@decorator
def repeat(count: int = 2):
  for i in range(count):
    yield


@context
def sample(begin: str = "begin", end: str = "end"):
  print(f"{begin} {__func__.__name__}()")
  yield
  print(f"{end} {__func__.__name__}()")


@repeat(3)
def func1():
  print("func1()")


@repeat
def func2():
  print("func2()")


@sample
def func3():
  print("func3()")


@sample("start", "stop")
def func4():
  print("func4()")


def func5():
  with sample:
    print("func5()")


def func6():
  with sample("start", "stop"):
    print("func6()")


class A:
  x: int = 0

  @repeat(3)
  def inc(self):
    self.x += 1

  @sample("start", "stop")
  def func(self):
    with sample:
      print("A.func()")


class DecoratorTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    a: A = new()
    self.assertEqual(a.x, 0)
    a.inc()
    self.assertEqual(a.x, 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
