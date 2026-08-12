"""``match`` 序列模式（list / deque / tuple / str）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def dispatch_list(cmd: list[int]) -> int:
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


def dispatch_tuple_pair(p: (int, int)) -> int:
  match p:
    case [0, y]:
      return y
    case [x, 0]:
      return x
    case [a, b]:
      return a + b
    case _:
      return -1


def dispatch_tuple_star(t: (int, int, int)) -> int:
  match t:
    case [a, *mid, c]:
      if len(mid) == 1:
        return a + mid[0] + c
      return -1
    case _:
      return 0


def dispatch_deque(d: deque[int]) -> int:
  match d:
    case [a, *rest, b]:
      return a + b + len(rest)
    case _:
      return -1


def dispatch_char(c: char) -> int:
  match c:
    case "a" | "b":
      return 1
    case _:
      return 0

def dispatch_str_tag(s: str) -> int:
  match s:
    case ["<", *body, ">"]:
      return len(body)
    case _:
      return -1


class MatchListTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    self.assertEqual(dispatch_list(xs), 5)
    zero: list[int] = [0]
    self.assertEqual(dispatch_list(zero), 0)
    ys: list[int] = [2, 1, 2, 3]
    self.assertEqual(dispatch_list(ys), 6)
    bad: list[int] = [9]
    self.assertEqual(dispatch_list(bad), -1)


class MatchTupleTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    self.assertEqual(dispatch_tuple_pair((0, 5)), 5)
    self.assertEqual(dispatch_tuple_pair((3, 0)), 3)
    self.assertEqual(dispatch_tuple_pair((2, 3)), 5)
    self.assertEqual(dispatch_tuple_star((1, 2, 3)), 6)


class MatchDequeTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    q: deque[int] = [1, 9, 2, 4]
    self.assertEqual(dispatch_deque(q), 7)


class MatchCharOrTests(TestCaseMixin):
  _test_tag = 25

  @override
  def test(self):
    self.assertEqual(dispatch_char("a"[0]), 1)
    self.assertEqual(dispatch_char("b"[0]), 1)
    self.assertEqual(dispatch_char("c"[0]), 0)

class MatchStrSequenceTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    self.assertEqual(dispatch_str_tag("<ab>"), 2)
    self.assertEqual(dispatch_str_tag("x"), -1)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
