"""``match`` 序列模式（list / deque / tuple / str）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def dispatchList(cmd: list[int]) -> int:
  match cmd:
    case [0]:
      return 0
    case [1, x, y]:
      return x + y
    case [2, *rest] if rest:
      total: int = 0
      for n in rest:
        total += n
      return total
    case _:
      return -1


def dispatchTuplePair(p: (int, int)) -> int:
  match p:
    case [0, y]:
      return y
    case [x, 0]:
      return x
    case [a, b]:
      return a + b
    case _:
      return -1


def dispatchTupleStar(t: (int, int, int)) -> int:
  match t:
    case [a, *mid, c]:
      if len(mid) == 1:
        return a + mid[0] + c
      return -1
    case _:
      return 0


def dispatchDeque(d: deque[int]) -> int:
  match d:
    case [a, *rest, b]:
      return a + b + len(rest)
    case _:
      return -1


def dispatchChar(c: char) -> int:
  match c:
    case "a" | "b":
      return 1
    case _:
      return 0

def dispatchStrTag(s: str) -> int:
  match s:
    case ["<", *body, ">"]:
      return len(body)
    case _:
      return -1


class MatchListTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    self.assertEqual(dispatchList(xs), 5)
    zero: list[int] = [0]
    self.assertEqual(dispatchList(zero), 0)
    ys: list[int] = [2, 1, 2, 3]
    self.assertEqual(dispatchList(ys), 6)
    bad: list[int] = [9]
    self.assertEqual(dispatchList(bad), -1)


class MatchTupleTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    self.assertEqual(dispatchTuplePair((0, 5)), 5)
    self.assertEqual(dispatchTuplePair((3, 0)), 3)
    self.assertEqual(dispatchTuplePair((2, 3)), 5)
    self.assertEqual(dispatchTupleStar((1, 2, 3)), 6)


class MatchDequeTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    q: deque[int] = [1, 9, 2, 4]
    self.assertEqual(dispatchDeque(q), 7)


class MatchCharOrTests(TestCaseMixin):
  _testTag = 25

  @override
  def test(self):
    self.assertEqual(dispatchChar("a"[0]), 1)
    self.assertEqual(dispatchChar("b"[0]), 1)
    self.assertEqual(dispatchChar("c"[0]), 0)

class MatchStrSequenceTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    self.assertEqual(dispatchStrTag("<ab>"), 2)
    self.assertEqual(dispatchStrTag("x"), -1)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
