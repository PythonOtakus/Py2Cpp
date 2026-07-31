"""``T: refcount`` / ``T: copyable`` / ``T: boxing`` 装饰器泛型约束与 ``WeakRef`` 存储类型。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.weak import WeakRef

@dataclass(eq=False, repr=True)
@refcount
class Widget:
    label: str = ''

@boxing
class Cell:

    def __init__(self, n: int=0):
        self.n: int = n

def peek[T: boxing](node: T) -> int:
    return node.n

@copyable
class Point:

    def __init__(self, x: int=0, y: int=0):
        self.x: int = x
        self.y: int = y

def dup[T: copyable](v: T) -> T:
    out: T = v
    return out

class RefcountConstraintTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        w: Widget = new('x')
        r: WeakRef[Widget] = new(w)
        self.assertTrue(r.alive)
        got: Widget = r.value
        self.assertEqual(got.label, 'x')
        w = new()
        got = new()
        self.assertFalse(r.alive)

class BoxingConstraintTests(TestCaseMixin):
    _test_tag = 2

    @override
    def test(self):
        p: Pointer[Cell] = alloc[Cell]()
        init(p, Cell(7))
        self.assertEqual(peek(p), 7)
        lst: list[Cell] = []
        lst.append(p)
        self.assertEqual(len(lst), 1)

class CopyableConstraintTests(TestCaseMixin):
    _test_tag = 3

    @override
    def test(self):
        self.assertEqual(dup(3), 3)
        q: Point = dup(Point(1, 2))
        self.assertEqual(q.x, 1)
        self.assertEqual(q.y, 2)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
