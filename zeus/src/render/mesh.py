"""渲染网格数据。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.color import Color


@copyable
class Mesh:
  """交错顶点：x,y,z,r,g,b（每顶点 6 float）。"""

  vertices: list[float64] = []
  vertex_count: int = 0

  def __init__(self):
    self.vertices = []
    self.vertex_count = 0

  @staticmethod
  def colored_cube(size: float64, color: Color) -> Self:
    """轴对齐彩色立方体（12 三角 / 36 顶点）。"""
    m: Self = new()
    h: float64 = size * 0.5
    r: float64 = color.r
    g: float64 = color.g
    b: float64 = color.b
    verts: list[float64] = [
      -h, -h, h, r, g, b, h, -h, h, r, g, b, h, h, h, r, g, b,
      -h, -h, h, r, g, b, h, h, h, r, g, b, -h, h, h, r, g, b,
      -h, -h, -h, r, g, b, -h, h, -h, r, g, b, h, h, -h, r, g, b,
      -h, -h, -h, r, g, b, h, h, -h, r, g, b, h, -h, -h, r, g, b,
      -h, h, -h, r, g, b, -h, h, h, r, g, b, h, h, h, r, g, b,
      -h, h, -h, r, g, b, h, h, h, r, g, b, h, h, -h, r, g, b,
      -h, -h, -h, r, g, b, h, -h, -h, r, g, b, h, -h, h, r, g, b,
      -h, -h, -h, r, g, b, h, -h, h, r, g, b, -h, -h, h, r, g, b,
      h, -h, -h, r, g, b, h, h, -h, r, g, b, h, h, h, r, g, b,
      h, -h, -h, r, g, b, h, h, h, r, g, b, h, -h, h, r, g, b,
      -h, -h, -h, r, g, b, -h, -h, h, r, g, b, -h, h, h, r, g, b,
      -h, -h, -h, r, g, b, -h, h, h, r, g, b, -h, h, -h, r, g, b,
    ]
    m.vertices = verts
    m.vertex_count = len(m.vertices) // 6
    return m
