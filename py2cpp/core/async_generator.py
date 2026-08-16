"""``PyAsyncGenerator[Y,S]`` 擦除异步生成器句柄（``templates/core/async_generator.h``）。

用户写 ``AsyncGeneratorType[Y,S]``（``protocols.AsyncGeneratorType``）；形参/字段/``@virtual`` 返回映射为本类型。
``async def`` 含 ``yield`` 仍译为具体 ``*_coroutine``。
"""
from ..builtins import *

__all__: list[str] = []


@native
@native_name("PyAsyncGenerator")
class _PyAsyncGeneratorStub:
  """占位；实现见 ``templates/core/async_generator.h``。"""

  pass
