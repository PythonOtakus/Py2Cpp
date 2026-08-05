"""``py2cpp.ui.widget``：控件无窗口字段透传与 ``UIPushButton``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.meta import UIButtonMeta, UILabelMeta
from py2cpp.ui.panel import UIPanelMixin
from py2cpp.ui.widget import (
  UICheckBox,
  UIFloatEdit,
  UIIntEdit,
  UILineEdit,
  UIPushButton,
  UISlider,
)


class UICheckBoxNoWindowTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    cb: UICheckBox = new()
    cb.checked = True
    self.assertTrue(cb.checked)


class UILineEditNoWindowTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    le: UILineEdit = new()
    le.text = "hero"
    self.assertEqual(le.text, "hero")


class UIIntEditNoWindowTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    ie: UIIntEdit = new()
    ie.value = 42
    self.assertEqual(ie.value, 42)


class UIFloatEditNoWindowTests(TestCaseMixin):
  _test_tag = 35

  @override
  def test(self):
    fe: UIFloatEdit = new()
    fe.value = 3.5
    self.assertTrue(fe.value > 3.4)
    self.assertTrue(fe.value < 3.6)


class UISliderNoWindowTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    sl: UISlider = new()
    sl.value = 42
    sl.lo = 0
    sl.hi = 100
    self.assertEqual(sl.value, 42)


class UIButtonNoWindowTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    btn: UIPushButton = new()
    btn.text = "OK"
    self.assertEqual(btn.text, "OK")


class UIButtonLayoutTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    cfg: ButtonPanel = new()
    win = cfg.create_panel("Test", 480, 320)
    self.assertTrue(win.handle != 0)
    win.close()


class UIButtonHandlerTests(TestCaseMixin):
  _test_tag = 70

  @override
  def test(self):
    cfg: ButtonPanel = new()
    self.assertEqual(cfg.clicks, 0)
    cfg.apply()
    self.assertEqual(cfg.clicks, 1)


class UIButtonCustomLabelTests(TestCaseMixin):
  _test_tag = 80

  @override
  def test(self):
    cfg: ButtonPanel = new()
    cfg.save()
    self.assertEqual(cfg.clicks, 2)


@dataclass
class ButtonPanel(UIPanelMixin, friends=(UIButtonHandlerTests, UIButtonCustomLabelTests,)):
  name: str @UILabelMeta("Name") = "hero"
  action: str @UILabelMeta("Action") = "go"
  clicks: int @UILabelMeta("Clicks") = 0

  @UIButtonMeta()
  def apply(self) -> None:
    self.clicks += 1

  @UIButtonMeta("保存")
  def save(self) -> None:
    self.clicks += 2


def main() -> int:
  suite: TestSuite = TestSuite()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
