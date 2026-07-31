"""Scene View：GLFW 无边框窗 + ``GLDevice`` 绘制场景 Mesh。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.color import Color
from py2cpp.spatial.vector import Vector3

from ..command import CommandBus
from ..platform.window import Window
from ..render.mesh import Mesh
from ..render.opengl.gl_device import GLDevice
from ..scene import Component, GameObject


@refcount
class SceneViewport:
  """对齐主窗中栏的无边框 GL 视口。"""

  win: Window = new()
  device: GLDevice = new()
  bus: CommandBus = new()
  ready: bool = False

  def __init__(self):
    self.win = new()
    self.device = new()
    self.bus = new()
    self.ready = False

  def bind_bus(self, bus: CommandBus) -> None:
    self.bus = bus

  def open(self, width: int, height: int) -> bool:
    if width < 1:
      width = 1
    if height < 1:
      height = 1
    ok: bool = self.win.create_viewport(width, height, "Zeus Scene")
    if not ok:
      return False
    self.win.make_current()
    self.device.set_clear_color(Color(0.18, 0.19, 0.22, 1.0))
    self.ready = True
    return True

  def set_screen_bounds(self, x: int, y: int, width: int, height: int) -> None:
    if not self.ready:
      return
    self.win.set_bounds_screen(x, y, width, height)

  def render(self) -> None:
    if not self.ready:
      return
    self.win.make_current()
    self.win.poll()
    w: int = self.win.width
    h: int = self.win.height
    self.device.begin_frame(w, h)
    self.device.clear()
    self._draw_go(self.bus.world.root)
    self.win.swap()

  def _draw_go(self, go: GameObject) -> None:
    if not go.active or not go.visible:
      return
    pos: Vector3 = go.root.local_position
    for i in range(go.component_count()):
      c: Component = go.component_at(i)
      m: Mesh | None = c.mesh_for_draw()
      if m is not None:
        self.device.draw_mesh_at(m, pos.x, pos.y, pos.z)
    n_ch: int = go.child_count
    for j in range(n_ch):
      self._draw_go(go.child_at(j))

  def close(self) -> None:
    if self.ready:
      self.win.destroy()
      self.ready = False
