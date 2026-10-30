"""GPU kernel 混入：标量 ``run`` + Host ``.map``。"""
from ..builtins import *
from .field import Field


@mixin
class GpuKernelMixin:
  """P1 点wise kernel：子类实现 ``def run(...) -> T``；Host 用 ``.map``。"""

  blockSize: int = 256

  def map(self, *fields: Field) -> None:
    """译期专用；末参须为 output ``Field``。"""
    ...
