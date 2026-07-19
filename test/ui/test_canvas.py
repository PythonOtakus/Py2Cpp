"""``py2cpp.ui.canvas``：绘制命令与视口变换。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.canvas import (
  DrawCmd,
  DrawCmdKind,
  UICanvas,
  UICanvasFont,
  UIPaintContext,
  _bezier_controls,
)


class DrawCmdTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.FillRect
    cmd.x = 1
    cmd.y = 2
    cmd.w = 10
    cmd.h = 20
    cmd.r = 30
    self.assertEqual(cmd.kind, DrawCmdKind.FillRect)
    self.assertEqual(cmd.w, 10)


class CanvasViewportTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    c: UICanvas = new()
    c.pan_x = 10.0
    c.pan_y = 20.0
    c.zoom = 2.0
    sx, sy = c.world_to_screen(5.0, 5.0)
    self.assertEqual(sx, 30.0)
    self.assertEqual(sy, 50.0)
    wx, wy = c.screen_to_world(sx, sy)
    self.assertEqual(wx, 5.0)
    self.assertEqual(wy, 5.0)


class CanvasWheelZoomTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    c: UICanvas = new()
    c.zoom = 1.0
    c.pan_x = 0.0
    c.pan_y = 0.0
    want_in: float64 = 1.1
    c.on_wheel(120, 100, 100)
    self.assertEqual(c.zoom, want_in)
    wx, wy = c.screen_to_world(100.0, 100.0)
    self.assertEqual(wx, 100.0)
    self.assertEqual(wy, 100.0)
    want_out: float64 = 1.0
    c.on_wheel(-120, 100, 100)
    self.assertEqual(c.zoom, want_out)


class CanvasFontScaleTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    ctx: UIPaintContext = new()
    font: UICanvasFont = new()
    font.size = 11
    ctx.begin_frame(0, 640, 480, font, 2.0)
    self.assertEqual(ctx.scaled_font_size(), 22)
    ctx.begin_frame(0, 640, 480, font, 0.5)
    self.assertEqual(ctx.scaled_font_size(), 5)


class PaintContextTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    ctx: UIPaintContext = new()
    font: UICanvasFont = new()
    font.name = "Arial"
    font.size = 12
    ctx.begin_frame(0, 640, 480, font)
    ctx.fill_rect(0, 0, 100, 50, (255, 0, 0))
    ctx.draw_line(0, 0, 10, 10, (0, 255, 0), 2)
    self.assertEqual(ctx.cmd_count(), 2)


class RoundRectCmdTests(TestCaseMixin):
  _test_tag = 6

  @override
  def test(self):
    ctx: UIPaintContext = new()
    font: UICanvasFont = new()
    ctx.begin_frame(0, 640, 480, font)
    ctx.fill_round_rect(10, 20, 100, 80, 8, (0, 122, 204))
    ctx.stroke_round_rect(10, 20, 100, 80, 8, (255, 198, 0), 2)
    ctx.fill_rect_in_round_clip(10, 20, 100, 28, 100, 80, 8, (0, 122, 204))
    ctx.draw_text(14, 20, 90, 28, "Title", (240, 240, 240), 1)
    self.assertEqual(ctx.cmd_count(), 4)


class BezierControlsTests(TestCaseMixin):
  _test_tag = 7

  @override
  def test(self):
    cx1, cy1, cx2, cy2 = _bezier_controls(0, 10, 100, 50)
    self.assertEqual(cx1, 50)
    self.assertEqual(cy1, 10)
    self.assertEqual(cx2, 50)
    self.assertEqual(cy2, 50)
    sx1, _, sx2, _ = _bezier_controls(0, 0, 20, 0)
    self.assertEqual(sx1, 20)
    self.assertEqual(sx2, 0)


class CommitDispatchTests(TestCaseMixin):
  _test_tag = 8

  @override
  def test(self):
    ctx: UIPaintContext = new()
    font: UICanvasFont = new()
    ctx.begin_frame(0, 640, 480, font)
    ctx.fill_rect(0, 0, 10, 10, (1, 2, 3))
    ctx.draw_bezier(0, 0, 80, 40, (255, 255, 255), 2)
    self.assertEqual(ctx.cmd_count(), 2)
    ctx.commit()
    self.assertEqual(ctx.cmd_count(), 2)


def main() -> int:
  suite: TestSuite = TestSuite()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
