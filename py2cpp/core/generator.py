"""``PyGenerator[Y,S,R]`` 擦除生成器句柄（``templates/core/generator.h``）。

用户仍写 ``Generator[Y,S,R]``（``protocols.Generator``）；仅形参/字段/``@virtual`` 返回映射为本类型。
"""
from ..builtins import *

__all__: list[str] = []


@native
@native_name("PyGenerator")
class _PyGeneratorStub:
  """占位；实现见 ``templates/core/generator.h``。"""

  pass
