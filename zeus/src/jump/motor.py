"""跳一跳：蓄力跳跃电机（``Component``）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.vector import Vector3

from ..scene import Component
from ..simple_world import SimpleBody


JUMP_IDLE: int = 0
JUMP_CHARGING: int = 1
JUMP_AIR: int = 2
JUMP_LANDED: int = 3
JUMP_FAILED: int = 4


@refcount
class JumpMotor(Component):
  """按住蓄力、松开起跳；落地由 ``JumpGame`` 判定。"""

  jump_power: float64 = 8.0
  max_charge: float64 = 1.2
  charge: float64 = 0.0
  state: int = 0
  body: SimpleBody = new()
  forward_x: float64 = 1.0
  forward_z: float64 = 0.0

  def __init__(self):
    self.kind = "JumpMotor"
    self.enabled = True
    self.asset_path = ""
    self._owner = None
    self.jump_power = 8.0
    self.max_charge = 1.2
    self.charge = 0.0
    self.state = JUMP_IDLE
    self.body = new()
    self.body.grounded = True
    self.forward_x = 1.0
    self.forward_z = 0.0

  def begin_charge(self) -> None:
    if self.state not in {JUMP_IDLE, JUMP_LANDED}:
      return
    self.state = JUMP_CHARGING
    self.charge = 0.0

  def tick_charge(self, dt: float64) -> None:
    if self.state != JUMP_CHARGING:
      return
    self.charge += dt
    if self.charge > self.max_charge:
      self.charge = self.max_charge

  def release_jump(self) -> None:
    if self.state != JUMP_CHARGING:
      return
    t: float64 = self.charge / self.max_charge
    if t < 0.05:
      t = 0.05
    speed: float64 = self.jump_power * t
    self.body.velocity = Vector3(self.forward_x * speed, speed * 1.1, self.forward_z * speed)
    self.body.grounded = False
    self.state = JUMP_AIR
    self.charge = 0.0

  def mark_landed(self) -> None:
    self.state = JUMP_LANDED
    self.body.grounded = True
    self.body.velocity = new(0.0, 0.0, 0.0)

  def mark_failed(self) -> None:
    self.state = JUMP_FAILED
    self.body.grounded = True
    self.body.velocity = new(0.0, 0.0, 0.0)

  def ready_next(self) -> None:
    if self.state == JUMP_LANDED:
      self.state = JUMP_IDLE
