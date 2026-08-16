"""``try`` / ``except`` / ``else`` / ``finally`` 集成测。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.exceptions import ExceptionGroup, KeyError, TypeError, ValueError


def tryExceptValue() -> int:
  n: int = 0
  try:
    n = 1
    raise ValueError()
    n = 2
  except ValueError:
    n = 3
  return n


def tryElseValue() -> int:
  n: int = 0
  try:
    n = 1
  except ValueError:
    n = 2
  else:
    n = 3
  return n


def tryExceptAsValue() -> int:
  n: int = 0
  try:
    raise ValueError()
  except ValueError as e:
    n = 1 if e else 0
  return n


def tryExceptStarAsValue() -> int:
  n: int = 0
  try:
    raise ValueError()
  except* ValueError as eg:
    n = len(eg)
  return n


def tryExceptStarSplit() -> int:
  total: int = 0
  try:
    raise ExceptionGroup("", [ValueError(), TypeError()])
  except* ValueError as eg:
    total += len(eg)
  except* TypeError as eg:
    total += len(eg)
  return total


def tryExceptStarWrapSingle() -> bool:
  wrapped: bool = False
  try:
    raise ValueError()
  except* ValueError as eg:
    wrapped = len(eg) == 1
  return wrapped


def tryRaiseFromHasCause() -> bool:
  hasCause: bool = False
  try:
    raise ValueError()
  except ValueError as e:
    try:
      raise TypeError() from e
    except TypeError as te:
      hasCause = te.__cause__ is not None
  return hasCause


def tryRaiseFromWithArgs() -> bool:
  hasCause: bool = False
  try:
    raise ValueError()
  except ValueError as e:
    try:
      raise KeyError("inner") from e
    except KeyError as ke:
      hasCause = ke.__cause__ is not None
  return hasCause


def tryFinallyValue() -> int:
  n: int = 0
  try:
    n = 1
    raise ValueError()
  except ValueError:
    n = 2
  finally:
    n = 3
  return n


def tryElseFinallyValue() -> int:
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


def tryTupleExcept() -> int:
  n: int = 0
  try:
    raise TypeError()
  except (ValueError, TypeError):
    n = 1
  return n


def tryNestedFinally() -> int:
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


def tryBareExceptValue() -> int:
  n: int = 0
  try:
    n = 1
    raise ValueError()
    n = 2
  except:
    n = 3
  return n


def tryBareElseValue() -> int:
  n: int = 0
  try:
    n = 1
  except:
    n = 2
  else:
    n = 3
  return n


def tryBareExceptElseOnError() -> int:
  n: int = 0
  try:
    n = 1
    raise TypeError()
  except:
    n = 4
  else:
    n = 5
  return n


def tryReturnFinallyOnce() -> int:
  acc: int = 0
  try:
    acc = 1
    return acc
  finally:
    acc = 2
  return acc


class TryExceptTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(tryExceptValue(), 3)
    self.assertEqual(tryExceptAsValue(), 1)
    self.assertEqual(tryExceptStarAsValue(), 1)
    self.assertEqual(tryExceptStarSplit(), 2)
    self.assertTrue(tryExceptStarWrapSingle())
    self.assertTrue(tryRaiseFromHasCause())
    self.assertTrue(tryRaiseFromWithArgs())
    self.assertEqual(tryElseValue(), 3)
    self.assertEqual(tryFinallyValue(), 3)
    self.assertEqual(tryElseFinallyValue(), 5)
    self.assertEqual(tryTupleExcept(), 1)
    self.assertEqual(tryNestedFinally(), 4)
    self.assertEqual(tryBareExceptValue(), 3)
    self.assertEqual(tryBareElseValue(), 3)
    self.assertEqual(tryBareExceptElseOnError(), 4)
    self.assertEqual(tryReturnFinallyOnce(), 2)


class TryComplexFloatTests(TestCaseMixin):
  _testTag = 10

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
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
