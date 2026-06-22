"""形参包：``*args: Ts`` / 无注解 ``*args``（独立 ``Args`` 包）、``len``、转发与 ``*PyTuple`` 交错。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def sum_all[*Ts](*args: Ts) -> int:
  total: int = 0
  for x in args:
    total += x
  return total


def head_plus_count[*Ts](first: int, *rest) -> int:
  return first + len(rest)


def pack_len[*Ts](*args) -> int:
  return len(args)


def forward_all[*Ts](*args: Ts) -> int:
  return sum_all(*args)


def via_tuple[*Ts](*args: Ts) -> int:
  t: (*Ts,) = args
  return sum_all(*t)


def interleave_scalars_and_tuple(a: (int, int), b: (int, int)) -> int:
  return sum_all(3, *a, 4, *b, 5)


class VariadicTemplateSumThreeTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(sum_all(1, 2, 3), 6)


class VariadicTemplateSumEmptyTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertEqual(sum_all(), 0)


class VariadicTemplateHeadRestTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    self.assertEqual(head_plus_count(10, 20, 30), 12)


class VariadicTemplatePackLenTests(TestCaseMixin):
  _test_tag = 6

  @override
  def test(self):
    self.assertEqual(pack_len(1, 2, 3), 3)
    self.assertEqual(pack_len(), 0)


class VariadicTemplateForwardTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    self.assertEqual(forward_all(1, 2), 3)


class VariadicTemplateViaTupleTests(TestCaseMixin):
  _test_tag = 7

  @override
  def test(self):
    self.assertEqual(via_tuple(1, 2, 3), 6)


class VariadicTemplateInterleaveTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    a: (int, int) = (1, 2)
    b: (int, int) = (7, 8)
    self.assertEqual(interleave_scalars_and_tuple(a, b), 30)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
