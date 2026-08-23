"""``async`` / ``await`` / ``async for`` / ``async with`` / ``Task.run`` / ``aiter`` / ``anext``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.concur.task import Task, LoopHandle
from py2cpp.io import AsyncCloseMixin


async def asyncReturn() -> int:
  return 42


async def asyncChain() -> int:
  x: int = await asyncReturn()
  return x + 1


async def asyncAwaitGen() -> int:
  """``await`` 另一协程。"""
  return await asyncReturn()


async def asyncGenTwo() -> AsyncGeneratorType[int, None]:
  yield 1
  yield 2


async def sumAsyncFor() -> int:
  total: int = 0
  async for x in asyncGenTwo():
    total += x
  return total


class SimpleAsyncCM:
  entered: int = 0

  async def __aenter__(self) -> int:
    self.entered = 1
    return 9

  async def __aexit__(self):
    self.entered = 2
    return None


async def useAsyncWith() -> int:
  async with SimpleAsyncCM() as v:
    return v


async def firstViaAiter() -> int:
  r = anext(aiter(asyncGenTwo()))
  return r.value


async def asyncVal(n: int) -> int:
  """可 ``await`` 的叶子协程（供控制流嵌套用例复用）。"""
  return n


async def asyncForIfElseAwait() -> list[int]:
  """``for``-``else`` + ``if``/``else`` 两分支均 ``await``。"""
  out: list[int] = []
  for i in range(4):
    if i % 2 == 0:
      v: int = await asyncVal(i)
      out.append(v)
    else:
      v: int = await asyncVal(i + 100)
      out.append(v)
  else:
    v: int = await asyncVal(200)
    out.append(v)
  return out


async def asyncForElseIfBreak() -> int:
  """``for``-``else`` + ``if``/``elif`` + ``break`` + 多段 ``await``（返回累加和）。"""
  acc: int = 0
  for i in range(4):
    if i < 2:
      v: int = await asyncVal(i)
      acc += v
    elif i == 2:
      a: int = await asyncVal(20)
      acc += a
      b: int = await asyncVal(21)
      acc += b
      break
  else:
    v: int = await asyncVal(900)
    acc += v
  return acc


async def asyncForElseBranchMix() -> int:
  """``continue`` / ``await`` / ``break`` / ``else`` 与 ``if``/``elif`` 交错（返回累加和）。"""
  acc: int = 0
  for i in range(5):
    if i == 0:
      v: int = await asyncVal(i)
      acc += v
    elif i == 1:
      continue
    elif i == 2:
      a: int = await asyncVal(40)
      acc += a
      b: int = await asyncVal(41)
      acc += b
    elif i == 3:
      v: int = await asyncVal(300)
      acc += v
      break
  else:
    v: int = await asyncVal(600)
    acc += v
  return acc


async def asyncNestedWhileContinueAwait() -> list[int]:
  """``while``-``else`` + ``continue`` + 分支内多段 ``await``。"""
  out: list[int] = []
  n: int = 0
  while n < 4:
    if n == 1:
      n += 1
      continue
    if n == 2:
      a: int = await asyncVal(5)
      out.append(a)
      b: int = await asyncVal(6)
      out.append(b)
    else:
      v: int = await asyncVal(n)
      out.append(v)
    n += 1
  else:
    v: int = await asyncVal(77)
    out.append(v)
  return out


async def asyncNestedForInnerBreakAwait() -> int:
  """外层 ``for``-``else`` + 内层 ``for`` + ``continue``/``await`` + 外层 ``break``（返回累加和）。"""
  acc: int = 0
  for i in range(6):
    v: int = await asyncVal(i)
    acc += v
    if i == 1:
      for j in range(3):
        if j == 0:
          continue
        elif j == 1:
          a: int = await asyncVal(8)
          acc += a
          b: int = await asyncVal(9)
          acc += b
        else:
          x: int = await asyncVal(100 + j)
          acc += x
      break
  else:
    v: int = await asyncVal(999)
    acc += v
  return acc


async def asyncWhileElseIfBreakAwait() -> int:
  """``while``-``else`` + ``if``/``elif`` + ``break`` + 条件 ``await``（返回累加和）。"""
  acc: int = 0
  k: int = 0
  while k < 5:
    if k == 3:
      break
    elif k == 2:
      v: int = await asyncVal(k * 100)
      acc += v
    else:
      v: int = await asyncVal(k)
      acc += v
    k += 1
  else:
    v: int = await asyncVal(88)
    acc += v
  return acc


async def asyncGenYieldAwaitSteps() -> AsyncGeneratorType[int, None]:
  """异步可迭代：显式 ``yield`` 与 ``await`` 交错。"""
  yield 1
  v: int = await asyncVal(2)
  yield v
  yield 3


async def asyncGenIndices() -> AsyncGeneratorType[int, None]:
  """``async for`` 驱动用的下标序列（体内 ``yield``）。"""
  i: int = 0
  while i < 5:
    yield i
    i += 1


async def asyncForElseCollect() -> list[int]:
  """``async for``-``else``：循环体与 ``else`` 均 ``await``。"""
  out: list[int] = []
  async for x in asyncGenYieldAwaitSteps():
    v: int = await asyncVal(x * 10)
    out.append(v)
  else:
    v: int = await asyncVal(500)
    out.append(v)
  return out


async def asyncForElseBreakSkip() -> int:
  """``async for``-``else`` + ``break``：``else`` 不得执行。"""
  acc: int = 0
  async for x in asyncGenYieldAwaitSteps():
    acc += x
    if x == 2:
      break
  else:
    v: int = await asyncVal(900)
    acc += v
  return acc


async def asyncForElseBranchMixAsync() -> int:
  """``async for``-``else`` + ``continue``/``break``/``if``/``elif`` + 多段 ``await``。"""
  acc: int = 0
  async for i in asyncGenIndices():
    if i == 0:
      v: int = await asyncVal(i)
      acc += v
    elif i == 1:
      continue
    elif i == 2:
      a: int = await asyncVal(40)
      acc += a
      b: int = await asyncVal(41)
      acc += b
    elif i == 3:
      v: int = await asyncVal(300)
      acc += v
      break
  else:
    v: int = await asyncVal(600)
    acc += v
  return acc


async def asyncMegaNestedControl() -> list[int]:
  """``for``-``else`` 套 ``async for``-``else`` + ``if``/``continue``/``break`` + ``await``/``yield`` 源。"""
  out: list[int] = []
  for outer in range(3):
    v: int = await asyncVal(outer * 10)
    out.append(v)
    if outer == 1:
      async for inner in asyncGenYieldAwaitSteps():
        if inner == 1:
          continue
        x: int = await asyncVal(inner + 1000)
        out.append(x)
      else:
        y: int = await asyncVal(7777)
        out.append(y)
      break
  else:
    z: int = await asyncVal(9999)
    out.append(z)
  return out


class ClosableAsyncResource(AsyncCloseMixin):
  closed: bool = False

  async def close(self) -> None:
    await asyncVal(0)
    self.closed = True


async def asyncCloseMixinCtx() -> bool:
  async with ClosableAsyncResource():
    pass
  return True


class AsyncRunTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(asyncReturn()), 42)
    self.assertEqual(Task.run(asyncChain()), 43)


class AsyncAwaitTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    self.assertEqual(Task.run(asyncAwaitGen()), 42)


class AsyncForTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    self.assertEqual(Task.run(sumAsyncFor()), 3)


class AsyncWithTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    self.assertEqual(Task.run(useAsyncWith()), 9)


class BuiltinAiterTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    self.assertEqual(Task.run(firstViaAiter()), 1)


class AsyncForIfElseAwaitTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    out: list[int] = Task.run(asyncForIfElseAwait())
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 101)
    self.assertEqual(out[2], 2)
    self.assertEqual(out[3], 103)
    self.assertEqual(out[4], 200)


class AsyncForElseIfBreakTests(TestCaseMixin):
  _testTag = 51

  @override
  def test(self):
    self.assertEqual(Task.run(asyncForElseIfBreak()), 42)


class AsyncForElseBranchMixTests(TestCaseMixin):
  _testTag = 52

  @override
  def test(self):
    self.assertEqual(Task.run(asyncForElseBranchMix()), 381)


class AsyncNestedWhileContinueAwaitTests(TestCaseMixin):
  _testTag = 53

  @override
  def test(self):
    out: list[int] = Task.run(asyncNestedWhileContinueAwait())
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 5)
    self.assertEqual(out[2], 6)
    self.assertEqual(out[3], 3)
    self.assertEqual(out[4], 77)


class AsyncNestedForInnerBreakAwaitTests(TestCaseMixin):
  _testTag = 54

  @override
  def test(self):
    self.assertEqual(Task.run(asyncNestedForInnerBreakAwait()), 120)


class AsyncWhileElseIfBreakAwaitTests(TestCaseMixin):
  _testTag = 55

  @override
  def test(self):
    self.assertEqual(Task.run(asyncWhileElseIfBreakAwait()), 201)


class AsyncForElseCollectTests(TestCaseMixin):
  _testTag = 56

  @override
  def test(self):
    out: list[int] = Task.run(asyncForElseCollect())
    self.assertEqual(len(out), 4)
    self.assertEqual(out[0], 10)
    self.assertEqual(out[1], 20)
    self.assertEqual(out[2], 30)
    self.assertEqual(out[3], 500)


class AsyncForElseBreakSkipTests(TestCaseMixin):
  _testTag = 57

  @override
  def test(self):
    self.assertEqual(Task.run(asyncForElseBreakSkip()), 3)


class AsyncForElseBranchMixAsyncTests(TestCaseMixin):
  _testTag = 58

  @override
  def test(self):
    self.assertEqual(Task.run(asyncForElseBranchMixAsync()), 381)


class AsyncMegaNestedControlTests(TestCaseMixin):
  _testTag = 59

  @override
  def test(self):
    out: list[int] = Task.run(asyncMegaNestedControl())
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 10)
    self.assertEqual(out[2], 1002)
    self.assertEqual(out[3], 1003)
    self.assertEqual(out[4], 7777)


class AsyncCloseMixinTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    self.assertTrue(Task.run(asyncCloseMixinCtx()))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
