"""``py2cpp.numeric.modint``：模整数回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.numeric.modint import ModInt
type Int = ModInt[int, 1000000007]

class ModIntArithmeticTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        a: Int = new(1000000005)
        b: Int = new(2)
        c: Int = a + b
        self.assertEqual(int(c), 0)
        d: Int = a * b
        self.assertEqual(int(d), 1000000003)
        e: Int = a / b
        self.assertEqual(int(e * b), int(a))
        self.assertEqual(a // b, 500000002)
        f: Int = a ** 3
        self.assertEqual(int(f), 999999999)
        inv_a: Int = a.inv
        self.assertEqual(int(a * inv_a), 1)

class ModIntNormalizeTests(TestCaseMixin):
    _test_tag = 10

    @override
    def test(self):
        self.assertEqual(int(Int(-1)), 1000000006)
        self.assertFalse(Int(0))
        self.assertEqual(int(Int(1)), 1)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
