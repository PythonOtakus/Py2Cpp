"""``@annotation`` 与 ``Self.iterFields[Ann]`` / ``Self.iterMethods[Ann]`` / ``get_annotation`` 译期反射展开。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@annotation
class Meta:
  pass


@annotation
class TagMeta:
  pass


@annotation
class MarkMeta:
  pass


@annotation
@dataclass
class ActionMeta:
  label: str = ""


class Row:
  title: str @Meta = "hello"

  def headline(self) -> str:
    return self.title


@MarkMeta
class TagBox:
  v: int = 0


@mixin
class SumTaggedMixin:
  def sumTagged(self) -> int:
    total: int = 0
    for field in Self.iterFields[TagMeta]():
      total += getattr(self, field)
    return total


class TaggedInts(SumTaggedMixin):
  alpha: int @TagMeta = 10
  beta: int @TagMeta = 5
  gamma: int = 100


@mixin
class CountMarkedMixin:
  def markedFieldCount(self) -> int:
    count: int = 0
    for field in Self.iterFields[MarkMeta]():
      count += 1
    return count


class MarkedStore(CountMarkedMixin):
  first: TagBox @property = new()
  second: TagBox @property = new()
  other: int = 0


@mixin
class MetaScanMixin:
  def metaFieldCount(self) -> int:
    count: int = 0
    for field in Self.iterFields(publicOnly=True):
      tagged = Self.getFieldAnnotation[Meta](field)
      if tagged is not None:
        count += 1
    return count


class MetaTaggedRow(MetaScanMixin):
  title: str @Meta = "hello"
  score: int @Meta = 1
  note: str = "plain"


@mixin
class FieldTypeMixin:
  def taggedTotal(self) -> int:
    total: int = 0
    for field in Self.iterFields[TagMeta]():
      value: Self.getFieldType(field) = getattr(self, field)
      total += value
    return total


class TypedTaggedInts(FieldTypeMixin):
  first: int @TagMeta = 7
  second: int @TagMeta = 9
  ignored: str = "ignored"


@mixin
class ActionRunnerMixin:
  clicks: int = 0

  def runLabeled(self, buttonLabel: str) -> None:
    for method in Self.iterMethods[ActionMeta]():
      label: str = method
      meta = Self.getMethodAnnotation[ActionMeta](method)
      if meta is not None and meta.label:
        label = meta.label
      if label == buttonLabel:
        getattr(self, method)()


class ActionPanel(ActionRunnerMixin):
  @ActionMeta("Go")
  def go(self) -> None:
    self.clicks += 1

  @ActionMeta()
  def apply(self) -> None:
    self.clicks += 10


class AnnotationFieldTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    r: Row = new()
    self.assertEqual(r.headline(), "hello")
    r.title = "bye"
    self.assertEqual(r.title, "bye")


class IterAnnotatedFieldsMarkerTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    row: TaggedInts = new()
    self.assertEqual(row.sumTagged(), 15)


class IterAnnotatedFieldsContainerTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    store: MarkedStore = new()
    self.assertEqual(store.markedFieldCount(), 2)


class FieldTypeReflectTests(TestCaseMixin):
  _testTag = 25

  @override
  def test(self):
    row: TypedTaggedInts = new()
    self.assertEqual(row.taggedTotal(), 16)


class IterFieldsGetAnnotationTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    row: MetaTaggedRow = new()
    self.assertEqual(row.metaFieldCount(), 2)


class IterAnnotatedMethodsTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    panel: ActionPanel = new()
    panel.runLabeled("Go")
    self.assertEqual(panel.clicks, 1)
    panel.runLabeled("apply")
    self.assertEqual(panel.clicks, 11)


@annotation(inheritable=True)
class InheritMeta:
  pass


class EntityBase:
  baseVal: int @InheritMeta = 7


@mixin
class InheritScanMixin:
  def inheritSum(self) -> int:
    total: int = 0
    for field in Self.iterFields[InheritMeta](mro=True):
      total += getattr(self, field)
    return total


class DerivedEntity(InheritScanMixin, EntityBase):
  ownVal: int = 3


@annotation(inheritable=True)
class MethodInheritMeta:
  pass


class MethodBase:
  @MethodInheritMeta()
  def baseHook(self) -> int:
    return 5


@mixin
class MethodInheritMixin:
  def callInheritedHooks(self) -> int:
    total: int = 0
    for method in Self.iterMethods[MethodInheritMeta](mro=True):
      total += getattr(self, method)()
    return total


class DerivedMethods(MethodInheritMixin, MethodBase):
  @MethodInheritMeta()
  def ownHook(self) -> int:
    return 2


class AnnotationMroTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    row: DerivedEntity = new()
    self.assertEqual(row.inheritSum(), 7)


class AnnotationMethodMroTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    obj: DerivedMethods = new()
    self.assertEqual(obj.callInheritedHooks(), 7)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
