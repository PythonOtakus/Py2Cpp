"""``PyCoroutine[Y,S,R]`` 擦除：形参/字段/``@virtual`` 返回；``-> Coroutine`` 仍为具体 ``*_coroutine``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.concur.task import Task, LoopHandle


async def coro_forty_two() -> int:
  return 42


async def await_coro(c: Coroutine[None, None, int]) -> int:
  return await c


async def async_gen_pair() -> AsyncGenerator[int, None]:
  yield 1
  yield 2


async def sum_async_gen(g: AsyncGenerator[int, None]) -> int:
  total: int = 0
  async for x in g:
    total += x
  return total


@copyable
class CoroHolder:
  c: Coroutine[None, None, int]

  def store(self, src: Coroutine[None, None, int]) -> None:
    self.c = src

  async def await_stored(self) -> int:
    return await self.c


class CoroStreamBase:
  @virtual
  async def stream(self) -> Coroutine[None, None, int]:
    return 42


@copyable
class CoroStreamA(CoroStreamBase):
  @override
  async def stream(self) -> Coroutine[None, None, int]:
    return await coro_forty_two()


async def await_override_stream(a: CoroStreamA) -> int:
  return await a.stream()


class CoroEraseParamTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(await_coro(coro_forty_two())), 42)


class CoroEraseFieldTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    h: CoroHolder = new()
    h.store(coro_forty_two())
    self.assertEqual(Task.run(h.await_stored()), 42)


class CoroEraseOverrideTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    a: CoroStreamA = new()
    self.assertEqual(Task.run(await_override_stream(a)), 42)


class CoroEraseAsyncForTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    self.assertEqual(Task.run(sum_async_gen(async_gen_pair())), 3)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
