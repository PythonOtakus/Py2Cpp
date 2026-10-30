"""负向：Host 调用 ``@GpuDeviceMeta`` 须译期失败。"""
from py2cpp import *
from py2cpp.gpu import GpuDeviceMeta


@GpuDeviceMeta
def clamp01(x: float) -> float:
  if x < 0.0:
    return 0.0
  if x > 1.0:
    return 1.0
  return x


def main() -> None:
  y: float = clamp01(0.5)
  return
