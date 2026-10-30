"""GPU 同步与设备查询（Host）。"""
from ..builtins import *


def deviceSynchronize() -> None:
  """设备同步：``--gpu-backend=cuda`` 时译为 ``cudaDeviceSynchronize()``；omp 为空。"""
  return


@context
def gpuSync():
  """``with gpuSync():`` — enter 无操作；exit 调用 ``deviceSynchronize``（无 ``as``）。"""
  yield
  deviceSynchronize()


def deviceCount() -> int:
  """可见 GPU 数量（P1 omp 桩为 0；CUDA 后续接 ``ffi/cuda``）。"""
  return 0
