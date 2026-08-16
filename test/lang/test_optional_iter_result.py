"""``Optional[T]`` / ``IterResult[Y,R]``（``@union``）与 ``done`` / ``value`` 属性。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.iter_result import IterResult, resultDone
from py2cpp.core.optional import Optional
from py2cpp.core.result import Result


def optionalSomeValue(opt: Optional[int]) -> int:
  match opt:
    case None:
      return -1
    case v:
      return v


def optionalLiteralMatch(opt: Optional[int]) -> int:
  match opt:
    case None:
      return 0
    case 7:
      return 1
    case _:
      return 2


def iterYieldValue(step: IterResult[int, int]) -> int:
  if step.done:
    return -1
  return step.value


def iterReturnValue(step: IterResult[int, int]) -> int:
  if step.done:
    return step.returnValue
  return 0


def optionalUnbox(opt: Optional[int]) -> int:
  return opt.value


def optionalFromValue(v: int) -> Optional[int]:
  out: Optional[int] = v
  return out


def optionalNone() -> Optional[int]:
  out: Optional[int] = None
  return out


def optionalNoneOrValue(v: int | None) -> int:
  x: Optional[int] = v
  if x is None:
    return -1
  if x is not None:
    return x.value
  return 0


def echoYieldValue[Y, R](v: IterResult[Y, R].YieldValue) -> IterResult[Y, R].YieldValue:
  return v


def echoOptValue[T](v: Optional[T].Value) -> Optional[T].Value:
  return v


def okValueTag[T]() -> int:
  if T is Result[int, ValueError]:
    return 1
  elif T is Result[str, ValueError]:
    return 2
  else:
    return 0


class OptionalSomeTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(optionalSomeValue(optionalFromValue(7)), 7)
    self.assertEqual(optionalSomeValue(optionalNone()), -1)
    self.assertEqual(optionalLiteralMatch(optionalNone()), 0)
    self.assertEqual(optionalLiteralMatch(optionalFromValue(7)), 1)
    self.assertEqual(optionalLiteralMatch(optionalFromValue(3)), 2)


class OptionalBoxUnboxTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    a: Optional[int] = 7
    self.assertEqual(optionalUnbox(a), 7)
    b: Optional[int] = None
    self.assertTrue(b is None)
    self.assertFalse(b is not None)
    c: Optional[int] = optionalFromValue(9)
    self.assertEqual(optionalUnbox(c), 9)
    self.assertEqual(optionalNoneOrValue(3), 3)
    self.assertEqual(optionalNoneOrValue(None), -1)


class IterResultPropertyTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    y: IterResult[int, int] = IterResult[int, int].Yield(3)
    self.assertFalse(y.done)
    self.assertEqual(iterYieldValue(y), 3)
    done: IterResult[int, int] = resultDone[int, int]()
    self.assertTrue(done.done)
    self.assertEqual(iterReturnValue(done), 0)
    ret: IterResult[int, int] = IterResult[int, int].Return(99)
    self.assertTrue(ret.done)
    self.assertEqual(iterReturnValue(ret), 99)
    self.assertEqual(echoYieldValue[int, int](5), 5)
    self.assertEqual(echoOptValue(11), 11)
    self.assertEqual(okValueTag[Result[int, ValueError]](), 1)
    self.assertEqual(okValueTag[Result[str, ValueError]](), 2)


def main() -> int:
  suite = TestSuite()
  suite.addTest(OptionalSomeTests())
  suite.addTest(OptionalBoxUnboxTests())
  suite.addTest(IterResultPropertyTests())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
