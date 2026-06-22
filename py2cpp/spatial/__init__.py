"""空间几何：``Vector`` / ``Rotator`` / ``Matrix`` / ``Transform``（游戏向 tggame 语义）。"""
from ..builtins import *
from .matrix import Matrix3, Matrix4
from .rotator import Quaternion, Rotator
from .transform import Transform2D, Transform3D
from .vector import Vector2, Vector3, Vector4

__all__ = [
  "Matrix3",
  "Matrix4",
  "Quaternion",
  "Rotator",
  "Transform2D",
  "Transform3D",
  "Vector2",
  "Vector3",
  "Vector4",
]
