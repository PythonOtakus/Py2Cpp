"""有窗跳一跳：GLFW + 输入蓄力 + 立即模式渲染。"""
from py2cpp import *
from py2cpp.spatial.color import Color
from py2cpp.spatial.vector import Vector3

from .jump.game import JumpGame
from .jump.motor import JUMP_AIR, JUMP_CHARGING, JUMP_FAILED, JUMP_IDLE, JUMP_LANDED
from .platform.input import jump_charge_held
from .platform.window import Window
from .render.mesh import Mesh
from .render.opengl.gl_device import GLDevice
from .scene import Component, GameObject


def _draw_go(device: GLDevice, go: GameObject) -> None:
  if not go.active or not go.visible:
    return
  pos: Vector3 = go.root.local_position
  for i in range(go.component_count()):
    c: Component = go.component_at(i)
    m: Mesh | None = c.mesh_for_draw()
    if m is not None:
      device.draw_mesh_at(m, pos.x, pos.y, pos.z)
  n: int = go.child_count
  for j in range(n):
    _draw_go(device, go.child_at(j))


def main() -> int:
  game: JumpGame = new()
  game.setup_default()
  win: Window = new()
  if not win.create(960, 540, "Zeus Jump", False):
    print("failed to create window")
    return 1
  device: GLDevice = new()
  device.set_clear_color(Color(0.12, 0.14, 0.18, 1.0))
  held_prev: bool = False
  while not win.should_close:
    win.poll()
    held: bool = jump_charge_held(win)
    if held and not held_prev:
      if game.motor.state in {JUMP_IDLE, JUMP_LANDED}:
        game.begin_charge()
    if held and game.motor.state == JUMP_CHARGING:
      game.tick_charge(0.016)
    if (not held) and held_prev and game.motor.state == JUMP_CHARGING:
      game.release_jump()
    held_prev = held
    if game.motor.state in {JUMP_AIR, JUMP_CHARGING}:
      game.step(0.016)
    elif game.motor.state == JUMP_FAILED:
      game.setup_default()
      held_prev = False
    win.make_current()
    device.begin_frame(win.width, win.height)
    device.clear()
    _draw_go(device, game.world.root)
    win.swap()
  win.destroy()
  print("score=" + str(game.score))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
