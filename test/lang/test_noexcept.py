"""``@noexcept`` / ``Result[T, E]`` 集成测。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.result import Result
from py2cpp.core.exceptions import ValueError, Exception


@noexcept
def div_ok(a: int, b: int) -> int:
  if b == 0:
    raise ValueError()
  return a // b


@noexcept
def try_catch_ok() -> int:
  n: int = 0
  try:
    raise ValueError()
  except ValueError:
    n = 7
  return n


@noexcept
def void_ok() -> None:
  return


def unwrap_ok(r: Result[int, ValueError]) -> int:
  if r.ok:
    return r.value
  return -1


def unwrap_err(r: Result[int, ValueError]) -> int:
  if not r.ok:
    return -2
  return r.value


def value_on_err_raises(r: Result[int, ValueError]) -> bool:
  caught: bool = False
  try:
    _: int = r.value
  except ValueError:
    caught = True
  return caught


def match_ok(r: Result[int, ValueError]) -> int:
  match r:
    case new.Ok(v):
      return v
    case new.Err(_):
      return -3


class NoexceptBasicTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    ok: Result[int, ValueError] = div_ok(10, 2)
    self.assertTrue(ok.ok)
    self.assertEqual(ok.value, 5)
    self.assertEqual(unwrap_ok(div_ok(8, 4)), 2)
    bad: Result[int, ValueError] = div_ok(1, 0)
    self.assertFalse(bad.ok)
    self.assertEqual(unwrap_err(bad), -2)
    self.assertTrue(value_on_err_raises(bad))
    self.assertEqual(match_ok(div_ok(6, 3)), 2)
    self.assertEqual(match_ok(div_ok(1, 0)), -3)


class NoexceptTryTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    r: Result[int, ValueError] = try_catch_ok()
    self.assertTrue(r.ok)
    self.assertEqual(r.value, 7)


class NoexceptVoidTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    r: Result[None, Exception] = void_ok()
    self.assertTrue(r.ok)


def main() -> int:
  suite = TestSuite()
  suite.addTest(NoexceptBasicTests())
  suite.addTest(NoexceptTryTests())
  suite.addTest(NoexceptVoidTests())
  return TextTestRunner().run(suite)
