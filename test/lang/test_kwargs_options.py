"""``**kwargs: Options``、构造关键字、``assign``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@dataclass
class WindowOpts:
  width: int = 0
  height: int = 0
  title: str = ""


@dataclass
class Window:
  width: int = 0
  height: int = 0
  title: str = ""

  def applyOpts(self, opts: WindowOpts) -> None:
    self.width = opts.width
    self.height = opts.height
    self.title = opts.title


@dataclass
class WindowFromOpts:
  width: int = 0
  height: int = 0
  title: str = ""


def newWindow(**kwargs: WindowOpts) -> Window:
  w: Window = new()
  w.applyOpts(kwargs)
  return w


def useOpts(**kwargs: WindowOpts) -> None:
  w: Window = new()
  w.applyOpts(kwargs)


def buildWithNew() -> WindowOpts:
  return new(width=5, height=6, title="mk")


@dataclass
class Widget:
  value: int = 0

  def fresh(self) -> Self:
    return new(value=9)


class KwargsMakeWindowTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    w: Window = newWindow(width=640, height=480, title="Hi")
    self.assertEqual(w.width, 640)
    self.assertEqual(w.height, 480)
    self.assertEqual(w.title, "Hi")

    relayed: Window = newWindow(width=1, height=2, title="R")
    self.assertEqual(relayed.width, 1)


class KwargsCtorAssignTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    direct: Window = Window(width=100, height=200, title="Direct")
    self.assertEqual(direct.width, 100)
    self.assertEqual(direct.title, "Direct")

    fromOpts: WindowFromOpts = WindowFromOpts(width=7, height=8, title="O")
    self.assertEqual(fromOpts.width, 7)
    self.assertEqual(fromOpts.title, "O")

    patched: Window = new()
    patched.assign(width=99, title="A")
    self.assertEqual(patched.width, 99)
    self.assertEqual(patched.title, "A")

    optsOnly: WindowOpts = WindowOpts(width=10, height=20, title="x")
    self.assertEqual(optsOnly.width, 10)

    useOpts(width=11, height=12, title="U")
    built: WindowOpts = buildWithNew()
    self.assertEqual(built.width, 5)
    self.assertEqual(built.title, "mk")


class KwargsSelfMakeTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    base: Widget = new()
    wg: Widget = base.fresh()
    self.assertEqual(wg.value, 9)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
