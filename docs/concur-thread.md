# `py2cpp.concur.thread` 线程库设计方案

> 状态：增量实施中；已落地 Thread / registry / Lock / RLock / Condition / Event / Semaphore / BoundedSemaphore / Barrier / Future / ThreadPool / `atomic[T]` / `Queue[T]` / `T @thread_local` 字段基础能力  
> 语义基线：CPython 3.13 `threading` / `_thread`  
> 目标平台：C++11，优先 MSVC，同时保持 GCC / Clang 可移植性  
> 相关规范：[参考手册](./参考手册.md)、[编码规范](./编码规范.md)

## 1. 背景与定位

Py2Cpp 当前有两种并发相关能力，但都不能代替线程库：

- `py2cpp.concur.task` 是单线程协作式协程调度器；
- `py2cpp.concur.parallel.prange` 由译器发射 OpenMP 数据并行循环。

`py2cpp.concur.thread` 补充 OS 抢占式线程、阻塞同步原语和线程局部状态：

| 能力 | 调度方式 | 适合场景 |
|---|---|---|
| `Task` | 单线程协作式 | 帧循环、异步状态机、非阻塞业务流程 |
| `prange` | OpenMP 数据并行 | 独立迭代、数值计算、reduction |
| `thread` | OS 抢占式线程 | 阻塞 I/O、长期后台任务、生产者/消费者、显式同步共享状态 |

线程库不能只包装 `std::thread`。它必须同时解决：

1. target 和捕获对象的跨线程生命周期；
2. Py2Cpp 引用计数的跨线程数据竞争；
3. Lock、RLock、Condition 的 Python 特有语义；
4. 线程入口异常不能逃逸并触发 `std::terminate`；
5. timed join、daemon、运行时退出等 `std::thread` 不直接提供的能力。

## 2. 目标与非目标

### 2.1 目标

- 核心 API 与 CPython 3.13 `threading` 语义一致；
- `ThreadPool` 参考 CPython 3.13 `ThreadPoolExecutor` 的 worker、Future、shutdown 和 broken pool 语义；
- Python 标准库源码负责状态机、参数校验和组合逻辑；
- C++ 只实现线程创建、阻塞、唤醒、TLS、单调计时等原子叶子；
- 不引入 GIL，共享可变对象由用户显式加锁；
- timeout 统一使用单调时钟和绝对截止时间；
- 资源具有明确的销毁、join、detach 和跨线程存活规则；
- MSVC、GCC、Clang 对外语义一致；
- 测试不依赖固定调度顺序或固定 `sleep` 时长。

### 2.2 非目标

- 复刻 CPython GIL；
- 让无锁并发读写 `list`、`dict`、`str` 自动安全；
- 公开 CPython 内部 `_ThreadHandle`；
- 把 `Task` 改造成线程池；
- 用线程库替代 `prange`；
- 首版完整复刻 `concurrent.futures.Executor.map/as_completed/wait` 的所有高级行为；
- 首版实现 trace/profile hook、fork 重初始化和 alien thread 的全部细节。

## 3. 分层架构

```text
公共 API / Python 组合层
  Thread, Condition, Event, Semaphore, Barrier
                │
私有 primitive 层
  _ThreadState, _LockBase, deadline/TLS/registry helpers
                │
C++11 runtime 叶子
  OS thread, mutex, condition_variable, atomic, chrono, TLS
```

遵循 Native 原子化原则：

- `Event` 基于 `Condition`；
- `Semaphore`、`BoundedSemaphore` 基于 `Condition`；
- `Barrier` 基于 `Condition`；
- Condition waiter 队列和 timeout 循环位于 Python 层；
- 只有无法继续拆分的阻塞、线程句柄和 TLS 操作进入 C++。

单一真相源为 `py2cpp/`、`templates/`、`src/` 和 `test/`，禁止直接修改 `generated/`。

## 4. 实施前置项

### 4.1 原子化 `PyRefCount`

当前 `PyRefCount` 的 strong/weak count 是普通整数。不同线程复制或销毁同一引用计数对象会产生 C++ data race。

方案：

- 控制块计数改为 `std::atomic<int>` 或等价原子类型；
- strong/weak increment 使用 relaxed；
- decrement 至零使用 acquire-release；
- 对象销毁前建立必要的可见性；
- `weak.lock()` 使用 CAS，禁止“检查大于零后普通递增”的竞态；
- 原子引用计数只保证对象生命周期，不让对象内容自动线程安全。

