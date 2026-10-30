# Py2Cpp GPU 计算 — 设计方案（现有写法优先）

> **状态**：P1 Host OpenMP sim 验收通过；**CUDA AOT 骨架**（`--gpu-backend=cuda` → `.cu` + Host `cudaMalloc` launch）已落地；`ffi/cuda` 待 Toolkit 安装后用 `ffi.bat` 生成  
> **单一真相源**：`py2cpp/gpu/*.py`、`src/passes/*gpu*`、`src/emit/*gpu*`、`src/codegen/gpu_backend_cuda.py`  
> **关联**：[编码规范](./编码规范.md)、[参考手册](./参考手册.md)、[concur-thread.md](./concur-thread.md)、[c-ffi-pyi.md](./c-ffi-pyi.md)、[py2cpp-design](../.cursor/skills/py2cpp-design/SKILL.md)

---

## 0. 设计约束：非必要不引入新语法

本方案在 **Host/Device 分层** 的前提下，**优先复用 Py2Cpp 已有机制**：

| 原则 | 做法 |
|------|------|
| **Kernel 形态（P1）** | **`@dataclass` + `@mixin GpuKernelMixin`** + 标量 **`run` → T** + **`.map(...)`** |
| **Device 辅助（P1）** | 模块级 **`@GpuDeviceMeta`** 函数，供 `run` 内调用（`@annotation` Meta，同 `FlowNodeMeta` 模式） |
| **点wise 不写循环** | P1：`.map` 外包 grid/`prange`；用户 `run` 只写**标量**表达式并 **`return`** |
| **调度 API** | **`.map`** → **`TRANSLATOR_ONLY_METHODS`**（同 `assign` / `select` / `build`） |
| **Host 同步** | **`@context def gpuSync()`**（同 `stopwatch`）；**`with gpuSync():`**，无 `as`；exit 设备同步（P1 Host sim 为空） |
| **构造写法** | **`op: Add = new(c=1.0)`** 或 **`Add(c=1.0).map(...)`**；**禁止 `new(Add(...))` / `new(Cls)`**（S0304） |
| **Host 边界** | **`list[T]`** / **`array[T,:]`** + **`copyFromHost`** / **`toHost`** |

**P1 范围（仅此）**：**`.map` + 标量 `run` + 模块级 `@GpuDeviceMeta`**。不做 stencil、规约、显式 `prange`、`launch(fn,…)`、模块级 `@GpuKernelMeta`。

**仍需的新增面**：

- **`Field[T]`**、**`GpuKernelMixin`**、**`@GpuDeviceMeta`**；
- GPU **`@native` 叶子** + **`ffi/cuda`**；
- Device **第二条 codegen 管线**（CUDA AOT）。

### 0.1 复用对照表

| 能力 | 既有范本 | GPU 方案 |
|------|----------|----------|
| 类 + 混入 | `TestCaseMixin`、`ArgumentParserMixin` | **`GpuKernelMixin`** |
| 译期专用成员 | `assign` / `select` / `build` | **`.map`** |
| Host 同步上下文 | `@context stopwatch` | **`@context gpuSync`**（`with gpuSync():`，无 `as`） |
| Device 辅助标记 | `@FlowNodeMeta`（`@annotation` + `@dataclass` Meta） | **`@GpuDeviceMeta`**（模块级函数） |
| 用户类构造 | `b: Box = new(w=10, h=20)` | **`op: Add = new(c=1.0)`**；**`Add(c=1.0).map(...)`** |
| 拷贝命名 | `copyFromSpan`、`copyFromPtr` | **`Field.copyFromHost`** / **`toHost`** |
| Native / FFI | `util/memory`、`ffi/sqlite` | `templates/gpu/+runtime.inl`、`ffi/cuda` |

---

## 1. 背景与定位

- **Host**：`Field` 准备数据、**`.map`** 调度、**`with gpuSync():`**（exit 设备同步）；
- **Device**：标量 **`run` → float/int/…**；必要时调 **`@GpuDeviceMeta`** 模块函数；
- **显式 H↔D 拷贝**，无 hidden sync。

---

## 2. 用户 API（P1 定案）

### 2.1 模块布局

```text
py2cpp/gpu/
  mixin.py      # @mixin class GpuKernelMixin
  meta.py       # @annotation class GpuDeviceMeta
  field.py      # Field[T]
  sync.py       # @context gpuSync(), deviceCount()
  __init__.py
```

### 2.2 典型用法

