"""``Proxy[T]`` / ``super`` / ``Super`` 回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Widget:
  value: int

  def __init__(self, v: int = 0):
    self.value = v

  def greet(self) -> str:
    return "hi"

  def tag(self) -> str:
    return "w"


class CountingProxy[Element](Proxy[Element]):
  hits: int = 0

  @override
  def greet(self) -> str:
    self.hits += 1
    return "log:" + super.greet()


class Base:
  n: int = 1

  def __call__(self) -> Self:
    return self

  @virtual
  def inc(self) -> int:
    self.n += 1
    return self.n


class Derived(Base):
  @override
  def inc(self) -> int:
    return super.inc() + 10


class DerivedCall(Base):
  @override
  def inc(self) -> int:
    return super().inc() + 10


class ProxyTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    w: Widget = new(1)
    p: Proxy[Widget] = new(w)
    self.assertEqual(p.greet(), "hi")
    self.assertEqual(p.tag(), "w")
    self.assertEqual(p.value, 1)
    p.value = 3
    self.assertEqual(p.value, 3)
    self.assertEqual(w.value, 1)

    cp: CountingProxy[Widget] = new(w)
    self.assertEqual(cp.greet(), "log:hi")
    self.assertEqual(cp.hits, 1)
    self.assertEqual(cp.tag(), "w")
    self.assertEqual(cp.greet(), "log:hi")
    self.assertEqual(cp.hits, 2)

    d: Derived = new()
    self.assertEqual(d.inc(), 12)
    self.assertEqual(d.n, 2)
    dc: DerivedCall = new()
    self.assertEqual(dc.inc(), 12)
    self.assertEqual(dc.n, 2)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
