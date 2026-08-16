# Py2Cpp `alg` 标准库域 — 设计与分期方案

> **状态**：P0.5/P1b + P1 + P2 + **P3**（`grid2d` / `graph` / `navigate` + ``NavigatableType``）已落地；P3b `spatial_hash`、P4 见 §7。  
> **单一真相源（实现后）**：`py2cpp/alg/*.py`  
> **关联**：[编码规范](./编码规范.md)、[参考手册](./参考手册.md)、[py2cpp-design](../.cursor/skills/py2cpp-design/SKILL.md)

---

## 1. 目标与边界

### 1.1 目标

在 **`py2cpp/alg/`** 提供 **ACM 算法竞赛** 与 **游戏开发** 中高频使用的**数据结构**（非完整算法库）：

- 用规范 Python（PEP 695 泛型）描述，由译器生成 C++11 模板；
- 复用现有 `list` / `dict` / `array` / `deque` / `Pool` / `Counter` 等，**禁止 STL**；
- 纳入 `py2cpp/alg/` 源树（``constant/stdlib_discovery`` 自动发现），支持 `from py2cpp import *`；
- 每个模块配套 `test/alg/test_*.py` + MSVC 集成测。

### 1.2 非目标（本期不做）

| 类别 | 说明 |
|------|------|
| 通用图算法库 | 网络流、JPS、flow field 等；**仅** `navigate.py` 提供对 ``NavigatableType`` 的 ``astar`` / ``dijkstra`` |
| CPython 兼容模块 | 不实现 `heapq` 模块；提供 **`alg.Heap`** 类即可 |
| 高级平衡树 | 替罪羊、FHQ Treap、LCT、可持久化结构 |
| 字符串进阶 | SAM、后缀数组/自动机 |
| 3D 专用 | KD-Tree、八叉树（四叉树放 P4 可选） |
| GPU / 多线程结构 | 超出 Py2Cpp 当前模型 |

### 1.3 与现有标准库的分工

| 场景 | 使用现有模块 | `alg` 补充 |
|------|-------------|-----------|
| 动态数组、栈数组 | `list`、`array`、`StackArray` | — |
| 双端队列（CPython 语义） | `util/deque` | — |
| 分块双端队列、大块两端 push/pop | — | **`ChunkDeque`**（`chunk_deque`） |
| 可 splice/concat 的序列（rope 语义） | `str` 不可变 | **`ChunkDeque`**（`chunk_deque`：`splice` / `extend` / `insert`） |
| 滑动窗口最值 | `deque` / `ChunkDeque` | 单调队列**语义**（`mono_queue`） |
| 哈希、多重集 | `dict`、`set`、`Counter` | — |
| 对象池、临时缓冲 | `Pool`、`Arena` | — |
| ECS | `design/ecs` | — |
| 固定规模索引结构 | — | DSU、BIT、线段树、堆、Trie、ST 等 |
| 2D 空间粗筛 | — | `grid2d`、`spatial_hash`（游戏） |

---

## 2. 推荐约定（默认决策）

实现与文档均按下列默认约定，除非后续 Issue 明确变更。

