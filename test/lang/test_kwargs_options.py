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

  def apply_opts(self, opts: WindowOpts) -> None:
    self.width = opts.width
    self.height = opts.height
    self.title = opts.title


@dataclass
class WindowFromOpts:
  width: int = 0
  height: int = 0
  title: str = ""


def new_window(**kwargs: WindowOpts) -> Window:
  w: Window = new()
  w.apply_opts(kwargs)
  return w


def use_opts(**kwargs: WindowOpts) -> None:
  w: Window = new()
  w.apply_opts(kwargs)


def build_with_new() -> WindowOpts:
  return new(width=5, height=6, title="mk")


@dataclass
class Widget:
  value: int = 0

  def fresh(self) -> Self:
    return new(value=9)


class KwargsMakeWindowTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    w: Window = new_window(width=640, height=480, title="Hi")
    self.assertEqual(w.width, 640)
    self.assertEqual(w.height, 480)
    self.assertEqual(w.title, "Hi")

    relayed: Window = new_window(width=1, height=2, title="R")
    self.assertEqual(relayed.width, 1)


class KwargsCtorAssignTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    direct: Window = Window(width=100, height=200, title="Direct")
    self.assertEqual(direct.width, 100)
    self.assertEqual(direct.title, "Direct")

    from_opts: WindowFromOpts = WindowFromOpts(width=7, height=8, title="O")
    self.assertEqual(from_opts.width, 7)
    self.assertEqual(from_opts.title, "O")

    patched: Window = new()
    patched.assign(width=99, title="A")
    self.assertEqual(patched.width, 99)
    self.assertEqual(patched.title, "A")

    opts_only: WindowOpts = WindowOpts(width=10, height=20, title="x")
    self.assertEqual(opts_only.width, 10)

    use_opts(width=11, height=12, title="U")
    built: WindowOpts = build_with_new()
    self.assertEqual(built.width, 5)
    self.assertEqual(built.title, "mk")


class KwargsSelfMakeTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    base: Widget = new()
    wg: Widget = base.fresh()
    self.assertEqual(wg.value, 9)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
