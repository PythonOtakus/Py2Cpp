"""``T[:N]`` / ``T[i:j]`` → ``PyStackArray``；``buf[i:j]`` → ``PyArray``；``buf.view[i:j]`` → ``span``。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def sumStack(buf: int[:4]) -> int:
  total: int = 0
  for i in range(len(buf)):
    total += buf[i]
  return total


def sumStackFor(buf: int[:4]) -> int:
  total: int = 0
  for x in buf:
    total += x
  return total


def sumOffsetFor(seg: int[1:3]) -> int:
  total: int = 0
  for x in seg:
    total += x
  return total


def sumSlice(seg: int[:]) -> int:
  return seg[0] + seg[1]


def sumView(seg: int[1:3]) -> int:
  return seg[1] + seg[2]


def sumSpan(seg: span[int]) -> int:
  return seg[0] + seg[1]


def sumSpanFor(seg: span[int]) -> int:
  total: int = 0
  for x in seg:
    total += x
  return total


class StackArrayLocalTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    buf: int[:4] = [10, 20, 30, 40]
    self.assertEqual(len(buf), 4)
    self.assertEqual(buf[0], 10)
    self.assertEqual(buf[1] + buf[3], 60)
    self.assertEqual(sumStack(buf), 100)
    self.assertEqual(sumStackFor(buf), 100)


class StackArrayForTests(TestCaseMixin):
  _testTag = 8

  @override
  def test(self):
    view: int[1:3] = [20, 30]
    self.assertEqual(sumOffsetFor(view), 50)
    acc: int = 0
    for x in view:
      acc += x
    self.assertEqual(acc, 50)


class StackArrayLen3Tests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    raw: int[:3] = new()
    raw[0] = 1
    raw[1] = 2
    raw[2] = 3
    self.assertEqual(len(raw), 3)
    self.assertEqual(raw[0] + raw[2], 4)


class StackArrayHeapSliceTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    buf: int[:4] = new()
    buf[0] = 10
    buf[1] = 20
    buf[2] = 30
    buf[3] = 40
    sub: int[:] = buf[1:3]
    self.assertEqual(len(sub), 2)
    self.assertEqual(sub[0], 20)
    self.assertEqual(sub[1], 30)
    self.assertEqual(sumSlice(sub), 50)
    tail: int[:] = buf[2:4]
    self.assertEqual(len(tail), 2)
    self.assertEqual(tail[0] + tail[1], 70)
    buf[1] = 99
    self.assertEqual(sub[0], 20)


class StackArraySpanViewTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    buf: int[:4] = new()
    buf[0] = 10
    buf[1] = 20
    buf[2] = 30
    buf[3] = 40
    vw: span[int] = buf.view
    sub: span[int] = vw[1:3]
    self.assertEqual(len(sub), 2)
    self.assertEqual(sub[0], 20)
    self.assertEqual(sub[1], 30)
    self.assertEqual(sumSpan(sub), 50)
    buf[1] = 99
    self.assertEqual(sub[0], 99)
    whole: span[int] = buf.view
    self.assertEqual(len(whole), 4)
    self.assertEqual(whole[0] + whole[3], 50)
    stride: span[int] = whole[:4:2]
    self.assertEqual(len(stride), 2)
    self.assertEqual(stride[0] + stride[1], 40)
    sub[0] = 55
    self.assertEqual(buf[1], 55)
    self.assertEqual(sub.at()[0], 55)


class StackArraySpanForTests(TestCaseMixin):
  _testTag = 7

  @override
  def test(self):
    buf: int[:4] = new()
    buf[0] = 10
    buf[1] = 20
    buf[2] = 30
    buf[3] = 40
    whole: span[int] = buf.view
    self.assertEqual(sumSpanFor(whole), 100)
    sub: span[int] = whole[1:3]
    self.assertEqual(sumSpanFor(sub), 50)
    acc: int = 0
    for x in sub:
      acc += x
    self.assertEqual(acc, 50)
    vw2: span[int] = buf.view
    tail: span[int] = vw2[2:4]
    self.assertEqual(sumSpanFor(tail), 70)
    sub[1] = 88
    self.assertEqual(buf[2], 88)
    self.assertEqual(tail[0], 88)


class StackArraySubsliceAnnTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    view: int[1:3] = [20, 30]
    self.assertEqual(sumView(view), 50)


class StackArrayZeroOffsetSliceTests(TestCaseMixin):
  _testTag = 6

  @override
  def test(self):
    buf: int[:3] = new()
    buf[0] = 5
    buf[1] = 6
    buf[2] = 7
    head: int[:] = buf[:2]
    self.assertEqual(head[0] + head[1], 11)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
