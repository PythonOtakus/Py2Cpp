"""``@annotation`` 与 ``Self.iter_fields[Ann]`` / ``Self.iter_methods[Ann]`` / ``get_annotation`` 译期反射展开。"""
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
  def sum_tagged(self) -> int:
    total: int = 0
    for field in Self.iter_fields[TagMeta]():
      total += getattr(self, field)
    return total


class TaggedInts(SumTaggedMixin):
  alpha: int @TagMeta = 10
  beta: int @TagMeta = 5
  gamma: int = 100


@mixin
class CountMarkedMixin:
  def marked_field_count(self) -> int:
    count: int = 0
    for field in Self.iter_fields[MarkMeta]():
      count += 1
    return count


class MarkedStore(CountMarkedMixin):
  first: TagBox @property = new()
  second: TagBox @property = new()
  other: int = 0


@mixin
class MetaScanMixin:
  def meta_field_count(self) -> int:
    count: int = 0
    for field in Self.iter_fields(public_only=True):
      tagged = Self.get_annotation[Meta](field)
      if tagged is not None:
        count += 1
    return count


class MetaTaggedRow(MetaScanMixin):
  title: str @Meta = "hello"
  score: int @Meta = 1
  note: str = "plain"


@mixin
class ActionRunnerMixin:
  clicks: int = 0

  def run_labeled(self, button_label: str) -> None:
    for method in Self.iter_methods[ActionMeta]():
      label: str = method
      meta = Self.get_method_annotation[ActionMeta](method)
      if meta is not None and meta.label:
        label = meta.label
      if label == button_label:
        getattr(self, method)()


class ActionPanel(ActionRunnerMixin):
  @ActionMeta("Go")
  def go(self) -> None:
    self.clicks += 1

  @ActionMeta()
  def apply(self) -> None:
    self.clicks += 10


class AnnotationFieldTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    r: Row = new()
    self.assertEqual(r.headline(), "hello")
    r.title = "bye"
    self.assertEqual(r.title, "bye")


class IterAnnotatedFieldsMarkerTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    row: TaggedInts = new()
    self.assertEqual(row.sum_tagged(), 15)


class IterAnnotatedFieldsContainerTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    store: MarkedStore = new()
    self.assertEqual(store.marked_field_count(), 2)


class IterFieldsGetAnnotationTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    row: MetaTaggedRow = new()
    self.assertEqual(row.meta_field_count(), 2)


class IterAnnotatedMethodsTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    panel: ActionPanel = new()
    panel.run_labeled("Go")
    self.assertEqual(panel.clicks, 1)
    panel.run_labeled("apply")
    self.assertEqual(panel.clicks, 11)


@annotation(inheritable=True)
class InheritMeta:
  pass


class EntityBase:
  base_val: int @InheritMeta = 7


@mixin
class InheritScanMixin:
  def inherit_sum(self) -> int:
    total: int = 0
    for field in Self.iter_fields[InheritMeta](mro=True):
      total += getattr(self, field)
    return total


class DerivedEntity(InheritScanMixin, EntityBase):
  own_val: int = 3


@annotation(inheritable=True)
class MethodInheritMeta:
  pass


class MethodBase:
  @MethodInheritMeta()
  def base_hook(self) -> int:
    return 5


@mixin
class MethodInheritMixin:
  def call_inherited_hooks(self) -> int:
    total: int = 0
    for method in Self.iter_methods[MethodInheritMeta](mro=True):
      total += getattr(self, method)()
    return total


class DerivedMethods(MethodInheritMixin, MethodBase):
  @MethodInheritMeta()
  def own_hook(self) -> int:
    return 2


class AnnotationMroTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    row: DerivedEntity = new()
    self.assertEqual(row.inherit_sum(), 7)


class AnnotationMethodMroTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    obj: DerivedMethods = new()
    self.assertEqual(obj.call_inherited_hooks(), 7)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