必须回归：strong/weak copy、release、lock、最后 strong/weak 并发释放、基类/派生类转换，以及现有 Task/容器/异常回归。

### 4.2 增加 owning callable

当前 `PyCallable` 只有裸 `void* _closure + _func`，不拥有绑定对象或 lambda。`Thread.start()` 返回后 target 可能悬空。

需要在 callable 基础设施层增加拥有生命周期的类型擦除，而不是在线程模块里重复造闭包系统：

```text
OwnedCallable control block
  atomic refcount
  _func(_closure)
  destroy(_closure)
  concrete closure storage
```

要求：

- 模块函数可以使用静态 context；
- 绑定方法持有 owner 强引用或稳定值副本；
- lambda 捕获对象由 control block 拥有；
- start 将 target 转移或复制到 thread state；
- worker 结束后释放 target；
- 禁止无所有权保证的 raw `this` 跨线程。

首版建议：

```python
Thread(target: Callable[[], None], name: str = "", daemon: bool = False)
```

任意 `args/kwargs` 不适合静态类型系统。首版通过 owning 闭包或绑定方法预先绑定参数；后续如增加 typed args，应设计泛型重载，不能退化成无类型字典。

## 5. 线程安全模型

### 5.1 保证

- Thread 状态查询和 join 是线程安全的；
- Lock/RLock/Condition/Event/Semaphore/Barrier 的公开操作是线程安全的；
- 原子化后的引用计数可跨线程 retain/release；
- thread start、锁 release/acquire、worker completion/join 建立相应 happens-before。

### 5.2 不保证

- 普通容器的无锁并发读写；
- 写入同一 `PyStr`、`PyList`、`PyDict` 时其他线程同时访问；
- `PyDelegate` 的无锁 add/remove/invoke；
- 裸指针目标的跨线程生命周期；
- 未经同步发布对象的可见性。

用户文档必须明确：共享可变状态需要由同一把锁或更高层同步对象保护。

## 6. 文件布局

### 6.1 新增

| 文件 | 职责 |
|---|---|
| `py2cpp/concur/thread.py` | 公共 API、状态机、校验、组合逻辑 |
| `templates/concur/-thread.inl` | 线程、锁、等待、TLS、registry native 叶子 |
| `templates/concur/+thread.h` | 仅在必须注入 native 字段或声明时使用 |
| `test/concur/test_thread.py` | 兼容和并发测试 |
| `test/concur/test_thread_pool.py` | ThreadPool/Future 兼容测试 |
| `src/tests/test_thread_*.py` | 仅在新增译器能力时增加 |

新模块会由 `stdlib_discovery.py` 自动发现，不应维护重复注册表。

### 6.2 可能修改

| 文件 | 原因 |
|---|---|
| `templates/core/refcount.h` | 原子引用计数 |
| `templates/core/delegate.h` | owning callable |
| `py2cpp/core/exceptions.py` | `BrokenBarrierError`、`TimeoutError`、`CancelledError`、`InvalidStateError`、`BrokenThreadPoolError` 等异常 |
| `py2cpp/util/deque.py` 或新增 queue primitive | ThreadPool 阻塞工作队列 |
| `src/compile.py` | GCC/Clang 编译链接增加 `-pthread` |
| `docs/参考手册.md` | 模块和线程安全模型 |
| `docs/编码规范.md` | 跨线程对象与同步规则 |

是否修改 translator 由最小原型验证决定。不得为了绕开基础设施问题改变 Python 公共语义。

## 7. Native primitive

### 7.1 `_ThreadState`

Thread 对象与 worker 生命周期必须解耦。建议 state 包含：

```text
atomic state refcount
thread handle
state mutex + condition_variable
phase: initial / starting / running / stopped
started / finished / joined / daemon
runtime ident / native id
owning target / name copy
```

生命周期：

1. Thread 对象持有 owner state 引用；
2. start 创建 worker state 引用；
3. worker 建立 TLS、ident、registry 后发布 started；
4. target 结束后清理 target，标记 stopped 并通知 joiner；
5. worker 和 Thread 对象分别释放引用；
6. 最后一个引用销毁 state。

不建议依赖 `std::shared_ptr`，应使用与 Py2Cpp 规则一致的最小原子 control block。

### 7.2 线程 ID

- `Thread.current.ident` 返回运行时分配的非零 `uint64` cookie；
- `thread_local` 保存当前 cookie；
- 主线程在 runtime 初始化时登记；
- 新线程从原子计数器分配 cookie；
- cookie 不作为永久身份或数组下标；
- `Thread.current.nativeId` 使用平台 API：Windows `GetCurrentThreadId`，Linux `gettid`，macOS `pthread_threadid_np`。