| 项 | 决策 |
|----|------|
| **下标** | 全程 **0-based**（与 Py2Cpp 一致）；ACM 题面 1-based 由调用方 `i - 1` |
| **容量** | 竞赛向结构构造时给定 `n`，内部 `array` / 定长 `int[:]`；游戏向可选 `reserve` 提示（参考 `Arena.reserve` 占位语义） |
| **拷贝 / 移动** | **无** ``@copyable``；``dst = src`` → **移动**（``__move__``）；显式副本 ``dst = src.copy()``（对齐 ``util/list`` / ``util/deque``） |
| **块节点** | 指针链式块节点标 **`@boxing``**（对齐 ``DictEntryUnsafe`` / ``util/deque``） |
| **堆元素** | **`Heap[T: ComparableType]`**，支持 `int` / `int64` 及实现 `__lt__` 的类型 |
| **线段树 v1** | **点修 + 区间 min/max/sum**；**不做**懒标记 / 区间赋值 |
| **Trie 键** | 首期仅 **`str`**（码点）；`list[int]` 通用 Trie 放 P2+ |
| **导出** | 包根 `__all__` 导出短名：`DSU`、`FenTree`、`Heap`、`MonoQueue`、`ChunkDeque` 等 |
| **块大小** | `ChunkDeque` 默认 **`blockSize=512`**（构造可改；须写清文档） |
| **命名空间** | C++：`py2cpp::alg::<module>::<Class>` |

---

## 2.5 统一 API 范式（已实现模块）

下列约定适用于 **P1 / P1b / P2 已落地** 模块；新模块须对齐，勿再引入闭区间 `query(l,r)` / 字符串 `mode` / `build()` 等旧草案 API。

### 索引结构（``FenTree`` / ``SegTree`` / ``SparseTable``）

| 写法 | 语义 |
|------|------|
| ``st[i]`` | 单点查询（``FenTree`` / ``SegTree`` 为当前值；``SparseTable`` 为静态原数组第 ``i`` 项） |
| ``st[l:r]`` | **半开区间** ``[l, r)`` 聚合（``FenTree`` 为区间和；``SegTree`` / ``SparseTable`` 为 min/max/sum 等） |
| ``st[i] = v`` | 单点赋值 / 点修（``SparseTable`` **无** ``__setitem__``，静态） |
| ``len(st)`` / ``i in st`` | 长度 / 下标是否在 ``[0, len)`` |
| 空切片 ``st[l:l]`` | 聚合**单位元**（``AggModeEnum`` 决定：``Sum``→0，``Min``→极大，``Max``→极小） |

闭区间旧写法 ``query(l, r)``（含 ``r``）→ 改为 ``st[l:r+1]``。

### ``AggModeEnum`` 枚举

- 构造：``SegTree(n, AggModeEnum.Sum)``、``SparseTable(data, AggModeEnum.Min)``；
- **禁止**字符串 ``"sum"`` / ``"min"``；
- ``SegTree`` 支持 ``Min`` / ``Max`` / ``Sum``；``SparseTable`` 仅 ``Min`` / ``Max``。

### 并查集 ``DSU``

- ``dsu[x]`` 代表元；``dsu[a] = b`` 合并；``has(a,b)``；``count(x)``；``x in dsu``。

### 字典树 / AC 自动机

| 类 | 要点 |
|----|------|
| ``Trie`` | ``add``、``remove``、``discard``、``clear``、``update(list/Self)``、``word in trie``、``startsWith(prefix) -> int``（前缀计数） |
| ``ACAuto`` | 同左 + ``flush()`` 建 fail；``add/remove/discard(..., flush=)``；``update(list/Self)``；``count(text)`` 含重叠 |

### 堆 / 单调队列

- ``Heap``：``push`` / ``pop`` / ``top`` / ``len`` / ``bool``；
- ``IndexedHeap``：上列 + ``in`` / ``remove`` / ``discard`` / ``clear``（元素唯一；``dict`` 维护下标）；
- ``MonoQueue``：``push`` / ``pop`` / ``min`` 或 ``max``（``isMin`` 构造参数）。

### 序列容器（``ChunkDeque``）

| 能力 | API |
|------|-----|
| 双端队列（竞赛向） | ``append`` / ``appendLeft`` / ``pop()`` 尾弹 / ``popLeft`` |
| rope / piece table | ``splice`` / ``extend`` / ``insert`` / ``pop(index)`` |
| 通用 | ``append`` / ``copy``（``@immutable``）+ ``__iter__`` / ``__reversed__`` + 下标读写 / ``__contains__`` / ``__delitem__`` / ``clear`` |

**非** CPython ``util/deque`` 全套。默认 ``blockSize=512``；块内 ``list[T]`` + ``@boxing`` 块级双向链（``chunk_deque.py`` 单类实现）。

### 测试与写法

- 集成测目录：**``test/alg/``**（``TestCaseMixin`` + ``override def test``）；
- 构造用 ``new(...)``；循环 ``for i in range(n)``；布尔 ``not seq`` / ``if seq``。

---

## 3. 目录与模块

```text
py2cpp/
  alg/
    __init__.py          # 文档索引 + re-export
    dsu.py               # 并查集 Union-Find
    fen_tree.py          # 树状数组 Fenwick / BIT（``FenTree``）
    heap.py              # 二叉堆 / 优先队列
    mono_queue.py        # 单调队列（滑动窗口最值，``MonoQueue``）
    chunk_deque.py       # ChunkDeque（块双向链 + list[T]）✅
    agg_mode.py          # 区间聚合 ``AggModeEnum``（``SegTree`` / ``SparseTable``）
    seg_tree.py          # 线段树（点修 + 区间聚合，``SegTree``）
    sparse_table.py      # 稀疏表（静态 RMQ）
    trie.py              # 字典树（str 前缀）
    ac_auto.py           # AC 自动机（``ACAuto``，多模式匹配）
    protocols.py         # ``NavigatableType[N]`` 寻路协议
    grid2d.py            # ``Grid2D`` / ``WalkGrid`` / ``GridNav`` + ``GridConnectivityEnum``
    graph.py             # ``AdjList`` / ``GraphNav``
    navigate.py          # ``astar`` / ``dijkstra``（仅 ``NavigatableType`` 参数）
    spatial_hash.py      # 均匀网格空间哈希
    quadtree.py          # 四叉树（可选，P4）
  design/
    __init__.py
    ecs.py               # ECS（``ECSEntity`` / ``ECSComponentTable`` / ``ECSWorldMixin``）
