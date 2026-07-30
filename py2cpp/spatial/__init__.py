"""``py2cpp.spatial``：向量 / 矩阵 / 旋转 / 变换 / 颜色 / 矩形。"""
from ..builtins import *
from .color import Color, ColorMatrix
from .matrix import Matrix3, Matrix4
from .rect import Rect
from .rotator import Quaternion, Rotator
from .transform import Transform2D, Transform3D
from .vector import Vector2, Vector3, Vector4

__all__ = [
  "Color",
  "ColorMatrix",
  "Matrix3",
  "Matrix4",
  "Quaternion",
  "Rect",
  "Rotator",
  "Transform2D",
  "Transform3D",
  "Vector2",
  "Vector3",
  "Vector4",
]
