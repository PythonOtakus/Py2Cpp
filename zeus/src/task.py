"""``Task``：World 主循环阶段槽。"""
from __future__ import annotations

from py2cpp import *


@copyable
class Task:
  """具名阶段（detect / update / draw / refresh）。"""

  name: str
  enabled: bool

  def __init__(self, name: str = ""):
    self.name = name
    self.enabled = True
