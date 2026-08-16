"""容器回归：``dict`` / ``frozendict``。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class DictBasicsTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    d: dict[int, int] = {}
    self.assertEqual(len(d), 0)
    self.assertFalse(1 in d)
    d[10] = 100
    d[20] = 200
    self.assertEqual(len(d), 2)
    self.assertTrue(10 in d)
    self.assertEqual(d[10], 100)
    self.assertEqual(d.get(20, 0), 200)
    self.assertEqual(d.get(99, -1), -1)


class DictMutationTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    d: dict[int, int] = {}
    d[1] = 10
    d[2] = 20
    d[1] = 11
    self.assertEqual(d[1], 11)
    self.assertEqual(len(d), 2)
    d.setDefault(3, 30)
    self.assertEqual(d[3], 30)
    self.assertEqual(d.setDefault(3, 99), 30)
    d.clear()
    self.assertEqual(len(d), 0)


class DictDelTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    d: dict[int, int] = {1: 10, 2: 20, 3: 30}
    del d[2]
    self.assertEqual(len(d), 2)
    self.assertFalse(2 in d)
    self.assertEqual(d[1], 10)
    self.assertEqual(d[3], 30)


class DictPopTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    d: dict[int, int] = {}
    d[1] = 10
    d[2] = 20
    v: int = d.pop(1)
    self.assertEqual(v, 10)
    self.assertFalse(1 in d)
    self.assertEqual(d.get(9, 0), 0)
    d[3] = 30
    d[4] = 40
    pair: (int, int) = d.popItem()
    self.assertEqual(pair[0], 4)
    self.assertEqual(pair[1], 40)
    self.assertEqual(len(d), 2)


class DictLiteralTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    lit: dict[int, int] = {1: 10, 2: 20, 3: 30}
    self.assertEqual(len(lit), 3)
    self.assertEqual(lit[2], 20)
    self.assertTrue(3 in lit)


class DictViewTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    d: dict[int, int] = {}
    d[1] = 10
    d[2] = 20
    d[3] = 30
    self.assertEqual(len(d.keys()), 3)
    sumK: int = 0
    for k in d:
      sumK += k
    self.assertEqual(sumK, 6)
    sumV: int = 0
    for v in d.values():
      sumV += v
    self.assertEqual(sumV, 60)
    count: int = 0
    for item in d.items():
      count += 1
      self.assertEqual(item[1], item[0] * 10)
    self.assertEqual(count, 3)


class DictOrderTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    d: dict[int, int] = {}
    d[1] = 1
    d[2] = 2
    d[3] = 3
    last: int = 0
    for k in d:
      last = k
    self.assertEqual(last, 3)
    p3: (int, int) = d.popItem()
    p2: (int, int) = d.popItem()
    p1: (int, int) = d.popItem()
    self.assertEqual(p3[0], 3)
    self.assertEqual(p2[0], 2)
    self.assertEqual(p1[0], 1)


class DictCopyUpdateTests(TestCaseMixin):
  _testTag = 80

  @override
  def test(self):
    a: dict[int, int] = {}
    a[1] = 10
    a[2] = 20
    b: dict[int, int] = a.copy()
    self.assertTrue(a == b)
    b[2] = 99
    self.assertFalse(a == b)
    a.update(b)
    self.assertEqual(a[2], 99)
    keys: list[int] = []
    keys.append(5)
    keys.append(6)
    keys.append(7)
    c: dict[int, int] = dict.fromKeys(keys, 0)
    self.assertEqual(len(c), 3)
    self.assertEqual(c[6], 0)


class DictMergeTests(TestCaseMixin):
  _testTag = 90

  @override
  def test(self):
    a: dict[int, int] = {}
    a[1] = 10
    b: dict[int, int] = {}
    b[2] = 20
    b[1] = 99
    m: dict[int, int] = a | b
    self.assertEqual(m[1], 99)
    self.assertEqual(m[2], 20)
    a |= b
    self.assertEqual(a[1], 99)


class DictGrowTests(TestCaseMixin):
  _testTag = 100

  @override
  def test(self):
    d: dict[int, int] = {}
    for i in range(32):
      d[i] = i * 10
    self.assertEqual(len(d), 32)
    self.assertEqual(d[31], 310)


class DictUnpackTests(TestCaseMixin):
  _testTag = 110

  @override
  def test(self):
    base: dict[int, int] = {1: 10, 2: 20}
    merged: dict[int, int] = {**base, 3: 30}
    self.assertEqual(len(merged), 3)
    self.assertEqual(merged[1], 10)
    self.assertEqual(merged[3], 30)


class DictComprehensionTests(TestCaseMixin):
  _testTag = 120

  @override
  def test(self):
    keys: list[int] = [1, 2, 3]
    m: dict[int, int] = {k: k * 10 for k in keys if k != 2}
    self.assertEqual(len(m), 2)
    self.assertEqual(m[1], 10)
    self.assertEqual(m[3], 30)


class DictCopyTests(TestCaseMixin):
  _testTag = 130

  @override
  def test(self):
    d: dict[int, int] = {}
    d[1] = 10
    d2: dict[int, int] = d.copy()
    self.assertEqual(len(d2), 1)
    self.assertEqual(d2[1], 10)


class FrozenDictTests(TestCaseMixin):
  _testTag = 140

  @override
  def test(self):
    empty: frozendict[int, int] = {}
    self.assertEqual(len(empty), 0)
    d: dict[int, int] = {1: 10, 2: 20}
    fd: frozendict[int, int] = new(d)
    self.assertEqual(len(fd), 2)
    self.assertEqual(fd[1], 10)
    self.assertTrue(2 in fd)
    keys: list[int] = []
    for k in fd:
      keys.append(k)
    self.assertEqual(len(keys), 2)
    self.assertTrue(1 in keys)
    self.assertTrue(2 in keys)
    vals: list[int] = []
    for v in fd.values():
      vals.append(v)
    self.assertEqual(len(vals), 2)
    dup: frozendict[int, int] = new(fd)
    self.assertTrue(fd == dup)
    lit: frozendict[int, int] = {3: 30, 4: 40}
    self.assertEqual(len(lit), 2)
    self.assertEqual(lit[3], 30)
    keys: list[int] = [1, 2]
    comp: frozendict[int, int] = {k: k * 10 for k in keys}
    self.assertEqual(len(comp), 2)
    self.assertEqual(comp[2], 20)



def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