### 7.3 普通 Lock

Python Lock 没有 owner，允许非 acquire 线程 release。`std::mutex` 要求 owner unlock，因此不能直接作为公开 Lock。

使用：

```text
state mutex
condition_variable
bool locked
```

- acquire 在 state mutex 下检查/设置 `locked`；
- 阻塞路径用 condition variable 循环等待；
- release 检查后设置 false 并 `notify_one()`；
- 任意线程可以 release；
- 未锁 release 抛 `RuntimeError`。

### 7.4 RLock

state 包含 `owner_ident + recursion_count + mutex + condition_variable`：

- owner 重入仅递增 count；
- 非 owner 等待 owner 清空；
- 非 owner release 抛 RuntimeError；
- count 归零后清空 owner 并唤醒 waiter；
- 为 Condition 提供 `_releaseSave()`、`_acquireRestore()`、`_isOwned()`；
- 完全释放和恢复必须保留递归层数。

### 7.5 timeout

- 仅 API 指定的 `-1` 代表无限等待；
- 其他负值按对应 CPython API 抛 ValueError 或折算为零；
- `blocking=False` 与显式非默认 timeout 冲突时抛 ValueError；
- 无穷或超过平台范围抛 OverflowError；
- 使用 monotonic 绝对 deadline；
- 伪唤醒后重新计算剩余时间；
- 常规超时返回 False，不抛 TimeoutError。

## 8. API 分期

### 8.1 第一阶段

```python
Thread
Lock
atomic[T]
Queue[T]
RLock
Condition
Event
Semaphore
BoundedSemaphore
Thread.current
Thread.main
Thread.activeCount
Thread.actives
```

第一阶段可以只支持 `daemon=False`，但必须明确拒绝 `daemon=True`，不能静默伪兼容。

当前已落地子集：

- `Thread(target: Callable[[], None], name="", daemon=False)`；
- `Thread.current`、`Thread.main`、`Thread.activeCount` 与 `Thread.actives`：返回持有同一 native handle 的稳定 `Thread` 包装，不返回 raw 指针；不再保留同义模块级全局函数；
- `Lock`；
- `RLock`：owner 递归、非 owner release 抛错、为 `Condition` 提供完整释放/恢复递归层数；
- `Condition`：支持默认 `RLock`、外部 `Lock` / `RLock`、`wait`、`waitFor`、`notify`、`notifyAll` 与上下文管理器；
- `Event`：Python 组合层基于 `Condition + atomic[bool]`，支持 `isSet`、`set`、`clear`、`wait`；
- `Semaphore` / `BoundedSemaphore`：Python 组合层基于 `Condition + atomic[int]`，支持 `acquire`、`release(n)` 与上下文管理器；
- `atomic[T]`：共享 native 原子状态，支持 `load/store/exchange/compareExchange/fetchAdd/fetchSub`；
- `Queue[T]`：对齐 Python 3.13 `queue.Queue` 的 FIFO、`put/get`、`putNowait/getNowait`、`qsize/__bool__/full`、`taskDone/join`、`shutdown(immediate=False)` 主线语义；
- `Barrier`：基于 `Condition + atomic[int]` 的 Python 组合层实现，支持 `wait/reset/abort/parties/nWaiting/broken` 与 action 主线；
- `Future[R]`：`@refcount` 共享状态，支持 `cancel/cancelled/running/done/result/exception/setRunningOrNotifyCancel/setResult/setException`；
- `ThreadPool[R]`：`@refcount` 共享线程池状态，使用 `Queue[_WorkItem[R]] + Thread` worker，支持 `submit/shutdown(wait, cancelFutures)`；
- `EmptyError`、`FullError`、`ShutDownError`；
- `BrokenBarrierError`、`CancelledError`、`TimeoutError`、`InvalidStateError`、`BrokenThreadPoolError`；
- `name: T @thread_local = value` 类字段：生成 C++11 `static thread_local`，通过 `Self.name` / `Class.name` / `self.name` 访问。

当前仍未承诺的管理能力：daemon shutdown manager、alien/dummy thread、trace/profile hook、Timer 与 `threading.local` 动态属性对象。

### 8.2 第二阶段

```python
Future[R]
ThreadPool
BrokenThreadPoolError
CancelledError
InvalidStateError
```

