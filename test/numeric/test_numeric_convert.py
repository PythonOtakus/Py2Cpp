"""数字类型 ``int()`` / ``float()`` / ``complex()`` 转换（向下兼容 dunder 链）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.numeric.modint import ModInt

type Int = ModInt[int, 1000000007]


class FixedWidthIntConvertTests(TestCaseMixin):
  _testTag = 0

  @override
  def test(self):
    signed: int16 = int16(-123)
    unsigned: uint16 = uint16(65535)
    self.assertEqual(signed, -123)
    self.assertEqual(unsigned, 65535)
    self.assertEqual(int16.Min, -32768)
    self.assertEqual(uint16.Max, 65535)

class LongConvertTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    v: long = 42
    self.assertEqual(float(v), 42.0)
    self.assertEqual(complex(v).real, 42)
    self.assertEqual(complex(v).imag, 0)
    big: long = 16777215
    self.assertEqual(float(big), 16777215.0)


class ModIntConvertTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    x: Int = new(5)
    self.assertEqual(float(x), 5.0)
    self.assertEqual(complex(x).real, 5)
    self.assertEqual(complex(x).imag, 0)


class ComplexConvertTests(TestCaseMixin):
  _testTag = 20

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
    realOnly: complex = 7 + 0j
    self.assertEqual(float(realOnly), 7.0)
    self.assertEqual(int(realOnly), 7)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
