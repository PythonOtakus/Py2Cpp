"""跳一跳：``JumpGame`` 管理分数、平台与落点。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.vector import Vector3

from ..scene import CameraComponent, GameObject, MeshComponent
from ..simple_world import SimpleWorld
from ..world import World
from .motor import JUMP_AIR, JumpMotor
from .platform import PlatformPad


@refcount
class JumpGame:
  """最小跳一跳会话（headless / 有窗共用）。"""

  world: World = new()
  physics: SimpleWorld = new()
  score: int = 0
  player: GameObject = new("Player")
  motor: JumpMotor = new()
  camera: GameObject = new("Camera")
  _plat_index: int = 0

  def __init__(self):
    self.world = new()
    self.physics = new(-18.0, 0.0)
    self.score = 0
    self.player = new("Player")
    self.motor = new()
    self.camera = new("Camera")
    self._plat_index = 0

  def setup_default(self) -> None:
    self.world.clear()
    self.score = 0
    self._plat_index = 1
    root: GameObject = self.world.root
    root.name = "JumpRoot"
    self._make_platform("Platform0", 0.0, 1.2)
    self._make_platform("Platform1", 4.0, 1.2)
    self.player = new("Player")
    self.player.parent = root
    self.player.root.localPosition = Vector3(0.0, 1.0, 0.0)
    self.motor = new()
    # 满蓄力约落在 Platform1（x=4）：dist ≈ power²·2.2/|g|
    self.motor.jump_power = 5.5
    self.player.add_component(self.motor)
    pm: MeshComponent = new()
    pm.color = new(0.9, 0.4, 0.2, 1.0)
    pm.set_cube(0.8)
    self.player.add_component(pm)
    self.camera = new("Camera")
    self.camera.parent = root
    self.camera.root.localPosition = Vector3(0.0, 4.0, 8.0)
    cam: CameraComponent = new()
    cam.look_at_target = Vector3(0.0, 1.0, 0.0)
    self.camera.add_component(cam)

  def _make_platform(self, name: str, x: float64, half: float64) -> None:
    go: GameObject = new(name)
    go.parent = self.world.root
    go.root.localPosition = Vector3(x, 0.0, 0.0)
    pad: PlatformPad = new()
    pad.half_x = half
    pad.half_z = half
    go.add_component(pad)
    mc: MeshComponent = new()
    mc.color = new(0.3, 0.7, 0.3, 1.0)
    mc.set_cube(half * 2.0)
    go.add_component(mc)

  def _spawn_next_platform(self) -> None:
    self._plat_index += 1
    name: str = "Platform" + str(self._plat_index)
    dist: float64 = 3.5 + float(self._plat_index % 3) * 0.5
    pos: Vector3 = self.player.root.localPosition
    px: float64 = pos.x + dist
    self._make_platform(name, px, 1.0)

  def _platform_at(self, index: int) -> GameObject | None:
    return self.world.root.find("Platform" + str(index))

  def _try_land(self) -> bool:
    p: Vector3 = self.player.root.localPosition
    if p.y > 1.2:
      return False
    for i in range(self._plat_index + 1):
      plat: GameObject | None = self._platform_at(i)
      if plat is not None and plat.find_component("PlatformPad") is not None:
        pl: Vector3 = plat.root.localPosition
        cx: float64 = pl.x
        cz: float64 = pl.z
        hx: float64 = 1.2
        hz: float64 = 1.2
        if p.x >= cx - hx and p.x <= cx + hx and p.z >= cz - hz and p.z <= cz + hz:
          p.y = 1.0
          self.player.root.localPosition = p
          self.motor.mark_landed()
          return True
    return False

  def begin_charge(self) -> None:
    self.motor.ready_next()
    self.motor.begin_charge()

  def tick_charge(self, dt: float64) -> None:
    self.motor.tick_charge(dt)

  def release_jump(self) -> None:
    self.motor.release_jump()

  def step(self, dt: float64) -> None:
    self.world.dt = dt
    if self.motor.state == JUMP_AIR:
      xf = self.player.root
      self.physics.ground_y = -50.0
      self.physics.step(self.motor.body, xf, dt)
      lp: Vector3 = xf.localPosition
      if lp.y <= 1.0:
        if self._try_land():
          self.score += 1
          self._spawn_next_platform()
          self.motor.ready_next()
        elif lp.y <= 0.0:
          self.motor.mark_failed()
    target: Vector3 = self.player.root.localPosition
    self.camera.root.localPosition = Vector3(target.x, target.y + 4.0, target.z + 8.0)
    self.world.step()

  def simulate_perfect_jump(self) -> None:
    self.begin_charge()
    self.tick_charge(self.motor.max_charge)
    self.release_jump()
    frames: int = 0
    while self.motor.state == JUMP_AIR and frames < 240:
      self.step(0.016)
      frames += 1
