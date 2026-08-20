"""Phase 2：GLFW 隐藏窗 + OpenGL 清屏 / cube 烟雾。"""
from py2cpp import *
from py2cpp.spatial.color import Color
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

from .platform.window import Window
from .render.mesh import Mesh
from .render.opengl.gl_device import GLDevice


class GlfwClearCubeTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    win: Window = new()
    ok: bool = win.create(320, 240, "zeus-gl-smoke", True)
    self.assertTrue(ok)
    win.make_current()
    device: GLDevice = new()
    device.set_clear_color(Color(0.2, 0.3, 0.4, 1.0))
    device.begin_frame(320, 240)
    device.clear()
    mesh: Mesh = new.colored_cube(1.0, Color(1.0, 0.4, 0.2, 1.0))
    device.draw_mesh(mesh)
    self.assertEqual(mesh.vertex_count, 36)
    self.assertTrue(device.draw_count >= 1)
    win.swap()
    win.poll()
    win.destroy()


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