第二阶段参考 CPython 3.13 `ThreadPoolExecutor`，但以静态类型友好的 `submit[R](Callable[[], R]) -> Future[R]` 为首版边界。

### 8.3 第三阶段

```python
Barrier
BrokenBarrierError
Timer
daemon + runtime shutdown manager
threading 风格 excepthook
```

### 8.4 第四阶段

```python
local
alien/dummy thread
trace/profile hooks
stack_size
interrupt_main
fork 重初始化
```

## 9. `Thread` 语义

### 9.1 状态机

```text
INITIAL -> STARTING -> RUNNING -> STOPPED
```

- 一个对象最多 start 一次；
- 二次 start 抛 `RuntimeError("threads can only be started once")`；
- start 返回时 ident 已设置；
- 创建失败必须回滚 registry/state；
- run 调用 target；
- target 结束后清除 target/闭包引用；
- ident 在线程结束后保留，但允许以后被复用。

### 9.2 join

- 可重复调用，总是返回 None；
- timeout 后通过 `alive` 属性判断；
- 未启动 join、自 join 抛 RuntimeError；
- 负 timeout 按 CPython `Thread.join` 视为零；
- `std::thread` 没有 timed join，timeout 等待 state condition variable；
- native join 只能执行一次，多 joiner 需要协调；
- 成功 join 建立 worker 写入的可见性。

### 9.3 异常

线程入口必须 catch 全部异常，不能让异常逃逸到 C++ thread entry：

- 受支持异常进入受限版 excepthook；
- join 不重抛 target 异常；
- 不能按异常基类值保存而发生 slicing；
- 未知 native 异常至少输出线程名，并保证不触发 `std::terminate`；
- finally 路径始终标记 stopped、清 registry、通知 joiner。

### 9.4 daemon

daemon 不能简单等同于 `std::thread::detach()`，否则 worker 可能访问已销毁的 runtime/global 对象。

正式支持前必须具备 shutdown manager：

- 维护 active 和 non-daemon registry；
- main 返回前等待非 daemon 线程；
- daemon 不阻止进程退出；
- registry 生命周期晚于普通全局对象，或使用受控常驻状态；
- 文档明确 daemon 退出不保证正常 finally 清理。

在此之前首版只允许非 daemon。

## 10. `ThreadPool` 语义

`ThreadPool` 是 `py2cpp.concur.thread` 中参考 CPython 3.13 `ThreadPoolExecutor` 的线程池。对外命名采用 Py2Cpp 标准库风格，语义对齐 executor：提交任务返回 Future，worker 从共享队列取任务，shutdown 后拒绝新任务，initializer 失败后池进入 broken 状态。

### 10.1 公共 API

首版建议：

```python
@refcount
class Future[R]:
  def cancel(self) -> bool: ...
  def cancelled(self) -> bool: ...
  def running(self) -> bool: ...
  def done(self) -> bool: ...
  def result(self, timeout: float = -1.0) -> R: ...
  def exception(self, timeout: float = -1.0) -> Exception | None: ...

@refcount
class ThreadPool[R]:
  def __init__(
    self,
    maxWorkers: int = 0,
    threadNamePrefix: str = "",
    initializer: Callable[[], None] | None = None,
  ): ...

  def submit(self, fn: Callable[[], R]) -> Future[R]: ...
  def shutdown(self, wait: bool = True, cancelFutures: bool = False) -> None: ...
```

差异与约束：

- 当前实现是静态类型友好的 `ThreadPool[R]`：一个 pool 处理同一返回类型 `R` 的任务；异构 `submit[R]` 需要后续 type-erased Future；
- 当前实现默认 `maxWorkers=4`；`min(32, cpu_count + 4)` 需要补 `cpu_count` native leaf 后恢复；
- `initializer` 首版使用零参数 callable，参数由 owning 闭包预绑定；
- `submit` 首版只接受零参数 callable，返回 `Future[R]`；当前回归覆盖模块函数 callable，泛型 `@refcount` 方法调用点的 lambda 返回类型推断仍需在译器调用分派中补强；
- CPython 的 `map`、`as_completed`、`wait` 先不作为首版目标；
- `Future.add_done_callback` 可后置，避免先引入跨线程 callback 生命周期问题；
- `Future.result(timeout)` 超时抛 `TimeoutError`，取消抛 `CancelledError`；任务异常首版标记为异常完成并在 `result()` 读取时抛 `RuntimeError("Future task raised")`。
- `Future.exception(timeout)` 首版返回 `bool` 表示是否异常完成；完整异常对象保存与重抛需要异常 type-erasure，后续补齐。

