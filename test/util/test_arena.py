"""``util.Arena``：分配、``str.adopt_span``、``reset``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class ArenaAdoptTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    # ``Arena.acquire`` / ``release`` + ``PyStr.adopt_span`` 接管缓冲
    ar: Arena = new()
    p: Pointer[char] = ar.acquire(5)
    s: str = ""
    owned: span[char] = new(p, 5, 1)
    h: char = ord("h")
    e: char = ord("e")
    l1: char = ord("l")
    l2: char = ord("l")
    o: char = ord("o")
    owned[0] = h
    owned[1] = e
    owned[2] = l1
    owned[3] = l2
    owned[4] = o
    s.adopt_span(owned)
    ar.release(p)
    self.assertEqual(len(s), 5)
    self.assertEqual(s[0], "h")
    ar.reset()


class ArenaEmptyAdoptTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    # 空 ``str`` 与 ``adopt_span`` 空 span
    s: str = ""
    empty: span[char] = new(None, 0, 1)
    s.adopt_span(empty)
    self.assertEqual(len(s), 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
