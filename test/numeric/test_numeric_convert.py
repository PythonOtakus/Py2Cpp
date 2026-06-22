"""数字类型 ``int()`` / ``float()`` / ``complex()`` 转换（向下兼容 dunder 链）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.numeric.modint import ModInt

type Int = ModInt[int, 1000000007]


class VarIntConvertTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    v: varint = 42
    self.assertEqual(float(v), 42.0)
    self.assertEqual(complex(v).real, 42)
    self.assertEqual(complex(v).imag, 0)
    big: varint = 16777215
    self.assertEqual(float(big), 16777215.0)


class ModIntConvertTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    x: Int = new(5)
    self.assertEqual(float(x), 5.0)
    self.assertEqual(complex(x).real, 5)
    self.assertEqual(complex(x).imag, 0)


class ComplexConvertTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    z: complex = 3 + 4j
    w: complex = new(z)
    self.assertEqual(w.real, 3)
    self.assertEqual(w.imag, 4)
    self.assertEqual(complex().real, 0)
    self.assertEqual(complex().imag, 0)
    self.assertEqual(complex(2, -1).real, 2)
    self.assertEqual(complex(2, -1).imag, -1)
    real_only: complex = 7 + 0j
    self.assertEqual(float(real_only), 7.0)
    self.assertEqual(int(real_only), 7)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
