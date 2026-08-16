"""``PyGenerator[Y,S,R]`` 擦除：形参/字段/``@virtual`` 返回；``-> GeneratorType`` 仍为具体 ``*_generator``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

def genPair() -> GeneratorType[int, None, None]:
    yield 1
    yield 2

def sumGen(g: GeneratorType[int, None, None]) -> int:
    s: int = 0
    for x in g:
        s += x
    return s

@copyable
class GenHolder:
    g: GeneratorType[int, None, None]

    def store(self, src: GeneratorType[int, None, None]) -> None:
        self.g = src

    def sumStored(self) -> int:
        s: int = 0
        for x in self.g:
            s += x
        return s

class GenStreamBase:

    @virtual
    def stream(self) -> GeneratorType[int, None, None]:
        yield 0

@copyable
class GenStreamA(GenStreamBase):

    @override
    def stream(self) -> GeneratorType[int, None, None]:
        yield 10
        yield 20

def sumOverrideStream(a: GenStreamA) -> int:
    s: int = 0
    for x in a.stream():
        s += x
    return s

class GenEraseParamTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        self.assertEqual(sumGen(genPair()), 3)

class GenEraseFieldTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        h: GenHolder = new()
        h.store(genPair())
        self.assertEqual(h.sumStored(), 3)

class GenEraseOverrideTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        self.assertEqual(sumOverrideStream(GenStreamA()), 30)

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    runner: TextTestRunner = new()
    return runner.run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
