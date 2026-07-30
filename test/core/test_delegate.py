"""``@delegate``、``Callable``、``Function`` 多播注册与调用。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@delegate
def Func[T](x: T) -> T: ...


@delegate
def Action(x: int) -> None: ...


@delegate
def Compare(a, b) -> int: ...


def _double(x: int) -> int:
  return x + x


def _inc(x: int) -> int:
  return x + 1


def _noop(x: int) -> None:
  pass


def _add(a: int, b: int) -> int:
  return a + b


def _triple(x: int) -> int:
  return x + x + x


def _prefix_text(s: str) -> str:
  return "fn:" + s


def add_inc(target: Func[int]) -> None:
  target += _inc


def call_target(target: Func[int], x: int) -> int:
  return target(x)


def attach_slot(d: Func[int], slot: Callable[[int], int]) -> None:
  d += slot


def detach_slot(d: Func[int], slot: Callable[[int], int]) -> None:
  d -= slot


def invoke_slot(slot: Callable[[int], int], x: int) -> int:
  return slot(x)


class HandlerBox:
  handler: Func[int] = new()

  def fire(self, x: int) -> int:
    return self.handler(x)


class SlotHolder:
  slot: Callable[[int], int]


class TextSlotHolder:
  slot: Callable[[str], str] = new()

  def call(self, s: str) -> str:
    return self.slot(s)


@copyable
class CopyBase:
  label: str = ""


@copyable
class CopyChild(CopyBase):
  value: int = 0


@copyable
class CopyCallableBox:
  slot: Callable[[str], str] = new()

  def call(self, s: str) -> str:
    return self.slot(s)


class SlotFactory:
  v: int = 0

  def make_slot(self) -> Callable[[int], int]:
    slot = lambda x: self.v + x
    return slot


class DelegateBasicTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    d: Func[int] = new()
    self.assertFalse(d)
    d += _inc
    self.assertTrue(d)
    self.assertEqual(d(5), 6)
    d += _double
    self.assertEqual(d(5), 10)
    d -= _inc
    self.assertEqual(d(5), 10)
    cb: Function[[int], int] = _double
    self.assertEqual(cb(3), 6)
    act: Action = new()
    act += _noop
    act(1)
    cmp: Compare[int, int] = new()
    cmp += _add
    self.assertEqual(cmp(2, 3), 5)
    lam_d: Func[int] = new()
    lam_d += lambda x: x + 1
    self.assertEqual(lam_d(5), 6)
    lam_d += _triple
    self.assertEqual(lam_d(5), 15)
    inc_lam = lambda x: x + 1
    cached_d: Func[int] = new()
    cached_d += inc_lam
    self.assertEqual(cached_d(5), 6)
    cached_d -= inc_lam
    self.assertFalse(cached_d)


class DelegateMemberTests(TestCaseMixin):
  _test_tag = 20

  v: int = 0

  def apply(self, x: int) -> int:
    self.v = x
    return self.v

  @override
  def test(self):
    d: Func[int] = new()
    d += self.apply
    self.assertEqual(d(7), 7)
    self.assertEqual(self.v, 7)
    d -= self.apply
    self.assertFalse(d)
    self.v = 0
    add_v = lambda x: self.v + x
    d += add_v
    self.assertEqual(d(3), 3)
    self.assertEqual(self.v, 0)
    self.v = 10
    self.assertEqual(d(3), 13)
    d -= add_v
    self.assertFalse(d)


class DelegateFieldTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    box: HandlerBox = new()
    self.assertFalse(box.handler)
    box.handler += _double
    self.assertTrue(box.handler)
    self.assertEqual(box.fire(4), 8)
    box.handler -= _double
    self.assertFalse(box.handler)


class CallableFieldTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    holder: SlotHolder = new()
    inc = lambda x: x + 1
    holder.slot = inc
    d: Func[int] = new()
    d += holder.slot
    self.assertEqual(d(5), 6)
    d -= holder.slot
    self.assertFalse(d)
    text: TextSlotHolder = new()
    text.slot = lambda s: "lam:" + s
    self.assertEqual(text.call("ok"), "lam:ok")
    text.slot = _prefix_text
    self.assertEqual(text.call("ok"), "fn:ok")


class CopyableInheritanceCallableTests(TestCaseMixin):
  _test_tag = 45

  @override
  def test(self):
    child: CopyChild = new()
    child.label = "base"
    child.value = 7
    copied: CopyChild = child
    self.assertEqual(copied.label, "base")
    self.assertEqual(copied.value, 7)
    items: list[CopyChild] = []
    items.append(child)
    self.assertEqual(items[0].label, "base")
    box: CopyCallableBox = new()
    box.slot = lambda s: "copy:" + s
    copied_box: CopyCallableBox = box
    self.assertEqual(copied_box.call("ok"), "copy:ok")


class DelegateParamTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    d: Func[int] = new()
    add_inc(d)
    self.assertEqual(call_target(d, 3), 4)
    d += _double
    self.assertEqual(call_target(d, 3), 6)


class CallableParamTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    d: Func[int] = new()
    slot = lambda x: x + 2
    self.assertEqual(invoke_slot(slot, 4), 6)
    attach_slot(d, slot)
    self.assertEqual(d(3), 5)
    detach_slot(d, slot)
    self.assertFalse(d)


class CallableLifetimeTests(TestCaseMixin):
  _test_tag = 70

  @override
  def test(self):
    factory: SlotFactory = new()
    factory.v = 10
    slot: Callable[[int], int] = factory.make_slot()
    self.assertEqual(slot(3), 13)
    factory.v = 20
    self.assertEqual(slot(3), 23)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
