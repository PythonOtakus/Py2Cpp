"""``py2cpp.ui.canvas``：绘制命令与视口变换。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.canvas import DrawCmd, DrawCmdEnum, UICanvas, UICanvasFont, UIPaintContext, _bezierControls

class DrawCmdTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        cmd: DrawCmd = new()
        cmd.kind = DrawCmdEnum.FillRect
        cmd.x = 1
        cmd.y = 2
        cmd.w = 10
        cmd.h = 20
        cmd.r = 30
        self.assertEqual(cmd.kind, DrawCmdEnum.FillRect)
        self.assertEqual(cmd.w, 10)

class CanvasViewportTests(TestCaseMixin):
    _testTag = 2

    @override
    def test(self):
        c: UICanvas = new()
        c.panX = 10.0
        c.panY = 20.0
        c.zoom = 2.0
        sx, sy = c.worldToScreen(5.0, 5.0)
        self.assertEqual(sx, 30.0)
        self.assertEqual(sy, 50.0)
        wx, wy = c.screenToWorld(sx, sy)
        self.assertEqual(wx, 5.0)
        self.assertEqual(wy, 5.0)

class CanvasWheelZoomTests(TestCaseMixin):
    _testTag = 4

    @override
    def test(self):
        c: UICanvas = new()
        c.zoom = 1.0
        c.panX = 0.0
        c.panY = 0.0
        wantIn: float64 = 1.1
        c.onWheel(120, 100, 100)
        self.assertEqual(c.zoom, wantIn)
        wx, wy = c.screenToWorld(100.0, 100.0)
        self.assertEqual(wx, 100.0)
        self.assertEqual(wy, 100.0)
        wantOut: float64 = 1.0
        c.onWheel(-120, 100, 100)
        self.assertEqual(c.zoom, wantOut)

class CanvasFontScaleTests(TestCaseMixin):
    _testTag = 5

    @override
    def test(self):
        ctx: UIPaintContext = new()
        font: UICanvasFont = new()
        font.size = 11
        ctx.beginFrame(0, 640, 480, font, 2.0)
        self.assertEqual(ctx.scaledFontSize(), 22)
        ctx.beginFrame(0, 640, 480, font, 0.5)
        self.assertEqual(ctx.scaledFontSize(), 5)

class PaintContextTests(TestCaseMixin):
    _testTag = 3

    @override
    def test(self):
        ctx: UIPaintContext = new()
        font: UICanvasFont = new()
        font.name = 'Arial'
        font.size = 12
        ctx.beginFrame(0, 640, 480, font)
        ctx.fillRect(0, 0, 100, 50, (255, 0, 0))
        ctx.drawLine(0, 0, 10, 10, (0, 255, 0), 2)
        self.assertEqual(ctx.cmdCount(), 2)

class RoundRectCmdTests(TestCaseMixin):
    _testTag = 6

    @override
    def test(self):
        ctx: UIPaintContext = new()
        ctx.beginFrame(0, 640, 480, UICanvasFont())
        ctx.fillRoundRect(10, 20, 100, 80, 8, (0, 122, 204))
        ctx.strokeRoundRect(10, 20, 100, 80, 8, (255, 198, 0), 2)
        ctx.fillRectInRoundClip(10, 20, 100, 28, 100, 80, 8, (0, 122, 204))
        ctx.drawText(14, 20, 90, 28, 'Title', (240, 240, 240), 1)
        self.assertEqual(ctx.cmdCount(), 4)

class BezierControlsTests(TestCaseMixin):
    _testTag = 7

    @override
    def test(self):
        cx1, cy1, cx2, cy2 = _bezierControls(0, 10, 100, 50)
        self.assertEqual(cx1, 50)
        self.assertEqual(cy1, 10)
        self.assertEqual(cx2, 50)
        self.assertEqual(cy2, 50)
        sx1, _, sx2, _ = _bezierControls(0, 0, 20, 0)
        self.assertEqual(sx1, 20)
        self.assertEqual(sx2, 0)

class CommitDispatchTests(TestCaseMixin):
    _testTag = 8

    @override
    def test(self):
        ctx: UIPaintContext = new()
        ctx.beginFrame(0, 640, 480, UICanvasFont())
        ctx.fillRect(0, 0, 10, 10, (1, 2, 3))
        ctx.drawBezier(0, 0, 80, 40, (255, 255, 255), 2)
        self.assertEqual(ctx.cmdCount(), 2)
        ctx.commit()
        self.assertEqual(ctx.cmdCount(), 2)

def main() -> int:
    suite: TestSuite = TestSuite()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
