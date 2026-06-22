"""``PyNone`` 供 ``Generator[..., None, ...]`` 与 ``send(None)`` 等。"""

from ..builtins import *


@native_name("PyNone")
class PyNone:
  """``Generator[..., None, ...]`` 与 ``send(None)`` 的占位类型（C++ 空结构体）。"""

  pass
