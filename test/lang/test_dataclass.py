"""``@dataclass`` 与 ``@copyable`` / ``@refcount`` 组合。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@dataclass
class Point:
  x: int
  y: int = 0


@dataclass(eq=False)
class Tag:
  name: str


@copyable
@dataclass
class CopyableBox:
  w: int
  h: int = 1


@dataclass
@refcount
class RefPoint:
  x: int
  y: int


@copyable
class WithFactory:
  items: list[int] @optional = []


@dataclass
class InnerBox:
  v: int = 0


@dataclass(eq=False, repr=False)
class WithNested:
  inner: InnerBox = new()


@dataclass
class WithOptional:
  required: int
  extra: int @optional = 99
  tags: list[str] @optional = []


@dataclass(frozen=True)
class FrozenPoint:
  x: int
  y: int = 0


@dataclass(order=True)
class OrderedRow:
  key: int
  label: str @optional = ""
  rank: int @optional = 0


@dataclass
class PostInitBox:
  w: int
  scale: int = 1
  area: int = 0

  def __post_init__(self):
    self.area = self.w * self.scale


class PointDataclassTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    p: Point = new(3, 4)
    self.assertEqual(p.x, 3)
    self.assertEqual(p.y, 4)
    p2: Point = new(1)
    self.assertEqual(p2.y, 0)
    self.assertNotEqual(p, p2)
    rp: str = repr(p)
    self.assertTrue(rp.startswith("Point("))


class TagDataclassTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    t: Tag = new("a")
    self.assertEqual(t.name, "a")


class CopyableDataclassTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    b: CopyableBox = new(w=10, h=20)
    self.assertEqual(b.w, 10)
    b2: CopyableBox = b
    self.assertEqual(b2.w, 10)
    self.assertEqual(b2.h, 20)


class RefcountDataclassTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    r: RefPoint = new(7, 8)
    self.assertEqual(r.x, 7)


class FactoryDefaultTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    wf: WithFactory = new()
    self.assertEqual(len(wf.items), 0)
    wf.items.append(1)
    self.assertEqual(wf.items[0], 1)


class NestedMakeDefaultTests(TestCaseMixin):
  _test_tag = 45

  @override
  def test(self):
    wn: WithNested = new()
    self.assertEqual(wn.inner.v, 0)
    custom: InnerBox = new()
    custom.v = 9
    wn2: WithNested = new(custom)
    self.assertEqual(wn2.inner.v, 9)


class OptionalFieldTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    wo: WithOptional = new(1)
    self.assertEqual(wo.required, 1)
    self.assertEqual(wo.extra, 99)
    self.assertEqual(len(wo.tags), 0)


class OrderedDataclassTests(TestCaseMixin):
  _test_tag = 55

  @override
  def test(self):
    a: OrderedRow = new(1)
    b: OrderedRow = new(2)
    c: OrderedRow = new(1)
    c.rank = 99
    self.assertTrue(a < b)
    self.assertTrue(b > a)
    self.assertTrue(a == c)
    self.assertTrue(a <= c)
    self.assertTrue(c >= a)


class PostInitTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    pb: PostInitBox = new(4, 3)
    self.assertEqual(pb.area, 12)
    pb2: PostInitBox = new(5)
    self.assertEqual(pb2.area, 5)


class FrozenDataclassTests(TestCaseMixin):
  _test_tag = 65

  @override
  def test(self):
    fp: FrozenPoint = new(3, 4)
    self.assertEqual(fp.x, 3)
    self.assertEqual(fp.y, 4)
    fp2: FrozenPoint = new(1)
    self.assertEqual(fp2.y, 0)
    fp2 = fp
    self.assertEqual(fp2.x, 3)
    self.assertEqual(fp2.y, 4)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
