"""``UIStyle`` / ``UIWindow.style`` 默认值与 tuple 字段。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.style import UIStyle
from py2cpp.ui.window import UIWindow


class UIStyleDefaultTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    st: UIStyle = new()
    self.assertEqual(st.fontName, "Segoe UI")
    self.assertEqual(st.fontSize, 11)
    self.assertEqual(st.textColor[0], 0)
    self.assertEqual(st.panelColor[2], 243)
    self.assertEqual(st.margin[0], 12)
    self.assertEqual(st.margin[1], 10)
    self.assertEqual(st.editSize[0], 260)
    self.assertEqual(st.editSize[1], 22)
    self.assertEqual(st.rowSpacing, 4)
    self.assertEqual(st.formSpacing, 8)


class UIWindowStyleTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    win: UIWindow = new()
    self.assertEqual(win.nextY, 10)
    self.assertEqual(win.style.checkboxSize[1], 18)
    win.style.editSize = (300, 28)
    self.assertEqual(win.style.editSize[0], 300)


def main() -> int:
  suite: TestSuite = TestSuite()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
