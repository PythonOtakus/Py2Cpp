"""OpenGL 清屏 / 立即模式：纯 Python 组合 ``ffi.gl.gl``。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.color import Color
from ffi.gl.gl import (
  PyiGlColorBufferBit,
  PyiGlDepthBufferBit,
  PyiGlDepthTest,
  PyiGlLines,
  PyiGlModelview,
  PyiGlProjection,
  PyiGlTriangles,
  pyiGlBegin,
  pyiGlClear,
  pyiGlClearColor,
  pyiGlColor3D,
  pyiGlEnable,
  pyiGlEnd,
  pyiGlFrustum,
  pyiGlLoadIdentity,
  pyiGlMatrixMode,
  pyiGlPopMatrix,
  pyiGlPushMatrix,
  pyiGlRotatef,
  pyiGlTranslatef,
  pyiGlVertex3D,
  pyiGlViewport,
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
    pyiGlClearColor(self.clear_r, self.clear_g, self.clear_b, self.clear_a)
    pyiGlClear(PyiGlColorBufferBit | PyiGlDepthBufferBit)

  def begin_frame(self, width: int, height: int) -> None:
    pyiGlViewport(0, 0, width, height)
    pyiGlEnable(PyiGlDepthTest)
    pyiGlMatrixMode(PyiGlProjection)
    pyiGlLoadIdentity()
    aspect: float64 = 1.0
    if height != 0:
      aspect = width / height
    pyiGlFrustum(-aspect, aspect, -1.0, 1.0, 1.0, 100.0)
    pyiGlMatrixMode(PyiGlModelview)
    pyiGlLoadIdentity()
    pyiGlTranslatef(0.0, 0.0, -4.0)
    pyiGlRotatef(25.0, 1.0, 0.0, 0.0)
    pyiGlRotatef(35.0, 0.0, 1.0, 0.0)

  def draw_mesh(self, mesh: Mesh) -> None:
    n: int = mesh.vertex_count
    if n <= 0:
      return
    pyiGlBegin(PyiGlTriangles)
    for i in range(n):
      base: int = i * 6
      x: float64 = mesh.vertices[base]
      y: float64 = mesh.vertices[base + 1]
      z: float64 = mesh.vertices[base + 2]
      r: float64 = mesh.vertices[base + 3]
      g: float64 = mesh.vertices[base + 4]
      b: float64 = mesh.vertices[base + 5]
      pyiGlColor3D(r, g, b)
      pyiGlVertex3D(x, y, z)
    pyiGlEnd()
    self.draw_count += 1

  def draw_mesh_at(self, mesh: Mesh, x: float64, y: float64, z: float64) -> None:
    pyiGlPushMatrix()
    pyiGlTranslatef(x, y, z)
    self.draw_mesh(mesh)
    pyiGlPopMatrix()

  def draw_translate_gizmo(self, x: float64, y: float64, z: float64, axis_len: float64) -> None:
    """选中物体处的 RGB 平移 gizmo（立即模式线段）。"""
    pyiGlPushMatrix()
    pyiGlTranslatef(x, y, z)
    pyiGlBegin(PyiGlLines)
    pyiGlColor3D(1.0, 0.2, 0.2)
    pyiGlVertex3D(0.0, 0.0, 0.0)
    pyiGlVertex3D(axis_len, 0.0, 0.0)
    pyiGlColor3D(0.2, 1.0, 0.2)
    pyiGlVertex3D(0.0, 0.0, 0.0)
    pyiGlVertex3D(0.0, axis_len, 0.0)
    pyiGlColor3D(0.2, 0.4, 1.0)
    pyiGlVertex3D(0.0, 0.0, 0.0)
    pyiGlVertex3D(0.0, 0.0, axis_len)
    pyiGlEnd()
    pyiGlPopMatrix()
