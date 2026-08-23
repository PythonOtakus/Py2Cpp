"""容器回归：``list``、unpack/comprehension。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def _negKey(v: int) -> int:
  return -v


class ListBasicsTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    empty: list[int] = []
    self.assertEqual(len(empty), 0)
    self.assertFalse(empty)
    xs: list[int] = [10, 20, 30]
    self.assertEqual(len(xs), 3)
    self.assertTrue(xs)
    self.assertEqual(xs[0], 10)
    self.assertEqual(xs[1], 20)
    self.assertEqual(xs[-1], 30)
    self.assertEqual(xs[-2], 20)
    xs[1] = 25
    self.assertEqual(xs[1], 25)
    copy1: list[int] = xs.copy()
    self.assertTrue(copy1 == xs)
    self.assertEqual(copy1[0], 10)


class ContainerMoveAssignTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    a: list[int] = [1, 2, 3]
    b: list[int] = a
    self.assertEqual(len(b), 3)
    self.assertTrue(a.__moved__)
    s: set[int] = {7, 8}
    t: set[int] = s
    self.assertEqual(len(t), 2)
    self.assertTrue(s.__moved__)
    d1: dict[int, int] = {1: 10}
    d2: dict[int, int] = d1
    self.assertEqual(len(d2), 1)
    self.assertTrue(d1.__moved__)


class ListAppendExtendTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    xs: list[int] = []
    xs.append(1)
    xs.append(2)
    self.assertEqual(len(xs), 2)
    self.assertEqual(xs[1], 2)
    ys: list[int] = [3, 4]
    xs.extend(ys)
    self.assertEqual(len(xs), 4)
    self.assertEqual(xs[2], 3)
    zs: list[int] = []
    for i in range(3):
      zs.append(i)
    self.assertEqual(len(zs), 3)
    self.assertEqual(zs[2], 2)


class ListInsertPopRemoveTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    xs.insert(0, 0)
    self.assertEqual(xs[0], 0)
    self.assertEqual(len(xs), 4)
    xs.insert(2, 99)
    self.assertEqual(xs[2], 99)
    xs.insert(100, 7)
    self.assertEqual(xs[-1], 7)
    self.assertEqual(xs.pop(), 7)
    self.assertEqual(xs.pop(0), 0)
    self.assertEqual(len(xs), 4)
    xs.remove(99)
    self.assertFalse(99 in xs)
    self.assertEqual(len(xs), 3)
    xs.clear()
    self.assertEqual(len(xs), 0)
    self.assertFalse(xs)


class ListDelTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    xs: list[int] = [10, 20, 30, 40]
    del xs[1]
    self.assertEqual(len(xs), 3)
    self.assertEqual(xs[0], 10)
    self.assertEqual(xs[1], 30)
    del xs[:2]
    self.assertEqual(len(xs), 1)
    self.assertEqual(xs[0], 40)


class ListSearchTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    xs: list[int] = [1, 2, 3, 2, 1]
    self.assertEqual(xs.count(2), 2)
    self.assertEqual(xs.count(9), 0)
    self.assertEqual(xs.index(2), 1)
    self.assertEqual(xs.index(2, 2), 3)
    self.assertTrue(2 in xs)
    self.assertFalse(8 in xs)
    self.assertEqual(xs.index(1), 0)
    self.assertEqual(xs.index(1, 1), 4)


class ListSortReverseTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    xs: list[int] = [3, 1, 4, 1, 5]
    xs.sort()
    self.assertEqual(xs[0], 1)
    self.assertEqual(xs[1], 1)
    self.assertEqual(xs[4], 5)
    ys: list[int] = [3, 1, 4]
    ys.sort(None, True)
    self.assertEqual(ys[0], 4)
    self.assertEqual(ys[2], 1)
    zs: list[int] = [1, 2, 3]
    zs.sort(_negKey, False)
    self.assertEqual(zs[0], 3)
    self.assertEqual(zs[2], 1)
    rev: list[int] = [1, 2, 3, 4]
    rev.reverse()
    self.assertEqual(rev[0], 4)
    self.assertEqual(rev[3], 1)


class ListSliceTests(TestCaseMixin):
  _testTag = 80

  @override
  def test(self):
    xs: list[int] = [0, 1, 2, 3, 4, 5]
    mid: list[int] = xs[1:4]
    self.assertEqual(len(mid), 3)
    self.assertEqual(mid[0], 1)
    self.assertEqual(mid[2], 3)
    step2: list[int] = xs[:6:2]
    self.assertEqual(len(step2), 3)
    self.assertEqual(step2[1], 2)
    back: list[int] = xs[::-1]
    self.assertEqual(len(back), 6)
    self.assertEqual(back[0], 5)
    self.assertEqual(back[5], 0)
    tail: list[int] = xs[3:]
    self.assertEqual(len(tail), 3)
    self.assertEqual(tail[0], 3)


class ListAlgebraTests(TestCaseMixin):
  _testTag = 90

  @override
  def test(self):
    a: list[int] = [1, 2]
    b: list[int] = [3, 4]
    c: list[int] = a + b
    self.assertEqual(len(c), 4)
    self.assertEqual(c[2], 3)
    a += b
    self.assertEqual(len(a), 4)
    self.assertEqual(a[3], 4)
    d: list[int] = [1, 2]
    e: list[int] = d * 3
    self.assertEqual(len(e), 6)
    self.assertEqual(e[0], 1)
    self.assertEqual(e[5], 2)
    f: list[int] = [1, 2]
    g: list[int] = 2 * f
    self.assertEqual(len(g), 4)
    h: list[int] = [1, 2]
    h *= 2
    self.assertEqual(len(h), 4)
    one: list[int] = [1]
    z: list[int] = one * 0
    self.assertEqual(len(z), 0)
    self.assertFalse(a == b)


class ThreeInts:
  """仅有 ``__len__`` + ``__getitem__(int)``；翻译期注入 ``ThreeInts_iterator`` 与 ``__iter__``。"""

  _a: int = 10
  _b: int = 20
  _c: int = 30

  @immutable
  def __len__(self) -> int:
    return 3

  @immutable
  def __getitem__(self, i: int) -> int:
    if i == 0:
      return self._a
    if i == 1:
      return self._b
    return self._c


class EmptySeq:
  """空序列：默认 ``__bool__`` 为假（``__len__`` → 0）。"""

  @immutable
  def __len__(self) -> int:
    return 0

  @immutable
  def __getitem__(self, i: int) -> int:
    return 0


class DefaultSeqIterTests(TestCaseMixin):
  _testTag = 100

  @override
  def test(self):
    s: ThreeInts = new()
    total: int = 0
    n: int = 0
    for x in s:
      n += 1
      total += x
    self.assertEqual(n, 3)
    self.assertEqual(total, 60)
    self.assertTrue(s)
    e: EmptySeq = new()
    self.assertFalse(e)
    emptySum: int = 0
    for v in e:
      emptySum += v
    self.assertEqual(emptySum, 0)


class ListIterTests(TestCaseMixin):
  _testTag = 110

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    n: int = 0
    s: int = 0
    for x in xs:
      n += 1
      s += x
    self.assertEqual(n, 3)
    self.assertEqual(s, 6)
    revSum: int = 0
    rev: list[int] = xs[::-1]
    for val in rev:
      revSum += val
    self.assertEqual(revSum, 6)
    acc: list[int] = []
    for val in xs:
      acc.append(val)
    self.assertEqual(len(acc), 3)
    self.assertEqual(acc[0], 1)
    self.assertEqual(acc[2], 3)
    revBuiltin: int = 0
    for x in reversed(xs):
      revBuiltin += x
    self.assertEqual(revBuiltin, 6)


class ListEnumerateTests(TestCaseMixin):
  _testTag = 115

  @override
  def test(self):
    xs: list[int] = [10, 20, 30]
    sumIdx: int = 0
    for i, x in enumerate(xs):
      sumIdx += i + x
    self.assertEqual(sumIdx, 63)
    lastIdx: int = 0
    for idx, x in enumerate(xs, 10):
      lastIdx = idx
    self.assertEqual(lastIdx, 12)
    comp: list[int] = [x for i, x in enumerate(xs) if i > 0]
    self.assertEqual(len(comp), 2)
    self.assertEqual(comp[0], 20)


class ListStrTests(TestCaseMixin):
  _testTag = 120

  @override
  def test(self):
    words: list[str] = []
    words.append("a")
    words.append("b")
    words.append("c")
    self.assertEqual(len(words), 3)
    self.assertEqual(words[1], "b")
    joined: str = "-".join(words)
    self.assertEqual(joined, "a-b-c")
    dup: list[str] = words.copy()
    self.assertTrue(dup == words)
    dup[0] = "z"
    self.assertFalse(dup == words)


class ListLiteralTests(TestCaseMixin):
  _testTag = 130

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    self.assertEqual(len(xs), 3)
    self.assertEqual(xs[0], 1)
    self.assertEqual(xs[2], 3)


class ListUnpackTests(TestCaseMixin):
  _testTag = 140

  @override
  def test(self):
    mid: list[int] = [2, 3]
    xs: list[int] = [1, *mid, 4]
    self.assertEqual(len(xs), 4)
    self.assertEqual(xs[0], 1)
    self.assertEqual(xs[1], 2)
    self.assertEqual(xs[3], 4)
    ys: list[int] = [10, 20]
    zs: list[int] = [*ys]
    self.assertEqual(len(zs), 2)
    self.assertEqual(zs[1], 20)


class ListComprehensionTests(TestCaseMixin):
  _testTag = 150

  @override
  def test(self):
    src: list[int] = [1, 2, 3, 4, 5]
    out: list[int] = [x * 2 for x in src if x > 2]
    self.assertEqual(len(out), 3)
    self.assertEqual(out[0], 6)
    self.assertEqual(out[2], 10)
    rng: list[int] = [i * 2 for i in range(5)]
    self.assertEqual(len(rng), 5)
    self.assertEqual(rng[4], 8)
    grid: list[int] = [i * j for i in range(3) for j in range(3)]
    self.assertEqual(len(grid), 9)
    self.assertEqual(grid[8], 4)


class FrozenListTests(TestCaseMixin):
  _testTag = 208

  @override
  def test(self):
    empty: frozenlist[int] = []
    self.assertEqual(len(empty), 0)
    fl: frozenlist[int] = [1, 2, 3]
    self.assertEqual(len(fl), 3)
    self.assertEqual(fl[0], 1)
    self.assertEqual(fl[2], 3)
    self.assertTrue(2 in fl)
    seen: list[int] = []
    for x in fl:
      seen.append(x)
    self.assertEqual(len(seen), 3)
    other: frozenlist[int] = [1, 2, 3]
    self.assertTrue(fl == other)
    lit: frozenlist[int] = [4, 5, 6]
    fromList: list[int] = [1, 2]
    comp: frozenlist[int] = [x + 10 for x in fromList]
    self.assertEqual(len(comp), 2)
    self.assertEqual(comp[0], 11)
    self.assertEqual(len(lit), 3)
    self.assertEqual(lit[1], 5)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
