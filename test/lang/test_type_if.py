"""泛型 type if 与标准库条件类型别名（``py2cpp.util.types``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


type InnerListElem[T] = ListElemOf[ListElemOf[T]]


def typeTag[T](x: T) -> int:
  if T is int:
    return 1
  elif T in [str, bool]:
    return 2
  elif T is list[int]:
    return 3
  else:
    return 0


def typeNotInt[T](x: T) -> int:
  if T is not int:
    return 0
  else:
    return 1


def tally[T]() -> int:
  n: int = 0
  for i in range(3):
    if T is int:
      n += 1
    elif T is str:
      n += 2
    else:
      pass
  return n


def typeNotInNum[T](x: T) -> int:
  if T not in {int, float}:
    return 0
  else:
    return 1


def typeListWildcard[T](x: T) -> int:
  if T is list[int]:
    return 1
  elif T is list[...]:
    return 2
  else:
    return 0


def elemCode[T]() -> int:
  if T is int:
    return 1
  elif T is list[int]:
    return 2
  elif T is str:
    return 3
  elif T is list[str]:
    return 4
  else:
    return 0


def innerCode[T]() -> int:
  if T is int:
    return 10
  elif T is list[int]:
    return 11
  elif T is list[list[int]]:
    return 12
  else:
    return 0


def pointeeCode[T]() -> int:
  if T is Pointer[int]:
    return 1
  elif T is int:
    return 2
  elif T is Pointer[str]:
    return 3
  else:
    return 0


def takeListElem[T](x: ListElemOf[T]) -> T:
  return cast(x)


def valCode[T]() -> int:
  if T is list[int]:
    return 1
  elif T is dict[str, int]:
    return 2
  else:
    return 0


def listNumElemCode[T, _U = ...](x: T) -> int:
  if T is list[_U] and _U in [int, float]:
    return 1
  elif T is list[_U]:
    return 2
  else:
    return 0


def pairIntCode[T, _U = ...]() -> int:
  if T is tuple[int, _U] and _U is int:
    return 10
  else:
    return 0


def scalarOrCode[T]() -> int:
  if T is int or T is float:
    return 1
  else:
    return 0


class TypeIfModuleTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(typeTag(42), 1)
    self.assertEqual(typeTag("hi"), 2)
    self.assertEqual(typeTag(True), 2)
    xs: list[int] = []
    self.assertEqual(typeTag(xs), 3)
    self.assertEqual(typeNotInt(1.0), 0)
    self.assertEqual(typeNotInt(7), 1)
    self.assertEqual(tally[int](), 3)
    self.assertEqual(tally[str](), 6)
    self.assertEqual(typeNotInNum("x"), 0)
    self.assertEqual(typeNotInNum(3.14), 1)
    xs2: list[int] = []
    self.assertEqual(typeListWildcard(xs2), 1)
    ys: list[str] = []
    self.assertEqual(typeListWildcard(ys), 2)


class TypeIfCaptureTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    xs: list[int] = [1, 2]
    self.assertEqual(listNumElemCode[list[int]](xs), 1)
    ys: list[float] = [1.0]
    self.assertEqual(listNumElemCode[list[float]](ys), 1)
    zs: list[str] = ["a"]
    self.assertEqual(listNumElemCode[list[str]](zs), 2)
    self.assertEqual(pairIntCode[tuple[int, int]](), 10)
    self.assertEqual(pairIntCode[tuple[int, str]](), 0)
    self.assertEqual(scalarOrCode[int](), 1)
    self.assertEqual(scalarOrCode[float](), 1)
    self.assertEqual(scalarOrCode[str](), 0)


class TypeAliasTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    self.assertEqual(elemCode[int](), 1)
    self.assertEqual(elemCode[list[int]](), 2)
    self.assertEqual(elemCode[str](), 3)
    self.assertEqual(elemCode[list[str]](), 4)
    self.assertEqual(innerCode[list[list[int]]](), 12)
    self.assertEqual(innerCode[list[int]](), 11)
    self.assertEqual(pointeeCode[Pointer[int]](), 1)
    self.assertEqual(pointeeCode[int](), 2)
    self.assertEqual(pointeeCode[Pointer[str]](), 3)
    n: int = 7
    self.assertEqual(takeListElem[int](n), 7)
    xs: list[int] = [1, 2]
    self.assertEqual(takeListElem[int](xs[0]), 1)
    self.assertEqual(valCode[list[int]](), 1)
    self.assertEqual(valCode[dict[str, int]](), 2)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
