"""``py2cpp.numeric.modint``：模整数回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.numeric.modint import ModInt
type Int = ModInt[int, 1000000007]

class ModIntArithmeticTests(TestCaseMixin):
    _testTag = 1

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
        invA: Int = a.inv
        self.assertEqual(int(a * invA), 1)

class ModIntNormalizeTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        self.assertEqual(int(Int(-1)), 1000000006)
        self.assertFalse(Int(0))
        self.assertEqual(int(Int(1)), 1)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