```python
from py2cpp import dataclass
from py2cpp.gpu import Field, GpuDeviceMeta, GpuKernelMixin, gpuSync

@GpuDeviceMeta
def clamp01(x: float) -> float:
  if x < 0.0:
    return 0.0
  if x > 1.0:
    return 1.0
  return x

@dataclass
class Add(GpuKernelMixin):
  c: float

  def run(self, a: float, b: float) -> float:
    return a + b + self.c

@dataclass
class Normalize(GpuKernelMixin):
  offset: float = 0.0

  def run(self, x: float) -> float:
    return clamp01(x + self.offset)

def main() -> None:
  n: int = 1024 * 1024
  a: Field[float] = new.zeros(n)
  b: Field[float] = new.ones(n)
  out: Field[float] = new.zeros(n)
  hostA: list[float] = []
  for i in range(n):
    hostA.append(1.0)
  a.copyFromHost(hostA)

  with gpuSync():
    op: Add = new(c=1.0)
    op.map(a, b, out)   # 末参 out 为 output Field

  host: list[float] = out.toHost()
  assert host[0] == 2.0
```

### 2.3 语义约定（P1）

| 元素 | 语义 |
|------|------|
| **`@dataclass` 字段** | kernel **uniform**（如 `self.c`） |
| **`run` 形参** | **标量**；个数 = `.map` 的 **input `Field` 个数**（不含末参 output） |
| **`run` 返回值** | **标量**（P1 默认 `float`）；译器写回 **末参 output `Field[i]`** |
| **`.map(f0, f1, …, out)`** | **最后一个参数必须是 output `Field[T]`**；其余为 input **`Field`**（同元素类型 `T`，与 `run` 返回类型一致）；**`len` 须一致**（译期检查） |
| **`@GpuDeviceMeta`** | 模块级函数；仅 **Device** 编译；**可被 `run` 调用**；**不可从 Host 调用** |
| **`.map` Host 侧** | 译期脱糖；**不**生成 C++ 方法体 |
| **禁止** | Host 调用 `run` / `@GpuDeviceMeta` 函数；`run` 内 `list`/`dict`/`str`/异常；P1 手写 `prange` |

**形参与 `.map` 对齐示例**：

| `run` 签名 | `.map` 调用 |
|------------|-------------|
| `run(self, x: float) -> float` | `op.map(xField, outField)` |
| `run(self, a: float, b: float) -> float` | `op.map(a, b, out)` |
| `run(self) -> float`（仅 uniform） | `op.map(out)` |

### 2.4 `GpuKernelMixin`

```python
@mixin
class GpuKernelMixin:
  """P1 点wise kernel：子类实现 ``def run(...) -> T``；Host 用 ``.map``。"""

  blockSize: int = 256

  def map(self, *fields: Field) -> None:
    """译期专用（``TRANSLATOR_ONLY_METHODS``）；末参须为 output Field。"""
    ...
```

- 子类 **`@dataclass`**（可有/无 uniform 字段）；
- **`run` 名**与 `TestCaseMixin.run` 同形不同 mixin，**勿**多重继承两者。

### 2.5 `@GpuDeviceMeta`

```python
@annotation
@dataclass
class GpuDeviceMeta:
  """标记模块级 Device 辅助函数；仅 ``run`` / 其它 ``@GpuDeviceMeta`` 可调用。"""
  ...
```

- 装饰 **`@GpuDeviceMeta`** 于模块级 `def`（同 `@FlowNodeMeta` 用于方法）；
- Host **无**函数体 / 不可调用；
- Device 生成 **`__device__`**（或 backend 等价物）；
- P1：**不**支持类内 instance 方法作 Device helper（用模块级 Meta）。

### 2.6 `Field[T]`

| | |
|--|--|
| 工厂 | `a: Field[float] = new.zeros(n)`（或 `Field[float].zeros`）；`ones` / `fromHost` 同理 |
| 边界 | `copyFromHost`、`toHost() -> list[T]`、`copyToHost(dst @ref)` |
| `.map` | input/output **仅** `Field[T]`；禁止 Host `list` 直入 |

---

## 3. 译器与 codegen（P1）

```text
Add(c=1.0).map(a, b, out)
  → TRANSLATOR_ONLY：GpuKernelMixin.map
  → 校验：末参 Field = output；前 N 个 Field 对齐 run 的 N 个标量形参
  → 收集 Add.run + clamp01 等 @GpuDeviceMeta 可达 Device AST
  → __global__：for i in prange(n): out[i] = run_device(self, a[i], b[i])
  → uniform：dataclass 字段（c）
  → Host stub：launchKernel + 已绑 Field
```

| 模块 | 职责 |
|------|------|
| `passes/expand_gpu_map.py` | `.map` 脱糖；绑定 `run` / uniform / output Field |
| `passes/check_gpu_run.py` | `run` 与 `@GpuDeviceMeta` Device 子集 |
| `emit/gpu_map_emit.py` | `.map` → runtime 叶子 |
| `codegen/gpu_backend_cuda.py` | Device IR → `.cu`（``__device__`` / ``__global__`` + ``extern "C"`` launch） |

