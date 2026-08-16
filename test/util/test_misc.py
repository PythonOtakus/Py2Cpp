"""``py2cpp.util.misc``：``Counter`` 等（对齐 Python 3.13 ``collections.Counter``）。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class CounterGetitemTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    c: Counter[str] = new()
    self.assertEqual(c["x"], 0)
    self.assertFalse("x" in c)
    c["a"] = 2
    self.assertEqual(c["a"], 2)
    self.assertTrue("a" in c)
    self.assertEqual(c["b"], 0)


class CounterDictLiteralInitTests(TestCaseMixin):
  _testTag = 15

  @override
  def test(self):
    c: Counter[str] = {"a": 3, "b": 1}
    self.assertEqual(c["a"], 3)
    self.assertEqual(c["b"], 1)
    d: Counter[str] = new()
    d.update({"x": 2})
    self.assertEqual(d["x"], 2)


class CounterInitUpdateTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    items: list[str] = ["a", "b", "a"]
    c: Counter[str] = new()
    c.update(items)
    self.assertEqual(c["a"], 2)
    self.assertEqual(c["b"], 1)
    d: dict[str, int] = {"x": 3, "y": 1}
    c.update(d)
    self.assertEqual(c["x"], 3)
    self.assertEqual(c["y"], 1)
    more: list[str] = ["y", "z"]
    c.update(more)
    self.assertEqual(c["y"], 2)
    self.assertEqual(c["z"], 1)


class CounterSubtractTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    src: dict[str, int] = {"a": 3, "b": 1}
    c: Counter[str] = new()
    c.update(src)
    sub: dict[str, int] = {"a": 1, "b": 2}
    c.subtract(sub)
    self.assertEqual(c["a"], 2)
    self.assertEqual(c["b"], -1)
    drop: list[str] = ["a"]
    c.subtract(drop)
    self.assertEqual(c["a"], 1)


class CounterTotalMostCommonTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    src: dict[str, int] = {"a": 3, "b": 1, "c": 2}
    c: Counter[str] = new()
    c.update(src)
    self.assertEqual(c.total(), 6)
    top: list[tuple[str, int]] = c.mostCommon(2)
    self.assertEqual(len(top), 2)
    self.assertEqual(c["a"], 3)
    self.assertEqual(c["c"], 2)
    self.assertTrue(c["a"] >= c["c"])


class CounterElementsTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    elems: list[str] = ["x", "y", "x"]
    c: Counter[str] = new()
    c.update(elems)
    out: list[str] = []
    for ch in c.elements():
      out.append(ch)
    self.assertEqual(len(out), 3)
    self.assertEqual(out[0], "x")
    self.assertEqual(out[1], "x")
    self.assertEqual(out[2], "y")


class CounterOpsTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    am: dict[str, int] = {"a": 3, "b": 1}
    bm: dict[str, int] = {"a": 1, "b": 2}
    a: Counter[str] = new()
    a.update(am)
    b: Counter[str] = new()
    b.update(bm)
    s: Counter[str] = a + b
    self.assertEqual(s["a"], 4)
    self.assertEqual(s["b"], 3)
    d: Counter[str] = a - b
    self.assertEqual(d["a"], 2)
    self.assertFalse("b" in d)
    u: Counter[str] = a | b
    self.assertEqual(u["a"], 3)
    self.assertEqual(u["b"], 2)
    i: Counter[str] = a & b
    self.assertEqual(i["a"], 1)
    self.assertEqual(i["b"], 1)
    self.assertFalse("z" in i)
    rawM: dict[str, int] = {"a": 1, "b": -1}
    raw: Counter[str] = new()
    raw.update(rawM)
    p: Counter[str] = raw.__pos__()  # py2cpp: strict-off
    self.assertEqual(len(p), 1)
    self.assertEqual(p["a"], 1)
    negM: dict[str, int] = {"a": -2}
    negSrc: Counter[str] = new()
    negSrc.update(negM)
    n: Counter[str] = -negSrc
    self.assertEqual(n["a"], 2)


class CounterEqCopyTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    m: dict[int, int] = {1: 2, 2: 1}
    c1: Counter[int] = new()
    c1.update(m)
    c2: Counter[int] = c1.copy()
    self.assertTrue(c1 == c2)
    c2[2] = 0
    self.assertFalse(c1 == c2)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
