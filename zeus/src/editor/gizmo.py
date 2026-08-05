"""Scene View 平移 gizmo：投影命中 + 沿轴拖拽。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.math import safe_sqrt
from py2cpp.spatial.matrix import Matrix4
from py2cpp.spatial.vector import Vector3

from ..platform.input import cursor_pos, mouse_left_down
from ..platform.window import Window
from ..render.opengl.gl_device import GLDevice

AXIS_LEN: float64 = 1.5
HIT_PX: float64 = 14.0
DRAG_SCALE: float64 = 0.02


@refcount
class TranslateGizmo:
  """与 ``GLDevice.begin_frame`` 固定相机一致的平移 gizmo。"""

  axis: int = 0
  dragging: bool = False
  last_mx: float64 = 0.0
  last_my: float64 = 0.0
  _px: Pointer[float64] = None
  _py: Pointer[float64] = None
  ready: bool = False

  def __init__(self):
    self.axis = 0
    self.dragging = False
    self.last_mx = 0.0
    self.last_my = 0.0
    self._px = None
    self._py = None
    self.ready = False

  def ensure(self) -> None:
    if self.ready:
      return
    self._px = alloc[float64]()
    self._py = alloc[float64]()
    self.ready = True

  def _view_matrix(self) -> Matrix4:
    cam_pos: Vector3 = new(0.0, 0.0, -4.0)
    t: Matrix4 = new.from_position(cam_pos)
    rx: Matrix4 = new.from_angle_x(25.0)
    ry: Matrix4 = new.from_angle_y(35.0)
    return t @ rx @ ry

  def project(
    self, world: Vector3, width: int, height: int,
  ) -> (float64, float64):
    eye: Vector3 = self._view_matrix() * world
    aspect: float64 = 1.0
    if height != 0:
      aspect = width / height
    z: float64 = -eye.z
    if z < 0.2:
      z = 0.2
    ndc_x: float64 = eye.x / (aspect * z)
    ndc_y: float64 = eye.y / z
    sx: float64 = (ndc_x + 1.0) * 0.5 * float(width)
    sy: float64 = (1.0 - ndc_y) * 0.5 * float(height)
    return (sx, sy)

  def _dist_point_seg(
    self, px: float64, py: float64, ax: float64, ay: float64, bx: float64, by: float64,
  ) -> float64:
    abx: float64 = bx - ax
    aby: float64 = by - ay
    apx: float64 = px - ax
    apy: float64 = py - ay
    ab2: float64 = abx * abx + aby * aby
    t: float64 = 0.0
    if ab2 > 1e-8:
      t = (apx * abx + apy * aby) / ab2
    if t < 0.0:
      t = 0.0
    if t > 1.0:
      t = 1.0
    cx: float64 = ax + abx * t
    cy: float64 = ay + aby * t
    dx: float64 = px - cx
    dy: float64 = py - cy
    return safe_sqrt(dx * dx + dy * dy)

  def pick_axis(
    self, origin: Vector3, mx: float64, my: float64, width: int, height: int,
  ) -> int:
    ox, oy = self.project(origin, width, height)
    tip_x: Vector3 = new(origin.x + AXIS_LEN, origin.y, origin.z)
    tip_y: Vector3 = new(origin.x, origin.y + AXIS_LEN, origin.z)
    tip_z: Vector3 = new(origin.x, origin.y, origin.z + AXIS_LEN)
    xx, xy = self.project(tip_x, width, height)
    yx, yy = self.project(tip_y, width, height)
    zx, zy = self.project(tip_z, width, height)
    dx: float64 = self._dist_point_seg(mx, my, ox, oy, xx, xy)
    dy: float64 = self._dist_point_seg(mx, my, ox, oy, yx, yy)
    dz: float64 = self._dist_point_seg(mx, my, ox, oy, zx, zy)
    best: float64 = HIT_PX
    axis: int = 0
    if dx < best:
      best = dx
      axis = 1
    if dy < best:
      best = dy
      axis = 2
    if dz < best:
      axis = 3
    return axis

  def draw(self, device: GLDevice, origin: Vector3) -> None:
    device.draw_translate_gizmo(origin.x, origin.y, origin.z, AXIS_LEN)

  def update(
    self,
    window: Window,
    origin: Vector3,
    width: int,
    height: int,
  ) -> (bool, Vector3):
    """处理拖拽；返回 ``(moved, new_pos)``。"""
    self.ensure()
    moved: bool = False
    pos: Vector3 = origin
    if not cursor_pos(window, self._px, self._py):
      return (False, pos)
    mx: float64 = self._px[0]
    my: float64 = self._py[0]
    down: bool = mouse_left_down(window)
    if down and not self.dragging:
      self.axis = self.pick_axis(origin, mx, my, width, height)
      if self.axis != 0:
        self.dragging = True
        self.last_mx = mx
        self.last_my = my
    elif down and self.dragging and self.axis != 0:
      dmx: float64 = mx - self.last_mx
      dmy: float64 = my - self.last_my
      delta: float64 = (dmx - dmy) * DRAG_SCALE
      nx: float64 = pos.x
      ny: float64 = pos.y
      nz: float64 = pos.z
      if self.axis == 1:
        nx += delta
      elif self.axis == 2:
        ny -= delta
      else:
        nz += delta
      pos = new(nx, ny, nz)
      moved = True
      self.last_mx = mx
      self.last_my = my
    elif not down:
      self.dragging = False
      self.axis = 0
    return (moved, pos)
