"""``util.array``：堆/SSO 缓冲与 ``list`` 底层 ``_data``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class HeapArrayTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    buf: int[:] = new(4)
    buf[0] = 1
    buf[1] = 2
    buf[2] = 3
    buf[3] = 4
    self.assertEqual(len(buf), 4)
    self.assertEqual(buf[0] + buf[3], 5)


class BuiltinAllocTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    p: Pointer[int] = allocArray[int](3)
    init(p, 7)
    init(p + 1, 8)
    init(p + 2, 9)
    self.assertEqual(p[0] + p[2], 16)
    freeArray(p)


class ArrayListTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    xs: list[int] = []
    xs.append(1)
    xs.append(2)
    self.assertEqual(len(xs), 2)
    self.assertEqual(xs[0] + xs[1], 3)


class ArraySsoTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    a: array[int, 4] = new(3)
    a[0] = 10
    a[1] = 20
    a[2] = 30
    self.assertEqual(len(a), 3)
    self.assertEqual(a[0] + a[2], 40)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
