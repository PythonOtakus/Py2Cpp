"""Inspector：对象属性 + ``JumpMotorPanel`` 镜像字段（``float64`` / ``UIFloatEdit``）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.vector import Vector3
from py2cpp.ui.meta import UIButtonMeta, UIInvisibleMeta, UILabelMeta
from py2cpp.ui.panel import UIPanelMixin

from ..command import CommandBus, ZeusCommandUnion
from ..scene import Component, GameObject
from .inspect_panels import JumpMotorPanel


@dataclass(eq=False, repr=False)
class InspectorPanel(UIPanelMixin):
  object_name: str @UILabelMeta("Name") = ""
  active: bool @UILabelMeta("Active") = True
  visible: bool @UILabelMeta("Visible") = True
  pos_x: float64 @UILabelMeta("Pos X") = 0.0
  pos_y: float64 @UILabelMeta("Pos Y") = 0.0
  pos_z: float64 @UILabelMeta("Pos Z") = 0.0
  jump_power: float64 @UILabelMeta("Jump Power") = 8.0
  max_charge: float64 @UILabelMeta("Max Charge") = 1.2
  components: str @UILabelMeta("Components") = ""
  _bus: CommandBus @UIInvisibleMeta = new()
  _bound_name: str @UIInvisibleMeta = ""
  _has_jump: bool @UIInvisibleMeta = False
  _motor_panel: JumpMotorPanel @UIInvisibleMeta = new()

  def bind_bus(self, bus: CommandBus) -> None:
    self._bus = bus

  def load_from_selection(self) -> None:
    name: str = self._bus.selected
    self._bound_name = name
    self._has_jump = False
    if not name:
      self.object_name = ""
      self.active = True
      self.visible = True
      self.pos_x = 0.0
      self.pos_y = 0.0
      self.pos_z = 0.0
      self.jump_power = 8.0
      self.max_charge = 1.2
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
    lp: Vector3 = go.root.localPosition
    self.pos_x = lp.x
    self.pos_y = lp.y
    self.pos_z = lp.z
    parts: list[str] = []
    for i in range(go.component_count()):
      c: Component = go.component_at(i)
      parts.append(c.kind)
      if c.kind == "JumpMotor":
        self._has_jump = True
        self._motor_panel.load_from_component(c)
        self.jump_power = self._motor_panel.jump_power
        self.max_charge = self._motor_panel.max_charge
    self.components = ",".join(parts)

  @UIButtonMeta("Apply")
  def apply(self) -> None:
    if not self._bound_name:
      return
    if self.object_name and self.object_name != self._bound_name:
      self._bus.dispatch(ZeusCommandUnion.ObjectRename(self._bound_name, self.object_name))
      self._bound_name = self.object_name
    self._bus.dispatch(ZeusCommandUnion.ObjectSetActive(self._bound_name, self.active))
    self._bus.dispatch(ZeusCommandUnion.ObjectSetVisible(self._bound_name, self.visible))
    self._bus.dispatch(
      ZeusCommandUnion.ObjectSetPosition(self._bound_name, self.pos_x, self.pos_y, self.pos_z)
    )
    if self._has_jump:
      self._motor_panel.jump_power = self.jump_power
      self._motor_panel.max_charge = self.max_charge
      self._bus.dispatch(
        ZeusCommandUnion.ComponentSetFloat(
          self._bound_name, "JumpMotor", "jump_power", self.jump_power,
        )
      )
      self._bus.dispatch(
        ZeusCommandUnion.ComponentSetFloat(
          self._bound_name, "JumpMotor", "max_charge", self.max_charge,
        )
      )

  @UIButtonMeta("Create")
  def create_empty(self) -> None:
    n: int = self._bus.world.root.child_count
    name: str = "GameObject" + str(n + 1)
    parent: str = self._bound_name
    if not parent:
      parent = ""
    self._bus.dispatch(ZeusCommandUnion.ObjectCreate(name, parent))
    self._bus.dispatch(ZeusCommandUnion.EditorSelect(name))
    self.load_from_selection()

  @UIButtonMeta("Add Mesh")
  def add_mesh(self) -> None:
    if not self._bound_name:
      return
    self._bus.dispatch(ZeusCommandUnion.ObjectAddMesh(self._bound_name, 1.0))
    self.load_from_selection()

  @UIButtonMeta("Add Camera")
  def add_camera(self) -> None:
    if not self._bound_name:
      return
    self._bus.dispatch(ZeusCommandUnion.ObjectAddCamera(self._bound_name))
    self.load_from_selection()

  @UIButtonMeta("Save")
  def save_scene(self) -> None:
    path: str = "zeus/examples/jump_demo/scenes/main.zas"
    self._bus.dispatch(ZeusCommandUnion.SceneSave(path, self._bus.scene_name))

  @UIButtonMeta("Play")
  def play(self) -> None:
    self._bus.dispatch(ZeusCommandUnion.PlayStart())

  @UIButtonMeta("Pause")
  def pause(self) -> None:
    self._bus.dispatch(ZeusCommandUnion.PlayPause())

  @UIButtonMeta("Stop")
  def stop(self) -> None:
    self._bus.dispatch(ZeusCommandUnion.PlayStop())

  @UIButtonMeta("Step")
  def step_one(self) -> None:
    self._bus.dispatch(ZeusCommandUnion.PlayStep(1))
