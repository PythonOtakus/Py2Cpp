"""``UIStyle`` / ``UIWindow.style`` 默认值与 tuple 字段。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.style import UIStyle
from py2cpp.ui.window import UIWindow


class UIStyleDefaultTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    st: UIStyle = new()
    self.assertEqual(st.font_name, "Segoe UI")
    self.assertEqual(st.font_size, 11)
    self.assertEqual(st.text_color[0], 0)
    self.assertEqual(st.panel_color[2], 243)
    self.assertEqual(st.margin[0], 12)
    self.assertEqual(st.margin[1], 10)
    self.assertEqual(st.edit_size[0], 260)
    self.assertEqual(st.edit_size[1], 22)
    self.assertEqual(st.row_spacing, 4)
    self.assertEqual(st.form_spacing, 8)


class UIWindowStyleTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    win: UIWindow = new()
    self.assertEqual(win.next_y, 10)
    self.assertEqual(win.style.checkbox_size[1], 18)
    win.style.edit_size = (300, 28)
    self.assertEqual(win.style.edit_size[0], 300)


def main() -> int:
  suite: TestSuite = TestSuite()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