**后端选择**：

| 开关 | 行为 |
|------|------|
| `--gpu`（默认 `--gpu-backend=omp`） | `.map` → OpenMP；`@GpuDeviceMeta` → Host static 辅助 |
| `--gpu --gpu-backend=cuda` | `.map` → Host `cudaMalloc`/`Memcpy` + launch；旁路生成 `.cu`；`gpuSync` exit → `cudaDeviceSynchronize()` |

**Host 侧**：`run`、`@GpuDeviceMeta` 函数在 **omp** 下不生成普通 Host 可调用体（仅 GPU emit）；**cuda** 下 Device 体只进 `.cu`。

---

## 4. Device 域子集（P1）

### 4.1 `run` / `@GpuDeviceMeta` 允许

- 赋值、aug 赋值、`if`/`elif`/`else`、**`return expr`**；
- 算术、比较、链式比较、逻辑运算；
- **`self.<dataclass字段>`**（uniform）；
- 标量形参；
- 调用其它 **`@GpuDeviceMeta`** 模块函数；
- 局部标量变量。

### 4.2 禁止（译期报错）

| 类别 | 示例 |
|------|------|
| Host 堆类型 | `list`、`dict`、`str` |
| 异常 / 异步 | `raise`、`try`、`async`、`yield` |
| 闭包捕获 Host 局部 | kernel 外变量未作 uniform/形参传入 |
| 显式并行 | `for i in prange(...)`（**P1 禁止**；由 `.map` codegen 外包） |
| Host API | `print`、I/O、线程 |
| Host 调用 | 直接调 `run`、直接调 `@GpuDeviceMeta` |
| output 形参 | `run(..., out: float)`（P1 用 **返回值**，不用 out 形参） |

---

## 5. P2 及以后（非 P1）

| 项 | 说明 |
|----|------|
| **stencil** | `run` 内显式 `for i in prange(n)` + 邻域下标 |
| **规约** | `.reduce` 或新 mixin |
| **`Vector2/3/4[float]`** | 复用 `spatial.vector` |
| **多后端** | D3D12、GL、`--gpu-sim` |

---

## 6. Runtime、FFI、构建

- **默认验收后端**：**Host OpenMP sim**（`cl /openmp`）；`build.bat gpu --gpu --seq`。
- **CUDA AOT**：`--gpu --gpu-backend=cuda` 生成旁路 `.cu`；`compile.py` 调 `nvcc -c -arch=native` 并链 `cudart`；无 `nvcc` 时编译报错。新会话需 `CUDA_PATH`（如 `...\CUDA\v13.3`）与 `PATH` 含 `bin`。
- **`ffi/cuda`**：已由 `ffi.bat`/`gen_c_ffi.py` 从 `cuda_runtime_api.h` 生成 `ffi/cuda/cuda_runtime_api.pyi`（**勿手改**）；**不进 `minimal.h`**；业务层尚未全面改调 `ffi::cuda`（Host 现直 include `<cuda_runtime.h>`）。
- **`--gpu` / `--no-gpu` / `--gpu-backend`**：未启用时遇 `.map` / Host 调 `@GpuDeviceMeta` → **译期 error**。
- 验收：`test/gpu/test_vector_add.py`、`test_gpu_device_meta.py`；负向 `test/fail/test_gpu_host_device_meta_fail.py`；译器 `src/tests/test_gpu_backend_emit.py`。

---

## 7. 已定决策

| # | 决策 |
|---|------|
| 1 | P1 仅 **`.map` + 标量 `run` + 模块级 `@GpuDeviceMeta`** |
| 2 | **`run` 输出**：**`def run(...) -> float`**（返回值写回 output Field）；**不用** out 形参 |
| 3 | **`.map`**：**末参必须是 output `Field`**；其余为 input `Field` |
| 4 | 构造：**`new(kw=…)`** / **`Cls(kw).map(...)`**；禁止 **`new(Cls(...))`** |
| 5 | P1 点wise：**用户不写 `prange`**；grid 由 `.map` codegen 内部生成 |
| 6 | P1 **用户 API** 按 CUDA AOT 设计；默认 **`--gpu-backend=omp`**；**`--gpu-backend=cuda`** 生成 `.cu`；默认 **blockSize=256** |

---

## 8. 参考

- [编码规范 §2.2](./编码规范.md)（`new` / `Cls(...)`）
- `TestCaseMixin`、`FlowNodeMeta`、`assign`/`select`/`build`
- [py2cpp-design SKILL](../.cursor/skills/py2cpp-design/SKILL.md)
