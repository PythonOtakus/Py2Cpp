"""OpenMP 并行循环（Cython ``prange`` 语义子集；``for i in prange(...)`` 由译器发射 ``#pragma omp``）。

``th``：迭代次数 ``trip`` 低于阈值时降级为串行 ``for``；``th=0``（默认）恒并行。
"""
from ..builtins import *


@overload
def prange(
  stop: int,
  *,
  schedule: str = "static",
  num_threads: int = 0,
  chunksize: int = 0,
  th: int = 0,
):
  ...


@overload
def prange(
  start: int,
  stop: int,
  step: int = 1,
  *,
  schedule: str = "static",
  num_threads: int = 0,
  chunksize: int = 0,
  th: int = 0,
):
  ...
