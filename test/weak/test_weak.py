"""``py2cpp.weak``：对齐 CPython 3.13 ``weakref`` 子集。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.weak import WeakList, WeakRef, WeakValueDict


@dataclass(eq=False, repr=True)
@refcount
class Node:
  name: str = ""
  value: int = 0


class WeakRefTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    n: Node = new("a", 1)
    w: WeakRef[Node] = new(n)
    self.assertTrue(w.alive)
    live: Node = w.value
    self.assertEqual(live.name, "a")
    n = new()
    live = new()
    self.assertFalse(w.alive)


class WeakValueDictTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    cache: WeakValueDict[str, Node] = new()
    n: Node = new("cached", 42)
    cache["k"] = n
    got: Node = cache["k"]
    self.assertEqual(got.value, 42)
    self.assertEqual(len(cache.keys()), 1)
    self.assertEqual(len(cache.valuerefs()), 1)
    pair: (str, Node) = cache.popitem()
    n = new()
    self.assertFalse("k" in cache)


class WeakListTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    lst: WeakList[Node] = new()
    n: Node = new("y", 0)
    lst.append(n)
    self.assertEqual(len(lst), 1)
    item: Node = lst[0]
    self.assertEqual(item.name, "y")
    item = new()
    n = new()
    self.assertEqual(len(lst), 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
