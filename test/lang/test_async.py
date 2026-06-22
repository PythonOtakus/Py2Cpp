"""``async`` / ``await`` / ``async for`` / ``async with`` / ``Task.run`` / ``aiter`` / ``anext``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.concur.task import Task, LoopHandle
from py2cpp.io import AsyncCloseMixin


async def async_return() -> int:
  return 42


async def async_chain() -> int:
  x: int = await async_return()
  return x + 1


async def async_await_gen() -> int:
  """``await`` 另一协程。"""
  return await async_return()


async def async_gen_two() -> AsyncGenerator[int, None]:
  yield 1
  yield 2


async def sum_async_for() -> int:
  total: int = 0
  async for x in async_gen_two():
    total += x
  return total


class SimpleAsyncCM:
  entered: int

  def __init__(self):
    self.entered = 0

  async def __aenter__(self) -> int:
    self.entered = 1
    return 9

  async def __aexit__(self):
    self.entered = 2
    return None


async def use_async_with() -> int:
  async with SimpleAsyncCM() as v:
    return v


async def first_via_aiter() -> int:
  r = anext(aiter(async_gen_two()))
  return r.value


async def async_val(n: int) -> int:
  """可 ``await`` 的叶子协程（供控制流嵌套用例复用）。"""
  return n


async def async_for_if_else_await() -> list[int]:
  """``for``-``else`` + ``if``/``else`` 两分支均 ``await``。"""
  out: list[int] = []
  for i in range(4):
    if i % 2 == 0:
      v: int = await async_val(i)
      out.append(v)
    else:
      v: int = await async_val(i + 100)
      out.append(v)
  else:
    v: int = await async_val(200)
    out.append(v)
  return out


async def async_for_else_if_break() -> int:
  """``for``-``else`` + ``if``/``elif`` + ``break`` + 多段 ``await``（返回累加和）。"""
  acc: int = 0
  for i in range(4):
    if i < 2:
      v: int = await async_val(i)
      acc += v
    elif i == 2:
      a: int = await async_val(20)
      acc += a
      b: int = await async_val(21)
      acc += b
      break
  else:
    v: int = await async_val(900)
    acc += v
  return acc


async def async_for_else_branch_mix() -> int:
  """``continue`` / ``await`` / ``break`` / ``else`` 与 ``if``/``elif`` 交错（返回累加和）。"""
  acc: int = 0
  for i in range(5):
    if i == 0:
      v: int = await async_val(i)
      acc += v
    elif i == 1:
      continue
    elif i == 2:
      a: int = await async_val(40)
      acc += a
      b: int = await async_val(41)
      acc += b
    elif i == 3:
      v: int = await async_val(300)
      acc += v
      break
  else:
    v: int = await async_val(600)
    acc += v
  return acc


async def async_nested_while_continue_await() -> list[int]:
  """``while``-``else`` + ``continue`` + 分支内多段 ``await``。"""
  out: list[int] = []
  n: int = 0
  while n < 4:
    if n == 1:
      n += 1
      continue
    if n == 2:
      a: int = await async_val(5)
      out.append(a)
      b: int = await async_val(6)
      out.append(b)
    else:
      v: int = await async_val(n)
      out.append(v)
    n += 1
  else:
    v: int = await async_val(77)
    out.append(v)
  return out


async def async_nested_for_inner_break_await() -> int:
  """外层 ``for``-``else`` + 内层 ``for`` + ``continue``/``await`` + 外层 ``break``（返回累加和）。"""
  acc: int = 0
  for i in range(6):
    v: int = await async_val(i)
    acc += v
    if i == 1:
      for j in range(3):
        if j == 0:
          continue
        elif j == 1:
          a: int = await async_val(8)
          acc += a
          b: int = await async_val(9)
          acc += b
        else:
          x: int = await async_val(100 + j)
          acc += x
      break
  else:
    v: int = await async_val(999)
    acc += v
  return acc


async def async_while_else_if_break_await() -> int:
  """``while``-``else`` + ``if``/``elif`` + ``break`` + 条件 ``await``（返回累加和）。"""
  acc: int = 0
  k: int = 0
  while k < 5:
    if k == 3:
      break
    elif k == 2:
      v: int = await async_val(k * 100)
      acc += v
    else:
      v: int = await async_val(k)
      acc += v
    k += 1
  else:
    v: int = await async_val(88)
    acc += v
  return acc


async def async_gen_yield_await_steps() -> AsyncGenerator[int, None]:
  """异步可迭代：显式 ``yield`` 与 ``await`` 交错。"""
  yield 1
  v: int = await async_val(2)
  yield v
  yield 3


async def async_gen_indices() -> AsyncGenerator[int, None]:
  """``async for`` 驱动用的下标序列（体内 ``yield``）。"""
  i: int = 0
  while i < 5:
    yield i
    i += 1


async def async_for_else_collect() -> list[int]:
  """``async for``-``else``：循环体与 ``else`` 均 ``await``。"""
  out: list[int] = []
  async for x in async_gen_yield_await_steps():
    v: int = await async_val(x * 10)
    out.append(v)
  else:
    v: int = await async_val(500)
    out.append(v)
  return out


async def async_for_else_break_skip() -> int:
  """``async for``-``else`` + ``break``：``else`` 不得执行。"""
  acc: int = 0
  async for x in async_gen_yield_await_steps():
    acc += x
    if x == 2:
      break
  else:
    v: int = await async_val(900)
    acc += v
  return acc


async def async_for_else_branch_mix_async() -> int:
  """``async for``-``else`` + ``continue``/``break``/``if``/``elif`` + 多段 ``await``。"""
  acc: int = 0
  async for i in async_gen_indices():
    if i == 0:
      v: int = await async_val(i)
      acc += v
    elif i == 1:
      continue
    elif i == 2:
      a: int = await async_val(40)
      acc += a
      b: int = await async_val(41)
      acc += b
    elif i == 3:
      v: int = await async_val(300)
      acc += v
      break
  else:
    v: int = await async_val(600)
    acc += v
  return acc


async def async_mega_nested_control() -> list[int]:
  """``for``-``else`` 套 ``async for``-``else`` + ``if``/``continue``/``break`` + ``await``/``yield`` 源。"""
  out: list[int] = []
  for outer in range(3):
    v: int = await async_val(outer * 10)
    out.append(v)
    if outer == 1:
      async for inner in async_gen_yield_await_steps():
        if inner == 1:
          continue
        x: int = await async_val(inner + 1000)
        out.append(x)
      else:
        y: int = await async_val(7777)
        out.append(y)
      break
  else:
    z: int = await async_val(9999)
    out.append(z)
  return out


class ClosableAsyncResource(AsyncCloseMixin):
  closed: bool

  def __init__(self):
    self.closed = False

  async def close(self) -> None:
    await async_val(0)
    self.closed = True


async def async_close_mixin_ctx() -> bool:
  async with ClosableAsyncResource():
    pass
  return True


class AsyncRunTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(async_return()), 42)
    self.assertEqual(Task.run(async_chain()), 43)


class AsyncAwaitTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    self.assertEqual(Task.run(async_await_gen()), 42)


class AsyncForTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    self.assertEqual(Task.run(sum_async_for()), 3)


class AsyncWithTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    self.assertEqual(Task.run(use_async_with()), 9)


class BuiltinAiterTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    self.assertEqual(Task.run(first_via_aiter()), 1)


class AsyncForIfElseAwaitTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    out: list[int] = Task.run(async_for_if_else_await())
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 101)
    self.assertEqual(out[2], 2)
    self.assertEqual(out[3], 103)
    self.assertEqual(out[4], 200)


class AsyncForElseIfBreakTests(TestCaseMixin):
  _test_tag = 51

  @override
  def test(self):
    self.assertEqual(Task.run(async_for_else_if_break()), 42)


class AsyncForElseBranchMixTests(TestCaseMixin):
  _test_tag = 52

  @override
  def test(self):
    self.assertEqual(Task.run(async_for_else_branch_mix()), 381)


class AsyncNestedWhileContinueAwaitTests(TestCaseMixin):
  _test_tag = 53

  @override
  def test(self):
    out: list[int] = Task.run(async_nested_while_continue_await())
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 5)
    self.assertEqual(out[2], 6)
    self.assertEqual(out[3], 3)
    self.assertEqual(out[4], 77)


class AsyncNestedForInnerBreakAwaitTests(TestCaseMixin):
  _test_tag = 54

  @override
  def test(self):
    self.assertEqual(Task.run(async_nested_for_inner_break_await()), 120)


class AsyncWhileElseIfBreakAwaitTests(TestCaseMixin):
  _test_tag = 55

  @override
  def test(self):
    self.assertEqual(Task.run(async_while_else_if_break_await()), 201)


class AsyncForElseCollectTests(TestCaseMixin):
  _test_tag = 56

  @override
  def test(self):
    out: list[int] = Task.run(async_for_else_collect())
    self.assertEqual(len(out), 4)
    self.assertEqual(out[0], 10)
    self.assertEqual(out[1], 20)
    self.assertEqual(out[2], 30)
    self.assertEqual(out[3], 500)


class AsyncForElseBreakSkipTests(TestCaseMixin):
  _test_tag = 57

  @override
  def test(self):
    self.assertEqual(Task.run(async_for_else_break_skip()), 3)


class AsyncForElseBranchMixAsyncTests(TestCaseMixin):
  _test_tag = 58

  @override
  def test(self):
    self.assertEqual(Task.run(async_for_else_branch_mix_async()), 381)


class AsyncMegaNestedControlTests(TestCaseMixin):
  _test_tag = 59

  @override
  def test(self):
    out: list[int] = Task.run(async_mega_nested_control())
    self.assertEqual(len(out), 5)
    self.assertEqual(out[0], 0)
    self.assertEqual(out[1], 10)
    self.assertEqual(out[2], 1002)
    self.assertEqual(out[3], 1003)
    self.assertEqual(out[4], 7777)


class AsyncCloseMixinTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    self.assertTrue(Task.run(async_close_mixin_ctx()))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
