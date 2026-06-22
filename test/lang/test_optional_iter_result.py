"""``Optional[T]`` / ``IterResult[Y,R]``（``@union``）与 ``done`` / ``value`` 属性。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.iter_result import IterResult, result_done
from py2cpp.core.optional import Optional
from py2cpp.core.result import Result


def optional_some_value(opt: Optional[int]) -> int:
  match opt:
    case None:
      return -1
    case v:
      return v


def optional_literal_match(opt: Optional[int]) -> int:
  match opt:
    case None:
      return 0
    case 7:
      return 1
    case _:
      return 2


def iter_yield_value(step: IterResult[int, int]) -> int:
  if step.done:
    return -1
  return step.value


def iter_return_value(step: IterResult[int, int]) -> int:
  if step.done:
    return step.return_value
  return 0


def optional_unbox(opt: Optional[int]) -> int:
  return opt.value


def optional_from_value(v: int) -> Optional[int]:
  out: Optional[int] = v
  return out


def optional_none() -> Optional[int]:
  out: Optional[int] = None
  return out


def optional_none_or_value(v: int | None) -> int:
  x: Optional[int] = v
  if x is None:
    return -1
  if x is not None:
    return x.value
  return 0


def echo_yield_value[Y, R](v: IterResult[Y, R].YieldValue) -> IterResult[Y, R].YieldValue:
  return v


def echo_opt_value[T](v: Optional[T].Value) -> Optional[T].Value:
  return v


def ok_value_tag[T]() -> int:
  if T is Result[int, ValueError]:
    return 1
  elif T is Result[str, ValueError]:
    return 2
  else:
    return 0


class OptionalSomeTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(optional_some_value(optional_from_value(7)), 7)
    self.assertEqual(optional_some_value(optional_none()), -1)
    self.assertEqual(optional_literal_match(optional_none()), 0)
    self.assertEqual(optional_literal_match(optional_from_value(7)), 1)
    self.assertEqual(optional_literal_match(optional_from_value(3)), 2)


class OptionalBoxUnboxTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    a: Optional[int] = 7
    self.assertEqual(optional_unbox(a), 7)
    b: Optional[int] = None
    self.assertTrue(b is None)
    self.assertFalse(b is not None)
    c: Optional[int] = optional_from_value(9)
    self.assertEqual(optional_unbox(c), 9)
    self.assertEqual(optional_none_or_value(3), 3)
    self.assertEqual(optional_none_or_value(None), -1)


class IterResultPropertyTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    y: IterResult[int, int] = IterResult[int, int].Yield(3)
    self.assertFalse(y.done)
    self.assertEqual(iter_yield_value(y), 3)
    done: IterResult[int, int] = result_done[int, int]()
    self.assertTrue(done.done)
    self.assertEqual(iter_return_value(done), 0)
    ret: IterResult[int, int] = IterResult[int, int].Return(99)
    self.assertTrue(ret.done)
    self.assertEqual(iter_return_value(ret), 99)
    self.assertEqual(echo_yield_value[int, int](5), 5)
    self.assertEqual(echo_opt_value(11), 11)
    self.assertEqual(ok_value_tag[Result[int, ValueError]](), 1)
    self.assertEqual(ok_value_tag[Result[str, ValueError]](), 2)


def main() -> int:
  suite = TestSuite()
  suite.addTest(OptionalSomeTests())
  suite.addTest(OptionalBoxUnboxTests())
  suite.addTest(IterResultPropertyTests())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
