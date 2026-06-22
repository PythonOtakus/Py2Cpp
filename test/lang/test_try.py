"""``try`` / ``except`` / ``else`` / ``finally`` 集成测。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.exceptions import ExceptionGroup, KeyError, TypeError, ValueError


def try_except_value() -> int:
  n: int = 0
  try:
    n = 1
    raise ValueError()
    n = 2
  except ValueError:
    n = 3
  return n


def try_else_value() -> int:
  n: int = 0
  try:
    n = 1
  except ValueError:
    n = 2
  else:
    n = 3
  return n


def try_except_as_value() -> int:
  n: int = 0
  try:
    raise ValueError()
  except ValueError as e:
    n = 1 if e else 0
  return n


def try_except_star_as_value() -> int:
  n: int = 0
  try:
    raise ValueError()
  except* ValueError as eg:
    n = len(eg)
  return n


def try_except_star_split() -> int:
  total: int = 0
  try:
    raise ExceptionGroup("", [ValueError(), TypeError()])
  except* ValueError as eg:
    total += len(eg)
  except* TypeError as eg:
    total += len(eg)
  return total


def try_except_star_wrap_single() -> bool:
  wrapped: bool = False
  try:
    raise ValueError()
  except* ValueError as eg:
    wrapped = len(eg) == 1
  return wrapped


def try_raise_from_has_cause() -> bool:
  has_cause: bool = False
  try:
    raise ValueError()
  except ValueError as e:
    try:
      raise TypeError() from e
    except TypeError as te:
      has_cause = te.__cause__ is not None
  return has_cause


def try_raise_from_with_args() -> bool:
  has_cause: bool = False
  try:
    raise ValueError()
  except ValueError as e:
    try:
      raise KeyError("inner") from e
    except KeyError as ke:
      has_cause = ke.__cause__ is not None
  return has_cause


def try_finally_value() -> int:
  n: int = 0
  try:
    n = 1
    raise ValueError()
  except ValueError:
    n = 2
  finally:
    n = 3
  return n


def try_else_finally_value() -> int:
  n: int = 0
  try:
    n = 1
  except ValueError:
    n = 2
  else:
    n = 4
  finally:
    n = 5
  return n


def try_tuple_except() -> int:
  n: int = 0
  try:
    raise TypeError()
  except (ValueError, TypeError):
    n = 1
  return n


def try_nested_finally() -> int:
  acc: int = 0
  try:
    try:
      acc = 1
      raise ValueError()
    finally:
      acc = 2
  except ValueError:
    acc = 3
  finally:
    acc = 4
  return acc


def try_bare_except_value() -> int:
  n: int = 0
  try:
    n = 1
    raise ValueError()
    n = 2
  except:
    n = 3
  return n


def try_bare_else_value() -> int:
  n: int = 0
  try:
    n = 1
  except:
    n = 2
  else:
    n = 3
  return n


def try_bare_except_else_on_error() -> int:
  n: int = 0
  try:
    n = 1
    raise TypeError()
  except:
    n = 4
  else:
    n = 5
  return n


def try_return_finally_once() -> int:
  acc: int = 0
  try:
    acc = 1
    return acc
  finally:
    acc = 2
  return acc


class TryExceptTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(try_except_value(), 3)
    self.assertEqual(try_except_as_value(), 1)
    self.assertEqual(try_except_star_as_value(), 1)
    self.assertEqual(try_except_star_split(), 2)
    self.assertTrue(try_except_star_wrap_single())
    self.assertTrue(try_raise_from_has_cause())
    self.assertTrue(try_raise_from_with_args())
    self.assertEqual(try_else_value(), 3)
    self.assertEqual(try_finally_value(), 3)
    self.assertEqual(try_else_finally_value(), 5)
    self.assertEqual(try_tuple_except(), 1)
    self.assertEqual(try_nested_finally(), 4)
    self.assertEqual(try_bare_except_value(), 3)
    self.assertEqual(try_bare_else_value(), 3)
    self.assertEqual(try_bare_except_else_on_error(), 4)
    self.assertEqual(try_return_finally_once(), 2)


class TryComplexFloatTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    ok: bool = True
    try:
      float(1 + 1j)
      ok = False
    except TypeError:
      ok = True
    self.assertTrue(ok)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
