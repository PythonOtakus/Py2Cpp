"""泛型类体内 ``if T is int:`` / ``elif`` / ``else`` 编译期分派 → C++ 类模板特化。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Cell[T]:
  if T is int:
    type V = int
    seed: V = 0
    band: int = 10
    @staticmethod
    def tag() -> int:
      return 1
  elif T is str:
    type V = str
    seed: V = new()
    band: int = 20
    @staticmethod
    def tag() -> int:
      return 2
  else:
    type V = float64
    seed: V = 0.0
    band: int = 30
    @staticmethod
    def tag() -> int:
      return 3

  serial: int = 0
  label: str @property = ""
  slot: V = new()

  def read(self) -> V:
    return self.slot

  def read_label(self) -> str:
    return self.label

  def write(self, x: V) -> None:
    self.slot = x

  def reset(self) -> None:
    self.slot = self.seed

  @staticmethod
  def arity_hint() -> int:
    return 1


class CellIntTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Cell[int].tag(), 1)
    self.assertEqual(Cell[int].arity_hint(), 1)
    c: Cell[int] = new()
    self.assertEqual(c.serial, 0)
    self.assertEqual(c.read(), 0)
    c.write(7)
    self.assertEqual(c.read(), 7)
    self.assertEqual(c.read_label(), "")
    c.reset()
    self.assertEqual(c.read(), 0)


class CellStrTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertEqual(Cell[str].tag(), 2)
    c: Cell[str] = new()
    self.assertEqual(c.read(), "")
    c.write("hi")
    self.assertEqual(c.read(), "hi")
    self.assertEqual(c.read_label(), "")
    c.reset()
    self.assertEqual(c.read(), "")


class CellFloatTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    self.assertEqual(Cell[float64].tag(), 3)
    c: Cell[float64] = new()
    self.assertEqual(c.read(), 0.0)
    c.write(3.5)
    self.assertEqual(c.read(), 3.5)
    c.reset()
    self.assertEqual(c.read(), 0.0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
