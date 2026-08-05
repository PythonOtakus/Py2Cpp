"""OpenGL 清屏 / 立即模式：纯 Python 组合 ``ffi.gl.gl``。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.color import Color
from ffi.gl.gl import (
  Pyi_GL_COLOR_BUFFER_BIT,
  Pyi_GL_DEPTH_BUFFER_BIT,
  Pyi_GL_DEPTH_TEST,
  Pyi_GL_LINES,
  Pyi_GL_MODELVIEW,
  Pyi_GL_PROJECTION,
  Pyi_GL_TRIANGLES,
  Pyi_glBegin,
  Pyi_glClear,
  Pyi_glClearColor,
  Pyi_glColor3d,
  Pyi_glEnable,
  Pyi_glEnd,
  Pyi_glFrustum,
  Pyi_glLoadIdentity,
  Pyi_glMatrixMode,
  Pyi_glPopMatrix,
  Pyi_glPushMatrix,
  Pyi_glRotatef,
  Pyi_glTranslatef,
  Pyi_glVertex3d,
  Pyi_glViewport,
)

from ..mesh import Mesh


@refcount
class GLDevice:
  """兼容配置下的清屏 + 彩色三角网格绘制。"""

  clear_r: float64 = 0.0
  clear_g: float64 = 0.0
  clear_b: float64 = 0.0
  clear_a: float64 = 1.0
  draw_count: int = 0

  def set_clear_color(self, color: Color) -> None:
    self.clear_r = color.r
    self.clear_g = color.g
    self.clear_b = color.b
    self.clear_a = color.a

  def clear(self) -> None:
    Pyi_glClearColor(self.clear_r, self.clear_g, self.clear_b, self.clear_a)
    Pyi_glClear(Pyi_GL_COLOR_BUFFER_BIT | Pyi_GL_DEPTH_BUFFER_BIT)

  def begin_frame(self, width: int, height: int) -> None:
    Pyi_glViewport(0, 0, width, height)
    Pyi_glEnable(Pyi_GL_DEPTH_TEST)
    Pyi_glMatrixMode(Pyi_GL_PROJECTION)
    Pyi_glLoadIdentity()
    aspect: float64 = 1.0
    if height != 0:
      aspect = width / height
    Pyi_glFrustum(-aspect, aspect, -1.0, 1.0, 1.0, 100.0)
    Pyi_glMatrixMode(Pyi_GL_MODELVIEW)
    Pyi_glLoadIdentity()
    Pyi_glTranslatef(0.0, 0.0, -4.0)
    Pyi_glRotatef(25.0, 1.0, 0.0, 0.0)
    Pyi_glRotatef(35.0, 0.0, 1.0, 0.0)

  def draw_mesh(self, mesh: Mesh) -> None:
    n: int = mesh.vertex_count
    if n <= 0:
      return
    Pyi_glBegin(Pyi_GL_TRIANGLES)
    for i in range(n):
      base: int = i * 6
      x: float64 = mesh.vertices[base]
      y: float64 = mesh.vertices[base + 1]
      z: float64 = mesh.vertices[base + 2]
      r: float64 = mesh.vertices[base + 3]
      g: float64 = mesh.vertices[base + 4]
      b: float64 = mesh.vertices[base + 5]
      Pyi_glColor3d(r, g, b)
      Pyi_glVertex3d(x, y, z)
    Pyi_glEnd()
    self.draw_count += 1

  def draw_mesh_at(self, mesh: Mesh, x: float64, y: float64, z: float64) -> None:
    Pyi_glPushMatrix()
    Pyi_glTranslatef(x, y, z)
    self.draw_mesh(mesh)
    Pyi_glPopMatrix()

  def draw_translate_gizmo(self, x: float64, y: float64, z: float64, axis_len: float64) -> None:
    """选中物体处的 RGB 平移 gizmo（立即模式线段）。"""
    Pyi_glPushMatrix()
    Pyi_glTranslatef(x, y, z)
    Pyi_glBegin(Pyi_GL_LINES)
    Pyi_glColor3d(1.0, 0.2, 0.2)
    Pyi_glVertex3d(0.0, 0.0, 0.0)
    Pyi_glVertex3d(axis_len, 0.0, 0.0)
    Pyi_glColor3d(0.2, 1.0, 0.2)
    Pyi_glVertex3d(0.0, 0.0, 0.0)
    Pyi_glVertex3d(0.0, axis_len, 0.0)
    Pyi_glColor3d(0.2, 0.4, 1.0)
    Pyi_glVertex3d(0.0, 0.0, 0.0)
    Pyi_glVertex3d(0.0, 0.0, axis_len)
    Pyi_glEnd()
    Pyi_glPopMatrix()
