"""``yield`` / ``yield from`` / ``send`` / ``return``（``GeneratorType[Y,S,R]``）；``for`` / ``else`` / ``continue``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def genThree() -> GeneratorType[int, None, None]:
  yield 1
  yield 2
  yield 3


def genRange(n: int) -> GeneratorType[int, None, None]:
  counter: int = 0
  while counter < n:
    yield counter
    counter += 1


def genFromList(xs: list[int]) -> GeneratorType[int, None, None]:
  yield from xs


def genInnerReturn() -> GeneratorType[int, None, int]:
  yield 10
  return 42


def genYieldFromReturn() -> GeneratorType[int, None, None]:
  ret: int = yield from genInnerReturn()
  yield ret


def genEcho() -> GeneratorType[int, int, None]:
  while True:
    received = yield 0
    if received < 0:
      break
    yield received * 2


def genWithReturn() -> GeneratorType[int, None, int]:
  yield 1
  yield 2
  return 99


def genForElseTail() -> GeneratorType[int, None, None]:
  """``for`` 正常结束 → ``else``；循环内 ``yield``。"""
  for i in range(3):
    yield i
  else:
    yield 100


def genForElseSkipOnBreak() -> GeneratorType[int, None, None]:
  """``break`` 时 ``else`` 不执行；循环内 ``yield`` + ``break`` 前收尾 ``yield``。"""
  for i in range(10):
    yield i
    if i == 2:
      yield 1
      break
  else:
    yield 100


def genForElseSkipOnBreakYf() -> GeneratorType[int, None, None]:
  """``break`` + 循环内 ``yield from``（``else`` 仍不执行）。"""
  extras: list[int] = []
  extras.append(70)
  extras.append(71)
  for i in range(5):
    yield i
    if i == 2:
      yield from extras
      yield 1
      break
  else:
    yield 100


def genForContinueAcc() -> GeneratorType[int, None, None]:
  """``for`` + ``continue`` + 循环内 ``yield``；末 ``yield`` 汇总 ``acc``。"""
  acc: int = 0
  for i in range(6):
    if i == 2:
      continue
    acc += i
    yield i
  yield acc


def genForContinueAccYf() -> GeneratorType[int, None, None]:
  """``continue`` + ``i==4`` 时 ``yield from`` 列表，末 ``yield acc``。"""
  acc: int = 0
  pair: list[int] = []
  pair.append(0)
  pair.append(0)
  for i in range(5):
    if i == 2:
      continue
    acc += i
    if i != 4:
      yield i
    if i == 4:
      pair[0] = acc
      pair[1] = acc + 1
      yield from pair
  yield acc


def genWhileElse() -> GeneratorType[int, None, None]:
  """``while`` 正常结束 → ``else`` 执行（循环体内无 ``yield``）。"""
  n: int = 2
  while n > 0:
    n -= 1
  else:
    yield 99


def genForYieldList(xs: list[int]) -> GeneratorType[int, None, None]:
  """``yield from`` 委托列表迭代（同 ``genFromList``）。"""
  yield from xs


def genForIfElseYield() -> GeneratorType[int, None, None]:
  """``for``-``else`` + ``if``/``else`` 两分支均 ``yield``。"""
  for i in range(4):
    if i % 2 == 0:
      yield i
    else:
      yield i + 100
  else:
    yield 200


def genForElseIfBreak() -> GeneratorType[int, None, None]:
  """``for``-``else`` + 分段 ``if`` + ``break`` + 多段 ``yield``。"""
  for i in range(4):
    if i < 2:
      yield i
    if i == 2:
      yield 20
      yield 21
      break
  else:
    yield 900


def genForElseBranchMix() -> GeneratorType[int, None, None]:
  """``continue`` / ``yield from`` / ``break`` / ``else`` 分段 ``if`` 交错。"""
  subs: list[int] = []
  subs.append(40)
  subs.append(41)
  for i in range(5):
    if i == 0:
      yield i
    elif i == 1:
      continue
    elif i == 2:
      yield from subs
    elif i == 3:
      yield 300
      break
  else:
    yield 600


def genNestedWhileContinueYf() -> GeneratorType[int, None, None]:
  """``while``-``else`` + ``continue`` + ``yield from`` + 普通 ``yield``。"""
  chunk: list[int] = []
  chunk.append(5)
  chunk.append(6)
  n: int = 0
  while n < 4:
    if n == 1:
      n += 1
      continue
    if n == 2:
      yield from chunk
    else:
      yield n
    n += 1
  else:
    yield 77


def genNestedForInnerBreakYf() -> GeneratorType[int, None, None]:
  """外层 ``for``-``else`` + 内层 ``for`` + ``continue``/``yield from`` + 外层 ``break``。"""
  inner: list[int] = []
  inner.append(8)
  inner.append(9)
  for i in range(6):
    yield i
    if i == 1:
      for j in range(3):
        if j == 0:
          continue
        if j == 1:
          yield from inner
        else:
          yield 100 + j
      break
  else:
    yield 999


def genWhileElseIfBreakYield() -> GeneratorType[int, None, None]:
  """``while``-``else`` + ``if`` + ``break`` + 条件 ``yield``。"""
  k: int = 0
  while k < 5:
    if k == 3:
      break
    if k == 2:
      yield k * 100
    else:
      yield k
    k += 1
  else:
    yield 88


def genWhileContinueAcc() -> GeneratorType[int, None, None]:
  """``while`` 内 ``continue`` + 多段 ``yield``（跳过 ``i==2`` 时须推进 ``i``，避免死循环）。"""
  i: int = 0
  acc: int = 0
  while i < 6:
    if i == 2:
      i += 1
      continue
    acc += i
    yield acc
    i += 1
  yield 99


class GenCollectTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    out: list[int] = []
    g = genThree()
    for x in g:
      out.append(x)
    self.assertEqual(len(out), 3)
    self.assertEqual(out[0], 1)
    self.assertEqual(out[2], 3)


class GenWhileTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    out: list[int] = []
    for x in genRange(4):
      out.append(x)
    self.assertEqual(len(out), 4)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[3], 3)


class GenYieldFromTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    src: list[int] = [10, 20]
    out: list[int] = []
    for x in genFromList(src):
      out.append(x)
    self.assertEqual(len(out), 2)
    self.assertEqual(out[0], 10)
    self.assertEqual(out[1], 20)


class GenYieldFromReturnTests(TestCaseMixin):
  _testTag = 25

  @override
  def test(self):
    out: list[int] = []
    for x in genYieldFromReturn():
      out.append(x)
    self.assertEqual(len(out), 2)
    self.assertEqual(out[0], 10)
    self.assertEqual(out[1], 42)


class GenSendTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    g = genEcho()
    r0 = g.send(0)
    self.assertFalse(r0.done)
    self.assertEqual(r0.value, 0)
    r1 = g.send(3)
    self.assertFalse(r1.done)
    self.assertEqual(r1.value, 6)
    r2 = g.send(-1)
    self.assertTrue(r2.done)


class GenReturnValueTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    g = genWithReturn()
    r1 = next(g)
    self.assertFalse(r1.done)
    self.assertEqual(r1.value, 1)
    r2 = next(g)
    self.assertFalse(r2.done)
    self.assertEqual(r2.value, 2)
    r3 = next(g)
    self.assertTrue(r3.done)
    self.assertEqual(r3.returnValue, 99)


class GenForElseTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    out: list[int] = []
    for x in genForElseTail():
      out.append(x)
    self.assertEqual(len(out), 4)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[2], 2)
    self.assertEqual(out[3], 100)


class GenForElseBreakTests(TestCaseMixin):
  _testTag = 51

  @override
  def test(self):
    out: list[int] = []
    for x in genForElseSkipOnBreak():
      out.append(x)
    self.assertEqual(len(out), 4)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 1)
    self.assertEqual(out[2], 2)
    self.assertEqual(out[3], 1)


class GenForElseBreakYfTests(TestCaseMixin):
  _testTag = 511

  @override
  def test(self):
    out: list[int] = []
    for x in genForElseSkipOnBreakYf():
      out.append(x)
    self.assertEqual(len(out), 6)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[2], 2)
    self.assertEqual(out[3], 70)
    self.assertEqual(out[4], 71)


class GenForContinueTests(TestCaseMixin):
  _testTag = 52

  @override
  def test(self):
    out: list[int] = []
    g = genForContinueAcc()
    for x in g:
      out.append(x)
    self.assertEqual(len(out), 6)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 1)
    self.assertEqual(out[2], 3)
    self.assertEqual(out[4], 5)
    self.assertEqual(out[5], 13)


class GenForContinueYfTests(TestCaseMixin):
  _testTag = 521

  @override
  def test(self):
    out: list[int] = []
    for x in genForContinueAccYf():
      out.append(x)
    self.assertEqual(len(out), 6)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 1)
    self.assertEqual(out[2], 3)
    self.assertEqual(out[3], 8)
    self.assertEqual(out[4], 9)
    self.assertEqual(out[5], 8)


class GenWhileElseTests(TestCaseMixin):
  _testTag = 53

  @override
  def test(self):
    out: list[int] = []
    for x in genWhileElse():
      out.append(x)
    self.assertEqual(len(out), 1)
    self.assertEqual(out[0], 99)


class GenForYieldListTests(TestCaseMixin):
  _testTag = 54

  @override
  def test(self):
    src: list[int] = [7, 8, 9]
    out: list[int] = []
    for x in genForYieldList(src):
      out.append(x)
    self.assertEqual(len(out), 3)
    self.assertEqual(out[0], 7)
    self.assertEqual(out[2], 9)


class GenWhileContinueYieldTests(TestCaseMixin):
  _testTag = 55

  @override
  def test(self):
    out: list[int] = []
    for x in genWhileContinueAcc():
      out.append(x)
    self.assertEqual(len(out), 6)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 1)
    self.assertEqual(out[2], 4)
    self.assertEqual(out[3], 8)
    self.assertEqual(out[4], 13)
    self.assertEqual(out[5], 99)


class GenForIfElseYieldTests(TestCaseMixin):
  _testTag = 56

  @override
  def test(self):
    out: list[int] = []
    for x in genForIfElseYield():
      out.append(x)
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 101)
    self.assertEqual(out[2], 2)
    self.assertEqual(out[3], 103)
    self.assertEqual(out[4], 200)


class GenForElseIfBreakTests(TestCaseMixin):
  _testTag = 57

  @override
  def test(self):
    out: list[int] = []
    for x in genForElseIfBreak():
      out.append(x)
    self.assertEqual(len(out), 4)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[2], 20)
    self.assertEqual(out[3], 21)


class GenForElseBranchMixTests(TestCaseMixin):
  _testTag = 58

  @override
  def test(self):
    out: list[int] = []
    for x in genForElseBranchMix():
      out.append(x)
    self.assertEqual(len(out), 4)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 40)
    self.assertEqual(out[2], 41)
    self.assertEqual(out[3], 300)


class GenNestedWhileContinueYfTests(TestCaseMixin):
  _testTag = 59

  @override
  def test(self):
    out: list[int] = []
    for x in genNestedWhileContinueYf():
      out.append(x)
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 5)
    self.assertEqual(out[2], 6)
    self.assertEqual(out[3], 3)
    self.assertEqual(out[4], 77)


class GenNestedForInnerBreakYfTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    out: list[int] = []
    for x in genNestedForInnerBreakYf():
      out.append(x)
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 1)
    self.assertEqual(out[2], 8)
    self.assertEqual(out[3], 9)
    self.assertEqual(out[4], 102)


class GenWhileElseIfBreakYieldTests(TestCaseMixin):
  _testTag = 61

  @override
  def test(self):
    out: list[int] = []
    for x in genWhileElseIfBreakYield():
      out.append(x)
    self.assertEqual(len(out), 3)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 1)
    self.assertEqual(out[2], 200)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