### 10.2 Future 状态机

Future 状态参考 `concurrent.futures._base`：

```text
PENDING -> RUNNING -> FINISHED
PENDING -> CANCELLED -> CANCELLED_AND_NOTIFIED
```

规则：

- `cancel()` 只能取消尚未 RUNNING 的任务；
- 已 RUNNING 或 FINISHED 时 cancel 返回 False；
- 重复 cancel 返回 True；
- worker 执行前必须调用 `setRunningOrNotifyCancel()`；
- 若 Future 已取消，worker 不执行任务；
- `setResult` 和 `setException` 只能从 RUNNING/PENDING 的合法路径进入 FINISHED；
- 状态变化通过 Condition 通知所有等待者；
- result/exception 使用 monotonic deadline 等待；
- 保存异常时必须避免 slicing，不能只存基类 `Exception` 值。

异常类型建议：

- `CancelledError`；
- `InvalidStateError`；
- `BrokenThreadPoolError`；
- `TimeoutError`，若项目已有内建异常则复用，否则补到 `core.exceptions` 或 `concur.thread` 中并记录差异。

### 10.3 WorkItem

WorkItem 保存：

```text
Future[R]
OwnedCallable[R]
```

执行流程：

1. 调用 `future.setRunningOrNotifyCancel()`；
2. 返回 False 时直接丢弃 work item；
3. 调用 callable；
4. 成功则 `future.setResult(result)`；
5. 抛异常则 `future.setException(exc)`；
6. 释放 callable 捕获和 work item 引用。

首版不支持 `fn, *args, **kwargs`，调用者通过 owning callable 绑定参数。

### 10.4 工作队列

CPython 使用无界 `queue.SimpleQueue`。Py2Cpp 可以实现私有 `_WorkQueue[T]`：

```text
mutex
condition_variable
deque[WorkItem | Sentinel]
closed flag
```

要求：

- `put` 在锁下入队并 notify_one；
- `get` 阻塞直到有 work item 或 sentinel；
- `getNowait` 供 shutdown(cancelFutures=True) 和 initializer failed drain 使用；
- 队列不承诺公平性；
- sentinel 使用明确的 variant/union，不能用裸 `None` 与合法任务混淆；
- 队列元素持有 work item 生命周期，worker 取走后负责释放。

如果现有 `deque` 不适合跨线程阻塞队列，应新增最小 native queue primitive；不要在 ThreadPool 里手写一套与容器重复的链表。

### 10.5 worker 循环

worker 参考 CPython 3.13：

1. 线程启动后先执行 initializer；
2. initializer 抛异常时，调用 `_initializer_failed()`，池进入 broken；
3. 循环优先尝试无阻塞取任务；
4. 队列空时释放 `_idle_semaphore`，再阻塞等待；
5. 取到 work item 时执行并继续；
6. 取到 sentinel 后检查全局 shutdown、executor 是否销毁、executor 是否 shutdown；
7. 需要退出时重新放入 sentinel 唤醒其他 worker，然后返回；
8. worker 外层 catch 所有异常，记录诊断并保持进程不 terminate。

`_idle_semaphore` 的作用是避免在已有 idle worker 时继续创建新线程。`submit` 入队后调用 `_adjustThreadCount()`，若能立即 acquire idle semaphore，说明已有空闲线程，不新建线程。

### 10.6 创建线程

`_adjustThreadCount()`：

- 若有 idle worker，直接返回；
- 当前线程数小于 maxWorkers 时创建新 Thread；
- 线程名使用 `threadNamePrefix + "_" + index`；
- worker target 必须由 owning callable/state 保活；
- 新线程加入 `_threads` 集合和全局 pool registry；
- start 失败时必须从集合、registry、队列状态中回滚。

默认 `maxWorkers` 参考 CPython 3.13：

```text
min(32, cpu_count + 4)
```

`process_cpu_count` 可以先由 native leaf 提供；若无法取得，按 1 处理。

### 10.7 shutdown

`shutdown(wait=True, cancelFutures=False)`：

- 持 `_shutdown_lock` 设置 `_shutdown = True`；
- `cancelFutures=True` 时 drain 队列，并取消尚未开始的 Future；
- 已 RUNNING 的任务不取消；
- 入队一个 sentinel 唤醒阻塞 worker；
- `wait=True` 时 join 所有 worker；
- `wait=False` 不等待，但 state 必须保证 worker 结束前 pool 相关资源仍存活；
- shutdown 后 submit 抛 RuntimeError；
- interpreter/runtime shutdown 时全局 registry 入队 sentinel 并等待非 daemon worker。

