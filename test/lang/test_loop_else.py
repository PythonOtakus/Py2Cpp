"""``for`` / ``while`` 的 ``else``（无用户 ``break`` 时执行）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def for_else_sum() -> int:
  acc: int = 0
  for i in range(3):
    acc += i
  else:
    acc += 100
  return acc


def for_else_skip_on_break() -> int:
  acc: int = 0
  for i in range(10):
    if i == 2:
      break
    acc += i
  else:
    acc += 100
  return acc


def while_else_count() -> int:
  acc: int = 0
  for n in range(3, 0, -1):
    acc += 1
  else:
    acc += 10
  return acc


class ForElseTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(for_else_sum(), 103)
    self.assertEqual(for_else_skip_on_break(), 1)


class WhileElseTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertEqual(while_else_count(), 13)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
