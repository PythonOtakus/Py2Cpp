"""``@noexcept`` / ``Result[T, E]`` 集成测。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.result import Result
from py2cpp.core.exceptions import ValueError, Exception


@noexcept
def divOk(a: int, b: int) -> int:
  if b == 0:
    raise ValueError()
  return a // b


@noexcept
def tryCatchOk() -> int:
  n: int = 0
  try:
    raise ValueError()
  except ValueError:
    n = 7
  return n


@noexcept
def voidOk() -> None:
  return


def unwrapOk(r: Result[int, ValueError]) -> int:
  if r.ok:
    return r.value
  return -1


def unwrapErr(r: Result[int, ValueError]) -> int:
  if not r.ok:
    return -2
  return r.value


def valueOnErrRaises(r: Result[int, ValueError]) -> bool:
  caught: bool = False
  try:
    _: int = r.value
  except ValueError:
    caught = True
  return caught


def matchOk(r: Result[int, ValueError]) -> int:
  match r:
    case new.Ok(v):
      return v
    case new.Err(_):
      return -3


class NoexceptBasicTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    ok: Result[int, ValueError] = divOk(10, 2)
    self.assertTrue(ok.ok)
    self.assertEqual(ok.value, 5)
    self.assertEqual(unwrapOk(divOk(8, 4)), 2)
    bad: Result[int, ValueError] = divOk(1, 0)
    self.assertFalse(bad.ok)
    self.assertEqual(unwrapErr(bad), -2)
    self.assertTrue(valueOnErrRaises(bad))
    self.assertEqual(matchOk(divOk(6, 3)), 2)
    self.assertEqual(matchOk(divOk(1, 0)), -3)


class NoexceptTryTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    r: Result[int, ValueError] = tryCatchOk()
    self.assertTrue(r.ok)
    self.assertEqual(r.value, 7)


class NoexceptVoidTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    r: Result[None, Exception] = voidOk()
    self.assertTrue(r.ok)


def main() -> int:
  suite = TestSuite()
  suite.addTest(NoexceptBasicTests())
  suite.addTest(NoexceptTryTests())
  suite.addTest(NoexceptVoidTests())
  return TextTestRunner().run(suite)
