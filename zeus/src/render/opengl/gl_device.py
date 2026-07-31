"""OpenGL 清屏 / 立即模式：纯 Python 组合 ``ffi.gl.gl``。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.color import Color
from ffi.gl.gl import (
  GL_COLOR_BUFFER_BIT,
  GL_DEPTH_BUFFER_BIT,
  GL_DEPTH_TEST,
  GL_MODELVIEW,
  GL_PROJECTION,
  GL_TRIANGLES,
  glBegin,
  glClear,
  glClearColor,
  glColor3d,
  glEnable,
  glEnd,
  glFrustum,
  glLoadIdentity,
  glMatrixMode,
  glPopMatrix,
  glPushMatrix,
  glRotatef,
  glTranslatef,
  glVertex3d,
  glViewport,
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
    glClearColor(self.clear_r, self.clear_g, self.clear_b, self.clear_a)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

  def begin_frame(self, width: int, height: int) -> None:
    glViewport(0, 0, width, height)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    aspect: float64 = 1.0
    if height != 0:
      aspect = width / height
    glFrustum(-aspect, aspect, -1.0, 1.0, 1.0, 100.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glTranslatef(0.0, 0.0, -4.0)
    glRotatef(25.0, 1.0, 0.0, 0.0)
    glRotatef(35.0, 0.0, 1.0, 0.0)

  def draw_mesh(self, mesh: Mesh) -> None:
    n: int = mesh.vertex_count
    if n <= 0:
      return
    glBegin(GL_TRIANGLES)
    for i in range(n):
      base: int = i * 6
      x: float64 = mesh.vertices[base]
      y: float64 = mesh.vertices[base + 1]
      z: float64 = mesh.vertices[base + 2]
      r: float64 = mesh.vertices[base + 3]
      g: float64 = mesh.vertices[base + 4]
      b: float64 = mesh.vertices[base + 5]
      glColor3d(r, g, b)
      glVertex3d(x, y, z)
    glEnd()
    self.draw_count += 1

  def draw_mesh_at(self, mesh: Mesh, x: float64, y: float64, z: float64) -> None:
    glPushMatrix()
    glTranslatef(x, y, z)
    self.draw_mesh(mesh)
    glPopMatrix()
