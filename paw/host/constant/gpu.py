"""GPU 计算（``paw/gpu``）译器约定。"""

GPU_KERNEL_MIXIN = "GpuKernelMixin"
GPU_MAP_METHOD = "map"
GPU_DEVICE_META = "GpuDeviceMeta"
GPU_FIELD_CLASS = "Field"
GPU_RUNTIME_PKG_PREFIX = "paw/gpu"
GPU_BACKEND_OMP = "omp"
GPU_BACKEND_CUDA = "cuda"
GPU_BACKENDS = frozenset({GPU_BACKEND_OMP, GPU_BACKEND_CUDA})
GPU_DEVICE_SYNC = "deviceSynchronize"
GPU_LAUNCH_BLOCK_SIZE_FIELD = "blockSize"
