"""跳一跳平台落点。"""
from __future__ import annotations

from py2cpp import *

from ..scene import Component


@refcount
class PlatformPad(Component):
  """水平平台半宽（XZ）；顶面 y 取宿主 ``root.local_position.y``。"""

  half_x: float64 = 1.0
  half_z: float64 = 1.0

  def __init__(self):
    self.kind = "PlatformPad"
    self.enabled = True
    self.asset_path = ""
    self._owner = None
    self.half_x = 1.0
    self.half_z = 1.0
