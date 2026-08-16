"""``PyCoroutine[Y,S,R]`` 擦除：形参/字段/``@virtual`` 返回；``-> CoroutineType`` 仍为具体 ``*_coroutine``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.concur.task import Task, LoopHandle

async def coroFortyTwo() -> int:
    return 42

async def awaitCoro(c: CoroutineType[LoopHandle, None, int]) -> int:
    return await c

async def asyncGenPair() -> AsyncGeneratorType[int, None]:
    yield 1
    yield 2

async def sumAsyncGen(g: AsyncGeneratorType[int, None]) -> int:
    total: int = 0
    async for x in g:
        total += x
    return total

@copyable
class CoroHolder:
    c: CoroutineType[LoopHandle, None, int]

    def store(self, src: CoroutineType[LoopHandle, None, int]) -> None:
        self.c = src

    async def awaitStored(self) -> int:
        return await self.c

class CoroStreamBase:

    @virtual
    async def stream(self) -> CoroutineType[LoopHandle, None, int]:
        return 42

@copyable
class CoroStreamA(CoroStreamBase):

    @override
    async def stream(self) -> CoroutineType[LoopHandle, None, int]:
        return await coroFortyTwo()

async def awaitOverrideStream(a: CoroStreamA) -> int:
    return await a.stream()

class CoroEraseParamTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        self.assertEqual(Task.run(awaitCoro(coroFortyTwo())), 42)

class CoroEraseFieldTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        h: CoroHolder = new()
        h.store(coroFortyTwo())
        self.assertEqual(Task.run(h.awaitStored()), 42)

class CoroEraseOverrideTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        self.assertEqual(Task.run(awaitOverrideStream(CoroStreamA())), 42)

class CoroEraseAsyncForTests(TestCaseMixin):
    _testTag = 30

    @override
    def test(self):
        self.assertEqual(Task.run(sumAsyncGen(asyncGenPair())), 3)

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    runner: TextTestRunner = new()
    return runner.run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
