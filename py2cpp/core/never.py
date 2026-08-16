"""``Never``：条件类型失败时的编译期底类型（无有效存储）。"""
from ..builtins import *


class Never:
  """落到字段/形参/返回等存储位置时译器或 C++ ``static_assert`` 拒绝。"""

  pass
