"""组件 Inspector 镜像面板（``UIPanelMixin`` + 字段 ``*Meta`` 静态反射）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.ui.meta import UILabelMeta
from py2cpp.ui.panel import UIPanelMixin

from ..scene import Component


@dataclass(eq=False, repr=False)
class JumpMotorPanel(UIPanelMixin):
  """``JumpMotor`` 可编辑字段镜像（与组件上 ``@UILabelMeta`` 对齐）。"""

  jump_power: float64 @UILabelMeta("Jump Power") = 8.0
  max_charge: float64 @UILabelMeta("Max Charge") = 1.2

  def load_from_component(self, comp: Component) -> None:
    self.jump_power = comp.inspect_float("jump_power")
    self.max_charge = comp.inspect_float("max_charge")

  def apply_to_component(self, comp: Component) -> None:
    comp.set_inspect_float("jump_power", self.jump_power)
    comp.set_inspect_float("max_charge", self.max_charge)
