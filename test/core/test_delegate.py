"""``@delegate``、``Callable``、``Function`` 多播注册与调用。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@delegate
def FuncDelegate[T](x: T) -> T: ...


@delegate
def ActionDelegate(x: int) -> None: ...


@delegate
def CompareDelegate(a, b) -> int: ...


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


def _prefixText(s: str) -> str:
  return "fn:" + s


def addInc(target: FuncDelegate[int]) -> None:
  target += _inc


def callTarget(target: FuncDelegate[int], x: int) -> int:
  return target(x)


def attachSlot(d: FuncDelegate[int], slot: Callable[[int], int]) -> None:
  d += slot


def detachSlot(d: FuncDelegate[int], slot: Callable[[int], int]) -> None:
  d -= slot


def invokeSlot(slot: Callable[[int], int], x: int) -> int:
  return slot(x)


class HandlerBox:
  handler: FuncDelegate[int] = new()

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

  def makeSlot(self) -> Callable[[int], int]:
    slot = lambda x: self.v + x
    return slot


class DelegateBasicTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    d: FuncDelegate[int] = new()
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
    act: ActionDelegate = new()
    act += _noop
    act(1)
    cmp: CompareDelegate[int, int] = new()
    cmp += _add
    self.assertEqual(cmp(2, 3), 5)
    lamD: FuncDelegate[int] = new()
    lamD += lambda x: x + 1
    self.assertEqual(lamD(5), 6)
    lamD += _triple
    self.assertEqual(lamD(5), 15)
    incLam = lambda x: x + 1
    cachedD: FuncDelegate[int] = new()
    cachedD += incLam
    self.assertEqual(cachedD(5), 6)
    cachedD -= incLam
    self.assertFalse(cachedD)


class DelegateMemberTests(TestCaseMixin):
  _testTag = 20

  v: int = 0

  def apply(self, x: int) -> int:
    self.v = x
    return self.v

  @override
  def test(self):
    d: FuncDelegate[int] = new()
    d += self.apply
    self.assertEqual(d(7), 7)
    self.assertEqual(self.v, 7)
    d -= self.apply
    self.assertFalse(d)
    self.v = 0
    addV = lambda x: self.v + x
    d += addV
    self.assertEqual(d(3), 3)
    self.assertEqual(self.v, 0)
    self.v = 10
    self.assertEqual(d(3), 13)
    d -= addV
    self.assertFalse(d)


class DelegateFieldTests(TestCaseMixin):
  _testTag = 30

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
  _testTag = 40

  @override
  def test(self):
    holder: SlotHolder = new()
    inc = lambda x: x + 1
    holder.slot = inc
    d: FuncDelegate[int] = new()
    d += holder.slot
    self.assertEqual(d(5), 6)
    d -= holder.slot
    self.assertFalse(d)
    text: TextSlotHolder = new()
    text.slot = lambda s: "lam:" + s
    self.assertEqual(text.call("ok"), "lam:ok")
    text.slot = _prefixText
    self.assertEqual(text.call("ok"), "fn:ok")


class CopyableInheritanceCallableTests(TestCaseMixin):
  _testTag = 45

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
    copiedBox: CopyCallableBox = box
    self.assertEqual(copiedBox.call("ok"), "copy:ok")


class DelegateParamTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    d: FuncDelegate[int] = new()
    addInc(d)
    self.assertEqual(callTarget(d, 3), 4)
    d += _double
    self.assertEqual(callTarget(d, 3), 6)


class CallableParamTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    d: FuncDelegate[int] = new()
    slot = lambda x: x + 2
    self.assertEqual(invokeSlot(slot, 4), 6)
    attachSlot(d, slot)
    self.assertEqual(d(3), 5)
    detachSlot(d, slot)
    self.assertFalse(d)


class CallableLifetimeTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    factory: SlotFactory = new()
    factory.v = 10
    slot: Callable[[int], int] = factory.makeSlot()
    self.assertEqual(slot(3), 13)
    factory.v = 20
    self.assertEqual(slot(3), 23)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
