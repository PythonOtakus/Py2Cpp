"""``PyContextManager[T]`` 擦除：形参/字段持有同步上下文管理器。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

@copyable
class IntCM:
    log: list[int] = []

    def __enter__(self) -> int:
        self.log.append(1)
        return 7

    def __exit__(self):
        pass

def run_cm(m: ContextManager[int]) -> None:
    with m:
        pass

def run_cm_as(m: ContextManager[int]) -> int:
    with m as x:
        return x

class CMHolder:
    m: ContextManager[int]

    def store(self, src: ContextManager[int]) -> None:
        self.m = src

    def run_stored(self) -> None:
        with self.m:
            pass

class ContextManagerEraseTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        cm: IntCM = new()
        run_cm(cm)
        self.assertEqual(len(cm.log), 1)

class ContextManagerFieldTests(TestCaseMixin):
    _test_tag = 10

    @override
    def test(self):
        h: CMHolder = new()
        src: IntCM = new()
        h.store(src)
        h.run_stored()
        self.assertEqual(len(src.log), 1)

class ContextManagerAsEnterTests(TestCaseMixin):
    _test_tag = 20

    @override
    def test(self):
        # 擦除形参持有底层对象；须具名存活，勿传 ``IntCM()`` 临时值
        cm: IntCM = new()
        self.assertEqual(run_cm_as(cm), 7)
        self.assertEqual(len(cm.log), 1)

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    runner: TextTestRunner = new()
    return runner.run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
