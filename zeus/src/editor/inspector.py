"""Inspector：``UIPanelMixin`` 编辑选中对象的 name / active / visible / 局部位移。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.ui.meta import UIButtonMeta, UIInvisibleMeta, UILabelMeta
from py2cpp.ui.panel import UIPanelMixin

from ..command import CommandBus, ZeusCommand
from ..scene import Component, GameObject
from py2cpp.spatial.vector import Vector3


@dataclass(eq=False, repr=False)
class InspectorPanel(UIPanelMixin):
  object_name: str @UILabelMeta("Name") = ""
  active: bool @UILabelMeta("Active") = True
  visible: bool @UILabelMeta("Visible") = True
  pos_x: str @UILabelMeta("Pos X") = "0"
  pos_y: str @UILabelMeta("Pos Y") = "0"
  pos_z: str @UILabelMeta("Pos Z") = "0"
  components: str @UILabelMeta("Components") = ""
  _bus: CommandBus @UIInvisibleMeta = new()
  _bound_name: str @UIInvisibleMeta = ""

  def bind_bus(self, bus: CommandBus) -> None:
    self._bus = bus

  def load_from_selection(self) -> None:
    name: str = self._bus.selected
    self._bound_name = name
    if not name:
      self.object_name = ""
      self.active = True
      self.visible = True
      self.pos_x = "0"
      self.pos_y = "0"
      self.pos_z = "0"
      self.components = ""
      return
    go: GameObject | None = None
    if self._bus.world.root.name == name:
      go = self._bus.world.root
    else:
      go = self._bus.world.root.find(name)
    if go is None:
      self.object_name = ""
      self.components = ""
      return
    self.object_name = go.name
    self.active = go.active
    self.visible = go.visible
    lp: Vector3 = go.root.local_position
    self.pos_x = str(lp.x)
    self.pos_y = str(lp.y)
    self.pos_z = str(lp.z)
    parts: list[str] = []
    for i in range(go.component_count()):
      c: Component = go.component_at(i)
      parts.append(c.kind)
    self.components = ",".join(parts)

  @UIButtonMeta("Apply")
  def apply(self) -> None:
    if not self._bound_name:
      return
    if self.object_name and self.object_name != self._bound_name:
      self._bus.dispatch(ZeusCommand.ObjectRename(self._bound_name, self.object_name))
      self._bound_name = self.object_name
    self._bus.dispatch(ZeusCommand.ObjectSetActive(self._bound_name, self.active))
    self._bus.dispatch(ZeusCommand.ObjectSetVisible(self._bound_name, self.visible))
    x: float64 = float(self.pos_x)
    y: float64 = float(self.pos_y)
    z: float64 = float(self.pos_z)
    self._bus.dispatch(ZeusCommand.ObjectSetPosition(self._bound_name, x, y, z))

  @UIButtonMeta("Play")
  def play(self) -> None:
    self._bus.dispatch(ZeusCommand.PlayStart())

  @UIButtonMeta("Pause")
  def pause(self) -> None:
    self._bus.dispatch(ZeusCommand.PlayPause())

  @UIButtonMeta("Stop")
  def stop(self) -> None:
    self._bus.dispatch(ZeusCommand.PlayStop())

  @UIButtonMeta("Step")
  def step_one(self) -> None:
    self._bus.dispatch(ZeusCommand.PlayStep(1))
