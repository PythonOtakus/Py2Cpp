"""``PyNone`` 供 ``GeneratorType[..., None, ...]`` 与 ``send(None)`` 等。"""

from ..builtins import *


class PyNone:
  """``GeneratorType[..., None, ...]`` 与 ``send(None)`` 的占位类型（C++ 空结构体）。"""

  pass
