"""``@final`` 类/方法/``T @final`` 实例字段。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@final
class Sealed:
  tag: int @final = 7


class Point:
  x: int @final
  y: int @final

  def __init__(self, x: int, y: int):
    self.x = x
    self.y = y


class Record:
  """final 进 ctor 初始化列表；非 final 留在 ``__init__`` 体内赋值。"""
  id: int @final
  name: str
  score: int = 0

  def __init__(self, id: int, name: str):
    self.id = id
    self.name = name


class Defaults:
  """final 类体默认 + 非 final 类体默认（无 ``__init__``）。"""
  key: int @final = 11
  label: str = "ok"


class MixedDefault:
  """final 类体默认 + 非 final 在 ``__init__`` 体内赋值。"""
  key: int @final = 99
  label: str

  def __init__(self, label: str):
    self.label = label


class DualInit:
  """多个 ``@overload`` ``__init__``：各 overload 均须初始化全部 ``@final`` 字段。"""
  a: int @final
  b: int @final

  @overload
  def __init__(self, a: int):
    self.a = a
    self.b = 0

  @overload
  def __init__(self, a: int, b: int):
    self.a = a
    self.b = b


class ValueHolder:
  @final
  def value(self) -> int:
    return 42


class FinalTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    p: Point = new(3, 4)
    self.assertEqual(p.x, 3)
    self.assertEqual(p.y, 4)
    r: Record = new(1, "a")
    self.assertEqual(r.id, 1)
    self.assertEqual(r.name, "a")
    self.assertEqual(r.score, 0)
    r.score = 5
    self.assertEqual(r.score, 5)
    d: Defaults = new()
    self.assertEqual(d.key, 11)
    self.assertEqual(d.label, "ok")
    d.label = "done"
    self.assertEqual(d.label, "done")
    m: MixedDefault = new("x")
    self.assertEqual(m.key, 99)
    self.assertEqual(m.label, "x")
    one: DualInit = new(3)
    self.assertEqual(one.a, 3)
    self.assertEqual(one.b, 0)
    two: DualInit = new(3, 4)
    self.assertEqual(two.a, 3)
    self.assertEqual(two.b, 4)
    s: Sealed = new()
    self.assertEqual(s.tag, 7)
    c: ValueHolder = new()
    self.assertEqual(c.value(), 42)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
