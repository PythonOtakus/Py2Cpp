"""``UIWindow`` Win32 后端：``show`` / ``drawPanel`` / ``close``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.app import UIApp
from py2cpp.ui.panel import UIPanelMixin
from py2cpp.ui.meta import UIInvisibleMeta, UILabelMeta, UISliderMeta
from py2cpp.ui.window import UIWindow


@dataclass
class DemoConfig(UIPanelMixin):
  hp: int @UILabelMeta("HP") @UISliderMeta(0, 100) = 42
  name: str @UILabelMeta("Name") = "player"
  enabled: bool = True
  _secret: int @UIInvisibleMeta = 7


class UIAppAvailableTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertTrue(UIApp.isAvailable())


class UIWindowBeginDrawTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    win: UIWindow = new()
    win.title = "Py2Cpp Panel"
    win.show(480, 320)
    self.assertTrue(win.handle != 0)
    cfg: DemoConfig = new()
    cfg.drawPanel(win)
    win.close()
    self.assertEqual(win.handle, 0)


class UIWindowTitlePropertyTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    win: UIWindow = new()
    win.title = "Before"
    win.show(320, 240)
    self.assertEqual(win.title, "Before")
    win.title = "After"
    self.assertEqual(win.title, "After")
    win.close()


class UIWindowResizeTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    win: UIWindow = new()
    win.title = "Resize"
    win.show(-1, -1)
    self.assertTrue(win.handle != 0)
    cfg: DemoConfig = new()
    cfg.drawPanel(win)
    win.resize(-1, -1)
    win.close()
    self.assertEqual(win.handle, 0)


def main() -> int:
  suite: TestSuite = TestSuite()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
