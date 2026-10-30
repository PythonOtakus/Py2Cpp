"""GPU Device 辅助函数元数据（``@annotation``）。"""
from ..builtins import *


@annotation
@dataclass
class GpuDeviceMeta:
  """标记模块级 Device 辅助函数；仅 ``run`` / 其它 ``@GpuDeviceMeta`` 可调用。"""

  _tag: bool = True
