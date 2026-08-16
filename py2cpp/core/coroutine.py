"""``PyCoroutine[Y,S,R]`` 擦除协程句柄（``templates/core/coroutine.h``）。

用户仍写 ``CoroutineType[Y,S,R]``（``protocols.CoroutineType``）；仅形参/字段/``@virtual`` 返回映射为本类型。
"""
from ..builtins import *

__all__: list[str] = []


@native
@native_name("PyCoroutine")
class _PyCoroutineStub:
  """占位；实现见 ``templates/core/coroutine.h``。"""

  pass
