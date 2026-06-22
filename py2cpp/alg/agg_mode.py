"""区间聚合模式（``SegTree`` / ``SparseTable`` 共用）。"""
from ..builtins import *


@enum
class AggMode:
  Min = 0
  Max = ...
  Sum = ...