```

**译器注册**（实现时同步）：

- `py2cpp/alg/<mod>.py` 新增模块（``src/constant/stdlib_discovery.py`` 遍历自动发现；必要时调整 ``constant/stdlib_modules`` 的 ``UMBRELLA_PREFIX_TIERS`` / ``constant/header_fixups_data`` 的 ``MODULE_HEADER_FIXUPS``）；
- `py2cpp/__init__.py` → 域再导出与 `__all__`（若对外暴露）；
- `src/codegen/umbrella_gen.py` → `minimal.h` include `alg/*.h`（注意顺序，全量 `build_all.bat` 验证）。

---

## 4. 数据结构清单

### 4.1 ACM 核心

| 结构 | 模块 | 典型用途 | 核心 API（草案） |
|------|------|----------|------------------|
| **并查集** | `dsu` | 连通性、Kruskal、离线合并 | ``dsu[x]``、``dsu[a]=b``、``has(a,b)``、``count(x)`` |
| **树状数组** | `fen_tree` | 单点修、前缀和、逆序对 | ``bit[i]``、``bit[l:r]``、``bit[i]=v``、``add`` |
| **二叉堆** | `heap` | Dijkstra、多路归并、事件调度 | `push`, `pop`, `top`, `__len__` |
| **单调队列** | `mono_queue` | 滑动窗口 min/max | `push`, `pop`, `min`/`max` |
| **线段树** | `seg_tree` | 区间最值/和、点修 | `__init__(n, AggModeEnum)`, `st[i]`/`st[l:r]`/`st[i]=v`, `len`/`in` |
| **稀疏表** | `sparse_table` | 静态 RMQ | `__init__(arr, AggModeEnum.Min/Max)`, `st[i]`/`st[l:r]`, `len`/`in` |
| **字典树** | `trie` | 前缀、xor 基 | `add`, `update`, `word in trie`, `startsWith`, `len` |
| **AC 自动机** | `ac_auto` | 多模式子串计数 | `add`, `flush`, `update`, `word in ac`, `count`, `len` |

### 4.2 游戏向

| 结构 | 模块 | 典型用途 | 核心 API（草案） |
|------|------|----------|------------------|
| **二维网格** | `grid2d` | tilemap、BFS、flow field | `width`/`height`, `get`/`set`, 四向 `neighbors` |
| **空间哈希** | `spatial_hash` | 粗碰撞、邻近查询 | `insert(id,x,y)`, `query_cell`, `query_rect` |
| **四叉树** | `quadtree` | 2D 范围选取、LOD 粗筛 | `insert`, `query_range`（P4） |

**不重复实现**：多重集 → `Counter`；对象池 → `Pool`；ECS → `design/ecs`；CPython **`collections.deque`** → **`util/deque`**（侵入式链表，**不迁移、不重命名**）。

### 4.3 序列容器（竞赛 / 编辑向）

| 结构 | 模块 | 典型用途 | 核心 API（草案） | 与现有模块 |
|------|------|----------|------------------|------------|
| **分块双端队列** | `chunk_deque` | 大块两端 append/pop、滑动窗口底层 | `append`/`appendLeft`/`pop`/`popLeft`, `__len__`, `__getitem__`（v1） | **非** `util/deque`；块内连续、块级双端链 |
| **可拼接序列** | `chunk_deque` | 中间 insert/pop、splice/extend、日志/文本缓冲 | `splice`, `extend`, `insert`, `pop`, `__getitem__`/`__setitem__`/`__delitem__`, `__contains__`, `__iter__`, `__reversed__`, `append`, `copy` | **非** `str`；**`ChunkDeque[T]`** |

**命名说明**（避免与 C++ `std::deque` / `util.deque` 混淆）：

| 口语 / 旧称 | 公开类名 | C++ 命名空间（预期） |
|-------------|----------|----------------------|
| 块状 deque、分块队列 | **`ChunkDeque[T]`** | `py2cpp::alg::chunk_deque::ChunkDeque<T>` |
| rope、Piece table | **`ChunkDeque[T]`** | `py2cpp::alg::chunk_deque::ChunkDeque<T>` |

可选别名 **`ChunkString`**：文档别名，表示 ``ChunkDeque`` 用于 ``str``/码点序列缓冲；**不**单独再实现一套 API。

---

## 5. API 形态示例

以下为**规格草图**（非最终实现）；须遵守 [编码规范](./编码规范.md)：`new`、`Self` 静态辅助、`for range`、无手写 dunder（除协议要求）、无 STL。

### 5.1 并查集 `DSU`

```python
class DSU:
  def __init__(self, n: int): ...
  def __contains__(self, x: int) -> bool: ...       # ``0 <= x < n``
  def __getitem__(self, x: int) -> int: ...       # 代表元
  def __setitem__(self, a: int, b: int) -> None: ...  # 合并两集合
  def has(self, a: int, b: int) -> bool: ...
  def count(self, x: int) -> int: ...
  def __len__(self) -> int: ...
  def __bool__(self) -> bool: ...
```

实现要点：路径压缩 + 按秩合并；`parent` / `rank` 用 `array[int]` 或 `int[:n]`。

### 5.2 树状数组 `FenTree`

```python
class FenTree[T: ComplexType]:
  def __init__(self, n: int): ...
  def __getitem__(self, i: int) -> T: ...
  def __getitem__(self, index: slice[int, int]) -> T: ...  # ``[l:r)`` 区间和
  def __setitem__(self, i: int, value: T) -> None: ...
  def add(self, i: int, delta: T) -> None: ...
```

``T`` 须支持 ``+`` / ``-``（``@protocol ComplexType`` 及其实现，如 ``int`` / ``float``）。

### 5.3 堆 `Heap` / `IndexedHeap`

```python
class Heap[T: ComparableType]:
  def __init__(self): ...
  def push(self, x: T) -> None: ...
  def pop(self) -> T: ...
  def top(self) -> T: ...
  def __len__(self) -> int: ...

class IndexedHeap[T: ComparableType & DictKeyType]:
  def push(self, x: T) -> None: ...       # 已存在则忽略（每元素至多一次）
  def pop(self) -> T: ...
  def top(self) -> T: ...
  def remove(self, x: T) -> None: ...    # 缺失 KeyError
  def discard(self, x: T) -> None: ...
  def clear(self) -> None: ...
  def __contains__(self, x: T) -> bool: ...
  def __len__(self) -> int: ...
```

内部：`list[T]` 数组堆（根为 ``_data[0]``）；``IndexedHeap`` 另持 ``dict[T, int]`` 元素下标，交换时同步更新。**不**使用 C++ `priority_queue`。

### 5.4 单调队列 `MonoQueue`

```python
class MonoQueue[T: ComparableType]:
  """滑动窗口最值；队头为当前窗口极值。"""
  def push(self, x: T) -> None: ...
  def pop(self) -> None: ...   # 窗口左端滑出
  def min(self) -> T: ...      # 或 max，构造参数 / 子类区分
```

实现：下标队列 + 外部数组，或基于 **`ChunkDeque`** / `util/deque` 存储下标（实现时择优，须写清文档）。

### 5.5 区间聚合模式 `AggModeEnum`

```python
@enum
class AggModeEnum:
  Min = 0
  Max = ...
  Sum = ...
```

``SegTree`` 支持 ``Min`` / ``Max`` / ``Sum``；``SparseTable`` 仅 ``Min`` / ``Max``。

### 5.6 线段树 `SegTree`（v1）

```python
class SegTree:
  """点修 + 区间聚合；``mode`` 为 ``AggModeEnum``。"""
  def __init__(self, n: int, mode: AggModeEnum): ...
  def __getitem__(self, i: int) -> int: ...
  def __getitem__(self, index: slice[int, int]) -> int: ...  # ``[l:r)`` 区间聚合
  def __setitem__(self, i: int, value: int) -> None: ...
```

下标/切片语义与 ``FenTree`` 一致（半开区间、空切片为聚合单位元）。

**v1 不做**：懒标记、区间赋值、区间加。

### 5.7 稀疏表 `SparseTable`

```python
class SparseTable:
  def __init__(self, data: list[int], mode: AggModeEnum): ...
  def __getitem__(self, i: int) -> int: ...
  def __getitem__(self, index: slice[int, int]) -> int: ...  # ``[l:r)`` 静态 RMQ
```

仅支持**静态**数组构建；无 ``__setitem__``；min/max 由构造 ``mode`` 指定。

### 5.8 字典树 `Trie`

```python
class Trie:
  def add(self, word: str) -> None: ...
  def remove(self, word: str) -> None: ...  # 删一次；缺失 KeyError
  def discard(self, word: str) -> None: ...  # 同 remove，缺失静默
  def clear(self) -> None: ...
  @overload
  def update(self, other: Self) -> None: ...
  @overload
  def update(self, words: list[str]) -> None: ...
  def __contains__(self, word: str) -> bool: ...
  def startsWith(self, prefix: str) -> int: ...
  def __len__(self) -> int: ...
  def __bool__(self) -> bool: ...
```

子节点：`dict[char, int]`（``word[i]`` 作码点键）。

### 5.9 AC 自动机 `ACAuto`

```python
class ACAuto:
  def add(self, word: str, flush: bool = True) -> None: ...
  def remove(self, word: str, flush: bool = True) -> None: ...  # 删一次；缺失 KeyError
  def discard(self, word: str, flush: bool = True) -> None: ...  # 同 remove，缺失静默
  def clear(self) -> None: ...
  def __contains__(self, word: str) -> bool: ...
  def flush(self) -> None: ...
  @overload
  def update(self, other: Self) -> None: ...
  @overload
  def update(self, words: list[str]) -> None: ...
  def count(self, text: str) -> int: ...  # 含重叠；未 flush 时首次 count 自动 flush
  def __len__(self) -> int: ...
  def __bool__(self) -> bool: ...
```

与 ``Trie`` 同构节点池 + ``fail``；**不继承** ``Trie``。重复 ``add`` 同一串计次。

### 5.10 寻路协议 `NavigatableType` + `navigate`

```python
@protocol
class NavigatableType[N: DictKeyType]:
  type Node = N
  def vertexCount(self) -> int: ...
  def toIndex(self, u: Node) -> int: ...
  def fromIndex(self, i: int) -> Node: ...
  def neighbors(self, u: Node) -> list[Node]: ...
  def moveCost(self, u: Node, v: Node) -> int: ...
  def heuristic(self, u: Node, goal: Node) -> int: ...

def astar[Node: DictKeyType](nav: NavigatableType[Node], start: Node, goal: Node) -> list[Node]: ...
def dijkstra[Node: DictKeyType](nav: NavigatableType[Node], start: Node, goal: Node) -> list[Node]: ...
```

``GridNav`` / ``GraphNav`` 满足协议；算法层**只**接收 ``NavigatableType``。

### 5.11 二维网格 `Grid2D` / `GridConnectivityEnum`（游戏）

```python
@enum
class GridConnectivityEnum:
  Four = 0
  Eight = ...

@copyable
@dataclass(eq=True)
class Cell:
  x: int
  y: int

class Grid2D:
  def __init__(self, width: int, height: int, fill: int = 0): ...
  # width / height / get / set / inBounds / fill / copy

class Grid2D:
  # ``0`` 墙，``>= 1`` 边权；``walkable`` / ``getWidth`` / ``getHeight`` / ``get`` / ``set`` / ``fill``

class GridNav:
  def __init__(self, grid: Grid2D, connectivity: GridConnectivityEnum): ...
```

存储：`int[:,:]`（行 ``y``、列 ``x``）。八向边权为进入格代价 × ``14/10``；启发式四向 Manhattan、八向 octile（10/14）。

### 5.12 邻接表 `AdjList` / `GraphNav`

```python
@dataclass
class Edge:
  to: int
  w: int = 1

class AdjList:
  def __init__(self, n: int): ...
  def addEdge(self, u: int, v: int, w: int = 1) -> None: ...
  def addUndirected(self, u: int, v: int, w: int = 1) -> None: ...

class GraphNav:
  def __init__(self, graph: AdjList, h: list[int] | None = None): ...
```

### 5.13 空间哈希 `SpatialHash`

```python
@copyable
class SpatialHash:
  def __init__(self, cell_size: float): ...
  def insert(self, id: int, x: float, y: float) -> None: ...
  def remove(self, id: int) -> None: ...
  def query_cell(self, cx: int, cy: int) -> list[int]: ...
```

桶：`dict` 映射 cell_key → `list[int]`。

### 5.14 分块序列 `ChunkDeque`（已实现）

块状双端队列 + **rope / piece table**（非 CPython `deque`，非 `std::deque`）。**仅导出** ``ChunkDeque[T]``（原 ``ChunkList`` 已合并）。

```python
class ChunkDeque[T]:
  def __init__(self, blockSize: int = 512): ...
  @immutable
  def copy(self) -> Self: ...
  def append(self, x: T) -> None: ...
  def appendLeft(self, x: T) -> None: ...
  @overload
  def pop(self) -> T: ...              # 尾弹，O(1) 摊还
  @overload
  def pop(self, index: int) -> T: ...  # 任意下标；尾/头走快路径
  def popLeft(self) -> T: ...
  def splice(self, pos: int) -> Self: ...   # [0, pos) 留本对象，返回 [pos, end)
  def extend(self, other: Self) -> None: ...
  def insert(self, pos: int, x: T) -> None: ...
  def __iter__(self): ...       # ``ChunkDequeIterator[T]``
  def __reversed__(self): ...   # ``ChunkDequeReverseIterator[T]``
  # __len__ / __bool__ / __getitem__ / __setitem__ / __delitem__ / __contains__ / clear
```

**实现要点（v1）**：块级 ``@boxing`` 双向链 + 块内 ``list[T]``；默认块 **512**。**不做**：``maxLen`` / ``rotate`` 等 CPython ``deque`` 全套。

| 操作 | 复杂度（B = 块数） |
|------|-------------------|
| ``append`` / ``appendLeft`` / ``pop()`` / ``popLeft`` | O(1) 摊还 |
| ``pop(i)``（非头尾） | O(B) 定位 + O(1) 块内 |
| ``splice`` / ``insert`` | v1 块链表；频繁中部编辑最坏 O(n) |
| ``__getitem__`` / ``__delitem__`` | O(B) 定位 |

**导入**：``from py2cpp.alg.chunk_deque import ChunkDeque``（或 ``from py2cpp.alg import ChunkDeque``）。

---

## 6. 实现规范摘要

实现时必须对照 [编码规范](./编码规范.md) 最小自检表：

| 项 | 要求 |
|----|------|
| 范式 | `new`、无手写 dunder（除非协议/运算符）、`@dataclass` 小结构；容器 ``copy()`` + 赋值移动 |
| 复用 | 不手写与 `str`/`dict` 等价的扫描逻辑；整数循环用 `for i in range(n)` |
| 切片/布尔 | `buf[:k]`、`not seq` |
| 静态辅助 | `Self._helper()`（对齐 `StringMixin._normEnd`） |
| 冲突 | Win 宏/译器问题在 `minimal.h` 或译器根因修，不改业务 API |
| Native | 业务 **零 `@native`**；仅叶子可 `@native`（本域预期不需要） |

**类命名**：公开类名采用短 PascalCase（如 `FenTree`、`MonoQueue`、`SegTree`）；模块文件为 snake_case（`fen_tree.py` 等）。C++ 名由 `CPP_RENAME` 映射（若需 `PyHeap` 等）。

---

## 7. 分期实施

### P0 — 域注册 + 冒烟

| 交付 | 说明 |
|------|------|
| `py2cpp/alg/__init__.py` | 空壳或仅文档字符串 |
| `constant/stdlib_discovery` | `py2cpp/alg/*.py` 自动发现 |
| `test/alg/test_alg_smoke.py` | `from py2cpp import *` + 最小构造 |
| 文档 | 本文件 + [编码规范 §10 测试目录表](./编码规范.md) 增 `test/alg/` 行 |

### P0.5 — 序列容器基础（`ChunkDeque`）✅

| 交付 | 说明 |
|------|------|
| `chunk_deque.py` | `ChunkDeque[T]` v1（双端 + splice/extend/insert） |
| `constant/stdlib_discovery` | `py2cpp/alg/chunk_deque.py` 自动发现 |
| `test/alg/test_chunk_deque.py` | 双端 append/pop、splice/extend/insert、下标 |

验证：bootstrap + 单测 MSVC 全绿。**预期无需改译器**（块内用 `list[T]`）。

### P1 — ACM 核心 ✅

| 模块 | 测试文件 |
|------|----------|
| `dsu` | `test_dsu.py` |
| `fen_tree` | `test_fen_tree.py` |
| `heap` | `test_heap.py` |
| `mono_queue` | `test_mono_queue.py` |

验证：`python main.py py2cpp\__init__.py -o generated --no-main` + 上述测试 MSVC 全绿。

### P1b — 可拼接序列（并入 `ChunkDeque`）✅

| 模块 | 测试文件 | 备注 |
|------|----------|------|
| `chunk_deque` | `test_chunk_deque.py` | ``splice``/extend/insert/pop/下标；与 P0.5 同测文件 |

### P2 — ACM 进阶 ✅

| 模块 | 测试文件 | 备注 |
|------|----------|------|
| `seg_tree` | `test_seg_tree.py` | 无懒标记 |
| `sparse_table` | `test_sparse_table.py` | |
| `trie` | `test_trie.py` | 仅 `str` 键 |
| `ac_auto` | `test_ac_auto.py` | 多模式 ``count`` |

### P3 — 游戏向（网格 / 寻路）✅

| 模块 | 测试文件 |
|------|----------|
| `protocols` | （由 `test_navigate` 间接覆盖） |
| `grid2d` | `test_grid2d.py` |
| `graph` | `test_graph.py` |
| `navigate` | `test_navigate.py` |

与 `ecs` **解耦**；不替代组件存储。

### P3b — 游戏向（空间索引，未做）

| 模块 | 测试文件 |
|------|----------|
| `spatial_hash` | `test_spatial_hash.py` |

### P4 — 可选

| 模块 | 说明 |
|------|------|
| `quadtree` | 2D 范围查询；节点 `@boxing` |
| `ChunkDeque` v2 | 块级平衡树；O(log 块数) splice/extend |

---

## 8. 测试与验证

### 8.1 目录

```text
test/alg/
  test_chunk_deque.py
  test_dsu.py
  test_fen_tree.py
  ...
```

结构：[编码规范 §10](./编码规范.md) — `TestCaseMixin` + `override def test` + `main()` 跑 suite。

### 8.2 命令

```bat
REM bootstrap
python main.py py2cpp\__init__.py -o generated --no-main

REM 单测
python main.py test\alg\test_dsu.py -o generated -c --compiler cl --exe generated\test\alg\test_dsu.exe
generated\test\alg\test_dsu.exe

REM 全量
build_all.bat
```

### 8.3 用例设计原则

- 每测例一行注释说明所测 API；
- 边界：`n=0/1`、空堆 pop、并查集自合并；
- 与 CPython 行为**不要求**一致（无对应标准库），以**规格本文**为准。

---

## 9. 文档与导出

### 9.1 实现后须同步

| 文档 | 内容 |
|------|------|
| [参考手册](./参考手册.md) | 新增「alg 标准库」节：模块列表、C++ 命名空间 |
| [编码规范 §8.1](./编码规范.md) | 模块对照表增加 `alg/*` |
| `py2cpp/__init__.py` | `__all__` 导出公开类名 |

### 9.2 建议 `__all__`（P1 后）

```python
__all__ = [
  "DSU",
  "FenTree",
  "Heap",
  "IndexedHeap",
  "MonoQueue",
  "ChunkDeque",
  # P2+
  "AggModeEnum",
  "SegTree",
  "SparseTable",
  "Trie",
  "ACAuto",
  # P3+
  "Grid2D",
  "SpatialHash",
]
```

---

## 10. 风险与依赖

| 风险 | 缓解 |
|------|------|
| `minimal.h` include 顺序 | 新增 `alg` 域后全量 `build_all.bat` |
| 泛型 `ComparableType` / `IntegralType` 约束 | 参考 `dict[K: DictKeyType]`；失败用 `static_assert` |
| 线段树递归深度 | 迭代实现或固定 `4*n` 数组 |
| Trie 节点内存 | 优先 `dict` 子节点；稠密字符集再评估 `@boxing` |
| `ChunkDeque` vs `util/deque` 职责混淆 | 文档与命名强制区分；**禁止**把 `util/deque` 迁入 `alg` |
| `ChunkDeque` splice 频繁 | v1 块链表最坏 O(n)；大 n 编辑场景等 P4 v2 或显式文档限制 |
| 块内定长 `T[:B]`（B 非字面量） | v1 优先 `list[T]`；若改定长栈数组再评估译器 |

**译器改动**：预期 **P0–P1 无需改译器**；若 `array2d` / 特殊下标未就绪，在 P3 前于基础设施层补。

---

## 11. PR 检查清单（实现阶段）

```text
[ ] 行为与本文档一致；分期范围未蔓延
[ ] py2cpp/alg 源树 + constant 发现 + __all__
[ ] test/alg/* 集成测 MSVC 全绿
[ ] 未手改 generated/
[ ] bootstrap: python main.py py2cpp\__init__.py -o generated --no-main
[ ] 编码规范自检（new / Self / 无 STL / range）
[ ] 参考手册 + 编码规范 §8.1 已更新
```

---

## 12. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-02 | 初稿：推荐方案落盘（P0–P4、默认约定、模块清单） |
| 2026-05-19 | 增 §2.5 统一 API 范式；``ChunkSequence``→``ChunkList``；落地 ``ChunkDeque`` / ``ChunkList``；P0.5/P1/P1b/P2 标记完成 |
| 2026-05-19 | 增 §4.3 / §5.12–5.13：`ChunkDeque`、`ChunkList`（rope 语义）；P0.5 / P1b 分期；明确 **`util/deque` 不动** |
| 2026-05-19 | ``alg`` 容器统一移除 ``@copyable``；``dst = src`` 移动、``src.copy()`` 显式副本；新增 ``ContainerMixin``（``util/mixins.py``） |
| 2026-05-19 | ``chunks``→``chunk_deque`` 模块名；``ChunkList`` 并入 ``ChunkDeque``；``split``→``splice``；删除 ``ChunkMixin`` |
| 2026-05-19 | ``ChunkDeque``：删 ``to_list``；增 ``__iter__`` / ``__reversed__``（``ChunkDequeIterator`` 等） |
| 2026-05-19 | ``ACAuto``：``remove`` / ``discard`` 增加 ``flush=``（与 ``add`` 对齐） |
| 2026-05-19 | ``ACAuto``：``update``→``flush``；``add(flush=)``；``update(list/Self)`` 批量并入 |
| 2026-05-19 | ``ACAuto``：Trie 边 ``dict[char, int]``，``word[i]`` 直作码点（无 ``ord``） |
| 2026-05-19 | ``IndexedHeap``（``alg.heap``：堆 + O(1) ``in`` + O(log n) ``remove``/``discard``） |
| 2026-05-19 | ``Trie`` / ``ACAuto``：``discard``（缺失不报错，对齐 ``set.discard``） |
| 2026-05-19 | ``Trie`` / ``ACAuto``：``remove``（单次删除 + 路径剪枝）、``clear`` |
| 2026-05-19 | ``Trie``：``dict[char, int]`` + ``update(list/Self)``（与 ``ACAuto`` 对齐） |