### 10.8 broken pool

initializer 失败后：

- 设置 `_broken` 文本；
- drain work queue；
- 对所有未开始任务设置 `BrokenThreadPoolError` 异常；
- 后续 `submit` 抛 `BrokenThreadPoolError`；
- 已开始任务按自身路径完成；
- worker 不再继续取普通任务。

### 10.9 生命周期风险

ThreadPool 比 Thread 更依赖基础设施：

- Future 保存 result/exception，需要泛型存储和异常 type erasure；
- WorkItem 队列跨线程移动 callable，必须依赖 owning callable；
- pool、worker、queue 之间存在环状生命周期，必须使用明确的 state 引用或弱引用策略；
- `wait=False` shutdown 不能让 pool 对象析构后 worker 访问悬空队列；
- callback 和 map 会扩大 callable 生命周期面，首版后置。

因此 ThreadPool 应在 Thread、Condition、owning callable、原子 refcount 完成后实施。

## 11. 同步对象语义

### 11.1 Lock / RLock

Lock：二态、无 owner、任意线程可 release、未锁 release 抛 RuntimeError、不承诺公平性，支持 context manager。

RLock：只有 owner 可 release，递归次数匹配后才真正解锁；Condition 可完全释放并恢复递归层数。

### 11.2 Condition

设计目标采用 CPython 风格的“外部底锁 + waiter 队列”组合：

```python
_lock: Lock | RLock
_waiters: list[Lock]
```

`wait(timeout)`：

1. 验证调用者持有底锁；
2. 创建并预先 acquire waiter Lock；
3. 加入 waiter 队列；
4. 完全释放底锁并保存 RLock 状态；
5. 阻塞获取 waiter，支持 timeout；
6. finally 中重新取得底锁并恢复递归层数；
7. 超时时从队列移除；
8. 被通知返回 True，超时返回 False。

`notify(n)` 要求持有底锁，从队列取出至多 n 个 waiter 并 release 它们，但不释放 Condition 底锁。被唤醒线程需等 notifier 离开临界区后继续。

`waitFor(predicate, timeout)` 在持锁状态先求值，使用循环抵抗竞态/伪唤醒，并复用同一个绝对 deadline。

当前实现为 native 条件变量叶子：`Condition` 仍绑定真实的外部 `Lock` / `RLock`，`wait()` 仍完整释放底锁并在返回前恢复 RLock 递归层数；waiter 队列由 native `waiters/signals` 计数表达，而不是在 Python 层显式维护每 waiter 一把 `Lock`。这是实现形态差异，不改变当前公开语义。`Event`、`Semaphore` 和 `BoundedSemaphore` 则保留在 Python 组合层，不额外引入整类 native 状态。

### 11.3 Event

Event 基于 `Condition + bool flag`：初始 clear；set 设置 flag 并 notifyAll；clear 只清 flag；set 后新 waiter 立即通过。已被 set 唤醒的 waiter 即使随后发生 clear，本次仍应按成功返回，不能做成自动复位事件。

### 11.4 Semaphore

- 初值必须 >= 0；
- acquire 在 value > 0 时原子递减，否则等待；
- release(n) 要求 n >= 1，增加计数后通知至多 n 个 waiter；
- BoundedSemaphore 保存 initial，过量 release 先抛 ValueError，状态不变；
- 不承诺公平性。

### 11.5 Barrier

当前基于 Condition 实现四态：`filling(0)`、`draining(1)`、`resetting(-1)`、`broken(-2)`。

- parties >= 1；
- 每轮 index 为 0..parties-1；
- 最后到达者执行 action 后进入 draining；
- 全部离开后恢复 filling，可循环复用；
- timeout 破坏整轮；
- action 抛异常时 barrier 进入 broken，等待方得到 `BrokenBarrierError`；首版执行 action 的线程也抛 `BrokenBarrierError`，原异常保留待异常 type-erasure 后补齐；
- abort 进入 broken；reset 使当前 waiter 抛 BrokenBarrierError，排空后恢复。

## 12. Registry 与 Thread 静态入口

registry 已支撑 `Thread.current` / `Thread.main` / `Thread.activeCount` / `Thread.actives`，后续继续支撑 shutdown：

- 受 native mutex 保护；
- 保存带原子引用计数的 `_ThreadHandle` state，不能保存 raw `Thread*`；
- worker 发布 started 前进入 active registry；
- stopped finally 中移除；
- main thread 在首次使用线程 API 或启动 worker 前登记；
- 外部线程作为后续 alien/dummy thread 支持项。

