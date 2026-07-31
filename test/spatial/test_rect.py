"""``py2cpp.spatial.rect``：``Rect``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import almost
from py2cpp.spatial.matrix import Matrix3
from py2cpp.spatial.rect import Rect
from py2cpp.spatial.vector import Vector2

class RectBasicTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        r: Rect = new(1.0, 2.0, 3.0, 4.0)
        self.assertTrue(almost(r.x, 1.0))
        self.assertTrue(almost(r.width, 3.0))
        self.assertTrue(r.contains(Vector2(2.0, 3.0)))
        self.assertFalse(r.contains(Vector2(0.0, 0.0)))
        self.assertTrue(Vector2(2.0, 3.0) in r)
        self.assertFalse(Vector2(0.0, 0.0) in r)
        neg: Rect = new(5.0, 5.0, -2.0, -3.0)
        fixed: Rect = neg.corrected()
        self.assertTrue(almost(fixed.x, 3.0))
        self.assertTrue(almost(fixed.y, 2.0))
        self.assertTrue(almost(fixed.width, 2.0))
        self.assertTrue(almost(fixed.height, 3.0))

class RectSetOpsTests(TestCaseMixin):
    _test_tag = 2

    @override
    def test(self):
        a: Rect = new(0.0, 0.0, 4.0, 4.0)
        b: Rect = new(2.0, 2.0, 4.0, 4.0)
        self.assertTrue(a.overlaps(b))
        inter: Rect = a & b
        self.assertTrue(almost(inter.x, 2.0))
        self.assertTrue(almost(inter.y, 2.0))
        self.assertTrue(almost(inter.width, 2.0))
        self.assertTrue(almost(inter.height, 2.0))
        self.assertTrue(inter == a.intersect(b))
        u: Rect = a | b
        self.assertTrue(almost(u.x, 0.0))
        self.assertTrue(almost(u.width, 6.0))
        self.assertTrue(almost(u.height, 6.0))
        self.assertTrue(u == a.union(b))
        self.assertTrue(a.embraces(Rect(1.0, 1.0, 1.0, 1.0)))
        moved: Rect = a.moved(Vector2(1.0, -1.0))
        self.assertTrue(almost(moved.x, 1.0))
        self.assertTrue(almost(moved.y, -1.0))

class RectMatrixTests(TestCaseMixin):
    _test_tag = 3

    @override
    def test(self):
        r: Rect = new(0.0, 0.0, 2.0, 2.0)
        out: Rect = r.apply_matrix(Matrix3.from_position(Vector2(1.0, 3.0)))
        self.assertTrue(almost(out.x, 1.0))
        self.assertTrue(almost(out.y, 3.0))
        self.assertTrue(almost(out.width, 2.0))
        self.assertTrue(almost(out.height, 2.0))

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
