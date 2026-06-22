"""``@union.mro``、嵌套 ``Enum``、``__enum__``、``Enum.of`` / ``Enum.create``（模块内自建，勿依赖 ``ExcSlot``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.exceptions import Exception


class LocalError(Exception):
  pass


class AlphaError(LocalError):
  pass


class BetaError(LocalError):
  pass


@union.mro
class ErrorSlot(base=Exception):
  @variant
  class Unknown:
    pass


def classify(e: Exception) -> ErrorSlot.Enum:
  return ErrorSlot.Enum.of(e)


def make_alpha() -> AlphaError:
  return new()


def slot_tag(slot: ErrorSlot) -> int:
  if slot.__enum__ == ErrorSlot.Enum.AlphaError:
    return 1
  if slot.__enum__ == ErrorSlot.Enum.BetaError:
    return 2
  return 0


class UnionMroEnumTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    a: AlphaError = new()
    self.assertEqual(classify(a), ErrorSlot.Enum.AlphaError)
    made: AlphaError = make_alpha()
    self.assertEqual(ErrorSlot.Enum.of(made), ErrorSlot.Enum.AlphaError)
    created: Exception = ErrorSlot.Enum.create(ErrorSlot.Enum.AlphaError)
    self.assertTrue(created)
    self.assertEqual(str(ErrorSlot.Enum.BetaError), "ErrorSlot.Enum.BetaError")
    self.assertEqual(repr(ErrorSlot.Enum.Unknown), "<ErrorSlot.Enum.Unknown: -1>")


class UnionMroDunderTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    ae: AlphaError = new()
    sa: ErrorSlot = new.AlphaError(ae)
    self.assertEqual(slot_tag(sa), 1)
    be: BetaError = new()
    sb: ErrorSlot = new.BetaError(be)
    self.assertEqual(slot_tag(sb), 2)
    self.assertEqual(sa.__enum__, ErrorSlot.Enum.AlphaError)
    self.assertTrue(sb.__enum__ != sa.__enum__)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