`Thread.current` / `Thread.main` / `Thread.actives` 返回 `Thread` 包装对象，包装对象复制 `_ThreadHandle` 并共享 native state，因此不会悬空。

## 13. `threading.local`

`local` 后置，因为它不仅是一个 `thread_local` 字段：

- 每个 local 对象在每个线程有独立 attribute dict；
- subclass `__init__` 在各线程首次访问时各执行一次；
- 构造参数需保存并在每线程初始化时复用；
- 线程结束和 local 销毁都需清理状态；
- 不能永久使用可复用 numeric ident 作 key；
- 普通属性线程隔离，但 `__slots__` 按 CPython 语义并不线程局部。

实现前需确认动态属性、描述符和 subclass init 能否表达这些语义，不能提供固定字段的同名伪实现。

已支持的 `T @thread_local` 是更小的静态类型能力：它只表示“类级静态字段按线程隔离存储”，不提供动态 attribute dict、子类每线程 `__init__` 或 CPython `threading.local` 的对象级语义。

示例：

```python
from py2cpp import *

class TLSCounter:
  value: int @thread_local = 0

  def bump(self) -> int:
    self.value += 1
    return self.value
```

生成形态等价于：

```cpp
class TLSCounter {
  static thread_local PyInt value;
};
```

## 14. 构建与平台

native 模板预计使用：

```cpp
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <chrono>
```

这些是线程基础设施，不用于替代 Py2Cpp 容器或字符串。

- MSVC 通常无需额外链接参数；
- GCC 编译和链接都增加 `-pthread`；
- Clang 非 MSVC ABI 时增加 `-pthread`；
- 不得只加编译参数而漏掉链接参数；
- 线程命名是可选增强，失败不影响 Python `Thread.name`；
- 信号中断阻塞 Lock 的能力按平台标注；
- `TIMEOUT_MAX` 根据 chrono/OS 表示范围计算，不硬编码某平台数值。

## 15. 测试矩阵

### 15.1 原则

- 用 Event、Condition、Barrier 握手，不靠固定 sleep 猜测调度；
- 不断言 waiter 唤醒顺序；
- timeout 只断言状态和返回值，时间边界留余量；
- Debug/慢机器上也必须稳定；
- 线程异常测试确认进程不会 terminate。

### 15.2 Thread

- start/ident/alive/正常 join/重复 join；
- 二次 start、未 start join、自 join；
- join timeout；
- 多 joiner；
- target 捕获对象的生命周期；
- target 异常进入 hook；
- Thread 对象提前释放时 worker state 仍存活。

### 15.3 Lock/RLock/Condition/Event

- Lock 非阻塞、timeout、跨线程 release、未锁 release；
- blocking=False 与 timeout 冲突；
- RLock 递归、非 owner release、归零才唤醒；
- Condition 未持锁 wait/notify 异常；
- notify 后 notifier 仍持有底锁；
- RLock 多层递归经过 wait 后恢复；
- waitFor 抵抗无关通知；
- Event set/clear/wait/set 后立即 clear 竞态。

### 15.4 Semaphore/Barrier

- Semaphore 初值、非阻塞、timeout、release(n)；
- BoundedSemaphore 过量 release 原子失败；
- Barrier 多轮、index、timeout、action、reset、abort、broken、nWaiting。

### 15.5 refcount/callable

- 多线程 retain/release；
- weak lock 与最后 strong release 竞争；
- lambda 捕获跨 start 返回后仍有效；
- 绑定 refcount 对象的方法由 target 保活；
- worker 后闭包只销毁一次；
- start 失败不泄漏 callable。

### 15.6 ThreadPool/Future

- 默认 maxWorkers；
- submit 返回 typed Future；
- Future cancel/running/done/result/exception；
- result timeout 抛 TimeoutError；
- 任务异常经 Future.result 重新抛出；
- 已取消任务不执行；
- idle worker 存在时不创建新线程；
- maxWorkers 限制；
- shutdown 后 submit 抛 RuntimeError；
- shutdown(wait=True) 等待所有 worker；
- shutdown(wait=False) 不悬空队列/state；
- cancelFutures=True 只取消未开始任务；
- initializer 成功时每个 worker 调用一次；
- initializer 失败后池 broken，排队任务得到 BrokenThreadPoolError；
- sentinel 唤醒所有 worker；
- pool 对象提前释放时 worker 能有序退出。

