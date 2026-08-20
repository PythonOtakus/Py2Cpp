"""Scene View：GLFW 无边框窗 + ``GLDevice`` + 平移 gizmo。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.color import Color
from py2cpp.spatial.vector import Vector3

from ..command import CommandBus, ZeusCommandUnion
from ..platform.window import Window
from ..render.mesh import Mesh
from ..render.opengl.gl_device import GLDevice
from ..scene import Component, GameObject
from ..world import WORLD_PLAYING
from .gizmo import TranslateGizmo


@refcount
class SceneViewport:
  """对齐主窗中栏的无边框 GL 视口。"""

  win: Window = new()
  device: GLDevice = new()
  bus: CommandBus = new()
  gizmo: TranslateGizmo = new()
  ready: bool = False

  def __init__(self):
    self.win = new()
    self.device = new()
    self.bus = new()
    self.gizmo = new()
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
    self.gizmo.ensure()
    self.ready = True
    return True

  def set_screen_bounds(self, x: int, y: int, width: int, height: int) -> None:
    if not self.ready:
      return
    self.win.set_bounds_screen(x, y, width, height)

  def _selected_go(self) -> GameObject | None:
    name: str = self.bus.selected
    if not name:
      return None
    if self.bus.world.root.name == name:
      return self.bus.world.root
    return self.bus.world.root.find(name)

  def render(self) -> None:
    if not self.ready:
      return
    self.win.make_current()
    self.win.poll()
    w: int = self.win.width
    h: int = self.win.height
    if self.bus.world.state != WORLD_PLAYING:
      sel: GameObject | None = self._selected_go()
      if sel is not None:
        origin: Vector3 = sel.root.localPosition
        moved, new_pos = self.gizmo.update(self.win, origin, w, h)
        if moved:
          self.bus.dispatch(
            ZeusCommandUnion.ObjectSetPosition(sel.name, new_pos.x, new_pos.y, new_pos.z)
          )
    self.device.begin_frame(w, h)
    self.device.clear()
    self._draw_go(self.bus.world.root)
    if self.bus.world.state != WORLD_PLAYING:
      sel2: GameObject | None = self._selected_go()
      if sel2 is not None:
        self.gizmo.draw(self.device, sel2.root.localPosition)
    self.win.swap()

  def _draw_go(self, go: GameObject) -> None:
    if not go.active or not go.visible:
      return
    pos: Vector3 = go.root.localPosition
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
