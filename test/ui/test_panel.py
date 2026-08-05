"""``py2cpp.ui``：``UIPanelMixin`` + 多 ``@`` 元数据。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.meta import UIInvisibleMeta, UILabelMeta, UISliderMeta
from py2cpp.ui.panel import UIPanelMixin
from py2cpp.ui.window import UIWindow

class PanelInvisibleTests(TestCaseMixin):
    _test_tag = 2

    @override
    def test(self):
        cfg: PlayerConfig = new()
        cfg.draw_panel(UIWindow())
        self.assertEqual(cfg._seed, 0)

class PanelAutoExposeTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        cfg: PlayerConfig = new()
        cfg.draw_panel(UIWindow())
        self.assertEqual(cfg.hp, 50)
        self.assertEqual(cfg.name, 'hero')
        self.assertTrue(cfg.enabled)

class PanelSliderTests(TestCaseMixin):
    _test_tag = 3

    @override
    def test(self):
        cfg: PlayerConfig = new()
        cfg.hp = 99
        cfg.draw_panel(UIWindow())
        self.assertEqual(cfg.hp, 99)
        cfg.hp = 200
        self.assertEqual(cfg.hp, 200)

class PanelFloatTests(TestCaseMixin):
    _test_tag = 5

    @override
    def test(self):
        cfg: PlayerConfig = new()
        cfg.speed = 2.5
        cfg.draw_panel(UIWindow())
        self.assertTrue(cfg.speed > 2.4)
        self.assertTrue(cfg.speed < 2.6)

class PanelCreateTests(TestCaseMixin):
    _test_tag = 4

    @override
    def test(self):
        cfg: PlayerConfig = new()
        win: UIWindow = cfg.create_panel('My Panel', 480, 320)
        self.assertTrue(win.handle != 0)
        self.assertEqual(win.title, 'My Panel')
        win.close()
        win2: UIWindow = cfg.create_panel()
        self.assertTrue(win2.handle != 0)
        self.assertEqual(win2.title, 'PlayerConfig')
        win2.close()

@dataclass
class PlayerConfig(UIPanelMixin, friends=(PanelInvisibleTests, PanelFloatTests,)):
    hp: int @ UILabelMeta('HP') @ UISliderMeta(0, 100) = 50
    name: str @ UILabelMeta('Name') = 'hero'
    enabled: bool = True
    speed: float64 @ UILabelMeta('Speed') = 1.0
    _seed: int @ UIInvisibleMeta = 0

def main() -> int:
    suite: TestSuite = TestSuite()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