## 16. 实施阶段

### 阶段 0：能力验证

- 验证 `Callable[[], None]` 字段、绑定方法、lambda 的实际 C++ 形态；
- 验证 `@refcount` Thread/Lock 层次和 `new()` 写法；
- 验证 native template 注入顺序；
- 不提交临时绕行 API。

### 阶段 1：线程安全基础设施

- 原子化 PyRefCount，修正 weak lock CAS；
- 增加 owning callable；
- 完成基础设施单测和现有全量回归。

该阶段与线程公共 API 分开审阅。

### 阶段 2：低层 primitive

- `_ThreadState`、`Thread.current` / `Thread.main`、main TLS；
- Lock/RLock、monotonic timed wait；
- 线程入口异常兜底；
- GCC/Clang `-pthread`。

### 阶段 3：首版公共 API

- Thread、Condition、Event、Semaphore/BoundedSemaphore；
- registry 支撑的 `Thread` 静态入口；
- 文档和测试矩阵。

### 阶段 4：ThreadPool/Future

- Future 状态机和异常类型；
- 阻塞 work queue；
- ThreadPool submit、worker loop、idle semaphore；
- shutdown、cancelFutures、broken pool；
- ThreadPool 测试矩阵。

### 阶段 5：高级兼容

- Barrier/BrokenBarrierError；
- excepthook；
- daemon + shutdown manager；
- Timer。

### 阶段 6：TLS 与工具能力

- local、alien/dummy thread；
- trace/profile/stack_size 等扩展。

## 17. 验证流程

每阶段完成后：

1. 对照 `docs/编码规范.md` 自检标准库 Python 写法；
2. 确认 native 已缩小到不可再拆的叶子；
3. 确认未手改 `generated/`；
4. bootstrap runtime：

   ```bat
   python main.py py2cpp\__init__.py -o generated --no-main
   ```

5. 编译并执行 `test/concur/test_thread.py` 和 `test/concur/test_thread_pool.py`；
6. 回归 refcount、delegate、Task、parallel；
7. 执行 MSVC 全量 `build_all.bat`；
8. 条件允许时执行 GCC/Clang 编译链接；
9. 崩溃难定位时用 `--debug`，不得手改生成代码猜测。

## 18. 完成标准

- target 不存在裸 context 悬空；
- PyRefCount retain/release 可安全跨线程；
- Future result/exception/cancel 状态机与 worker 执行竞态正确；
- ThreadPool shutdown 后没有 worker 访问已释放 pool/queue；
- 线程入口异常不会导致 `std::terminate`；
- Lock 支持跨线程 release，未做 `std::mutex` 非 owner unlock；
- Condition 正确恢复 RLock 递归层数；
- timed wait 全部使用 monotonic deadline；
- daemon 有 shutdown manager，否则明确拒绝；
- 已知 CPython 差异有文档；
- MSVC 回归通过，GCC/Clang 线程链接参数完整；
- 测试不依赖固定调度顺序。

## 19. 已确定的设计决策

1. 不改变 Task 和 prange 定位；
2. Python 层保留状态机和组合语义；
3. Lock 使用 flag + condition variable，不直接包装 `std::mutex`；
4. Condition 使用 per-waiter Lock 队列；
5. 先解决 owning callable 和原子引用计数；
6. 无 GIL，共享可变状态由用户加锁；
7. 首版 target 使用零参数 `Callable[[], None]`，参数由闭包绑定；
8. ThreadPool 首版使用 `submit[R](Callable[[], R]) -> Future[R]`，参数由闭包绑定；
9. ThreadPool 先实现 submit/Future/shutdown，不首版承诺 map/as_completed/wait；
10. daemon 在 shutdown manager 前不做伪兼容；
11. local 在动态属性和 TLS 生命周期确认前后置。

## 20. 实施前仍需确认

1. 第一阶段是否只允许 `daemon=False`；
2. 是否接受首版零参数 target，通过闭包绑定参数；
3. ThreadPool 是否纳入第二个交付批次，还是等 Barrier/daemon 之后；
4. Future 是否首版支持 `add_done_callback`；
5. Barrier 纳入首版还是后续阶段；
6. 首个合入版本是否要求同时通过 GCC/Clang，还是先以 MSVC 为门槛；
7. 已确定：不保留 `current_thread()` 等模块级全局函数；线程 registry 仅通过 `Thread.current` / `Thread.main` / `Thread.activeCount` / `Thread.actives` 暴露。

这些选择只影响迭代边界，不改变基础安全要求。
