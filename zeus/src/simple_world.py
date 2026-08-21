"""简易重力 / 落点（不装 PhysX）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.vector import Vector3

from .scene import Transform


@copyable
class SimpleBody:
  """质点速度。"""

  velocity: Vector3
  grounded: bool

  def __init__(self):
    self.velocity = new(0.0, 0.0, 0.0)
    self.grounded = False


@refcount
class SimpleWorld:
  """匀加速重力 + y=ground 落点。"""

  gravity: float64
  ground_y: float64

  def __init__(self, gravity: float64 = -9.8, ground_y: float64 = 0.0):
    self.gravity = gravity
    self.ground_y = ground_y

  def step(self, body: SimpleBody, xf: Transform, dt: float64) -> None:
    if body.grounded:
      return
    v: Vector3 = body.velocity
    v.y += self.gravity * dt
    body.velocity = v
    p: Vector3 = xf.position
    p += Vector3(v.x * dt, v.y * dt, v.z * dt)
    if p.y <= self.ground_y:
      p.y = self.ground_y
      body.velocity = new(v.x, 0.0, v.z)
      body.grounded = True
    xf.position = p
