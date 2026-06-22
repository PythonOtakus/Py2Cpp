"""泛型 type if 与标准库条件类型别名（``py2cpp.util.types``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


type InnerListElem[T] = ListElemOf[ListElemOf[T]]


def type_tag[T](x: T) -> int:
  if T is int:
    return 1
  elif T in [str, bool]:
    return 2
  elif T is list[int]:
    return 3
  else:
    return 0


def type_not_int[T](x: T) -> int:
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


def type_not_in_num[T](x: T) -> int:
  if T not in {int, float}:
    return 0
  else:
    return 1


def type_list_wildcard[T](x: T) -> int:
  if T is list[int]:
    return 1
  elif T is list[...]:
    return 2
  else:
    return 0


def elem_code[T]() -> int:
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


def inner_code[T]() -> int:
  if T is int:
    return 10
  elif T is list[int]:
    return 11
  elif T is list[list[int]]:
    return 12
  else:
    return 0


def pointee_code[T]() -> int:
  if T is Pointer[int]:
    return 1
  elif T is int:
    return 2
  elif T is Pointer[str]:
    return 3
  else:
    return 0


def take_list_elem[T](x: ListElemOf[T]) -> T:
  return cast(x)


def val_code[T]() -> int:
  if T is list[int]:
    return 1
  elif T is dict[str, int]:
    return 2
  else:
    return 0


def list_num_elem_code[T, _U = ...](x: T) -> int:
  if T is list[_U] and _U in [int, float]:
    return 1
  elif T is list[_U]:
    return 2
  else:
    return 0


def pair_int_code[T, _U = ...]() -> int:
  if T is tuple[int, _U] and _U is int:
    return 10
  else:
    return 0


def scalar_or_code[T]() -> int:
  if T is int or T is float:
    return 1
  else:
    return 0


class TypeIfModuleTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(type_tag(42), 1)
    self.assertEqual(type_tag("hi"), 2)
    self.assertEqual(type_tag(True), 2)
    xs: list[int] = []
    self.assertEqual(type_tag(xs), 3)
    self.assertEqual(type_not_int(1.0), 0)
    self.assertEqual(type_not_int(7), 1)
    self.assertEqual(tally[int](), 3)
    self.assertEqual(tally[str](), 6)
    self.assertEqual(type_not_in_num("x"), 0)
    self.assertEqual(type_not_in_num(3.14), 1)
    xs2: list[int] = []
    self.assertEqual(type_list_wildcard(xs2), 1)
    ys: list[str] = []
    self.assertEqual(type_list_wildcard(ys), 2)


class TypeIfCaptureTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    xs: list[int] = [1, 2]
    self.assertEqual(list_num_elem_code[list[int]](xs), 1)
    ys: list[float] = [1.0]
    self.assertEqual(list_num_elem_code[list[float]](ys), 1)
    zs: list[str] = ["a"]
    self.assertEqual(list_num_elem_code[list[str]](zs), 2)
    self.assertEqual(pair_int_code[tuple[int, int]](), 10)
    self.assertEqual(pair_int_code[tuple[int, str]](), 0)
    self.assertEqual(scalar_or_code[int](), 1)
    self.assertEqual(scalar_or_code[float](), 1)
    self.assertEqual(scalar_or_code[str](), 0)


class TypeAliasTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertEqual(elem_code[int](), 1)
    self.assertEqual(elem_code[list[int]](), 2)
    self.assertEqual(elem_code[str](), 3)
    self.assertEqual(elem_code[list[str]](), 4)
    self.assertEqual(inner_code[list[list[int]]](), 12)
    self.assertEqual(inner_code[list[int]](), 11)
    self.assertEqual(pointee_code[Pointer[int]](), 1)
    self.assertEqual(pointee_code[int](), 2)
    self.assertEqual(pointee_code[Pointer[str]](), 3)
    n: int = 7
    self.assertEqual(take_list_elem[int](n), 7)
    xs: list[int] = [1, 2]
    self.assertEqual(take_list_elem[int](xs[0]), 1)
    self.assertEqual(val_code[list[int]](), 1)
    self.assertEqual(val_code[dict[str, int]](), 2)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
