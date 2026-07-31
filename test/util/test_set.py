"""容器回归：``set`` / ``frozenset``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class SetBasicsTests(TestCaseMixin):
    _test_tag = 10

    @override
    def test(self):
        empty: set[int] = new()
        self.assertEqual(len(empty), 0)
        self.assertFalse(empty)
        s: set[int] = {1, 2, 3}
        self.assertEqual(len(s), 3)
        self.assertTrue(2 in s)
        self.assertFalse(9 in s)
        seen: list[int] = []
        for x in s:
            seen.append(x)
        self.assertEqual(len(seen), 3)
        self.assertTrue(1 in s)
        self.assertTrue(2 in s)
        self.assertTrue(3 in s)

class SetMutateTests(TestCaseMixin):
    _test_tag = 20

    @override
    def test(self):
        s: set[int] = new()
        s.add(10)
        s.add(20)
        s.add(10)
        self.assertEqual(len(s), 2)
        s.discard(99)
        self.assertEqual(len(s), 2)
        s.remove(10)
        self.assertEqual(len(s), 1)
        other: set[int] = {30, 40}
        s.update(other)
        self.assertTrue(30 in s)
        s.clear()
        self.assertEqual(len(s), 0)

class SetAlgebraTests(TestCaseMixin):
    _test_tag = 30

    @override
    def test(self):
        a: set[int] = {1, 2, 3}
        b: set[int] = {2, 3, 4}
        u: set[int] = a | b
        self.assertEqual(len(u), 4)
        a &= b
        self.assertEqual(len(a), 2)
        self.assertTrue(2 in a)

class SetCompareTests(TestCaseMixin):
    _test_tag = 40

    @override
    def test(self):
        s1: set[int] = {1, 2}
        s2: set[int] = {1, 2, 3}
        self.assertTrue(s1.issubset(s2))
        self.assertFalse(s1.issuperset(s2))
        other: set[int] = {9, 10}
        self.assertTrue(s1.isdisjoint(other))
        c: set[int] = s1.copy()
        self.assertTrue(c == s1)

class FrozenSetTests(TestCaseMixin):
    _test_tag = 50

    @override
    def test(self):
        self.assertEqual(len(frozenset[int]()), 0)
        fs: frozenset[int] = {1, 2, 3}
        self.assertEqual(len(fs), 3)
        fs2: frozenset[int] = {4, 5}
        self.assertEqual(len(fs2), 2)

class FrozenSetLiteralTests(TestCaseMixin):
    _test_tag = 60

    @override
    def test(self):
        fs: frozenset[int] = {6, 7}
        self.assertEqual(len(fs), 2)
        src: list[int] = [1, 2]
        comp: frozenset[int] = {x + 5 for x in src}
        self.assertEqual(len(comp), 2)
        self.assertTrue(6 in comp)

class SetCompTests(TestCaseMixin):
    _test_tag = 70

    @override
    def test(self):
        src: list[int] = [1, 2, 3]
        s: set[int] = {x * 2 for x in src}
        self.assertEqual(len(s), 3)
        self.assertTrue(4 in s)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
