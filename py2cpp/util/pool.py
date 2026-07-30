"""``Pool[T]``：多段块对象池（贴近 ``std::hive`` 块复用；非 CPython 标准库）。

``_block_bufs`` 块表 + 栈定长 ``_free_top`` / ``_free_data``（每块 LIFO 空闲下标，无 ``PyList``）
+ ``_use_mark``（在用槽标记）+ ``_meta_*`` / ``_skip_hi``（``_skip_hi_append`` 增量维护）。
扩容仅 ``allocArray`` 追加块。``capacity`` 为属性（写代替 ``reserve``）。

``block_capacity`` ≤ ``Self._BLOCK_CAP``；块数 ≤ ``Self._BLOCK_COUNT``。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from .list import list


class pool_slot_loc:
  """块下标 + 块内偏移（避免元组解包被译成重复求值）。"""

  def __init__(self, block_index: int = 0, offset: int = 0):
    self.block_index: int = block_index
    self.offset: int = offset


@uncopyable
@native_name("PyPool")
class Pool[T]:
  """``block_capacity`` 为每块槽数（≤ ``Self._BLOCK_CAP``）。"""

  _BLOCK_CAP: int @const = 64
  _BLOCK_COUNT: int @const = 32
  _FREE_DATA_LEN: int @const = 2048
  _SLOT_CAP: int @const = 2048

  def __init__(self, block_capacity: int = Self._BLOCK_CAP):
    if block_capacity < 1:
      raise ValueError("Pool block_capacity must be >= 1")
    if block_capacity > Self._BLOCK_CAP:
      raise ValueError("Pool block_capacity exceeds Self._BLOCK_CAP")
    self._block_capacity: int = block_capacity
    self._block_bufs: list[Pointer[T]] = []
    self._free_top: int[:_BLOCK_COUNT] = new()
    self._free_data: int[:_FREE_DATA_LEN] = new()
    self._meta_block_index: list[int] = []
    self._meta_base: list[Pointer[T]] = []
    self._meta_capacity: list[int] = []
    self._skip_hi: list[int] = []
    self._use_mark: int[:_FREE_DATA_LEN] = new()
    self._live: int = 0

  def __del__(self):
    self.clear()

  def __move__(self, other: Self):
    self.clear()
    self._block_capacity = other._block_capacity
    self._block_bufs = other._block_bufs
    self._free_top = other._free_top
    self._free_data = other._free_data
    self._meta_block_index = other._meta_block_index
    self._meta_base = other._meta_base
    self._meta_capacity = other._meta_capacity
    self._skip_hi = other._skip_hi
    self._use_mark = other._use_mark
    self._live = other._live
    other._block_capacity = Self._BLOCK_CAP
    other._block_bufs = []
    other._meta_block_index = []
    other._meta_base = []
    other._meta_capacity = []
    other._skip_hi = []
    other._live = 0

  @immutable
  def __len__(self) -> int:
    return self._live

  @immutable
  def __bool__(self) -> bool:
    return self._live > 0

  @property
  @immutable
  def capacity(self) -> int:
    return len(self._block_bufs) * self._block_capacity

  @property.setter
  def capacity(self, need: int) -> None:
    if need < 0:
      raise ValueError("Pool.capacity must be >= 0")
    cur: int = len(self._block_bufs) * self._block_capacity
    while cur < need:
      self._add_block()
      cur = len(self._block_bufs) * self._block_capacity

  def acquire(self) -> Pointer[T]:
    loc: pool_slot_loc = self._pop_free_slot()
    if loc.block_index < 0:
      self._add_block()
      loc = self._pop_free_slot()
      if loc.block_index < 0:
        raise ValueError("Pool.acquire: no free slot")
    b: int = loc.block_index
    self._use_mark[self._free_base(b) + loc.offset] = 1
    self._live += 1
    return self._slot_ptr(b, loc.offset)

  def release(self, ptr: Pointer[T]) -> None:
    loc: pool_slot_loc = self._locate_ptr(ptr)
    if loc.block_index < 0:
      raise ValueError("Pool.release: pointer not from this pool")
    destroy(ptr)
    b: int = loc.block_index
    self._use_mark[self._free_base(b) + loc.offset] = 0
    top: int = self._free_top[b]
    if top >= self._block_capacity:
      raise ValueError("Pool.release: free stack overflow")
    base: int = self._free_base(b)
    self._free_data[base + top] = loc.offset
    self._free_top[b] = top + 1
    self._live -= 1

  def clear(self):
    cap: int = self._block_capacity
    if self._live > 0:
      for bi in range(len(self._block_bufs)):
        base: Pointer[T] = self._block_bufs[bi]
        mark_base: int = self._free_base(bi)
        for off in range(cap):
          mi: int = mark_base + off
          if self._use_mark[mi]:
            destroy(base + off)
            self._use_mark[mi] = 0
    for bi in range(len(self._block_bufs)):
      freeArray(self._block_bufs[bi])
      self._free_top[bi] = 0
    self._block_bufs.clear()
    self._meta_block_index.clear()
    self._meta_base.clear()
    self._meta_capacity.clear()
    self._skip_hi.clear()
    self._live = 0

  def _add_block(self):
    n_blocks: int = len(self._block_bufs)
    if n_blocks >= Self._BLOCK_COUNT:
      raise ValueError("Pool: too many blocks (max Self._BLOCK_COUNT)")
    cap: int = self._block_capacity
    base: Pointer[T] = allocArray[T](cap)
    self._block_bufs.append(base)
    for o in range(cap):
      destroy(base + o)
    self._init_free_stack(n_blocks, cap)
    self._meta_insert(n_blocks, base, cap)

  @immutable
  def _free_base(self, block_index: int) -> int:
    return block_index * Self._BLOCK_CAP

  def _init_free_stack(self, block_index: int, cap: int):
    base: int = self._free_base(block_index)
    top: int = cap
    for o in range(cap):
      self._free_data[base + o] = o
    self._free_top[block_index] = top

  @immutable
  def _locate_ptr(self, ptr: Pointer[T]) -> pool_slot_loc:
    n_meta: int = len(self._meta_base)
    if n_meta == 0:
      miss: pool_slot_loc = new(-1, -1)
      return miss
    if n_meta == 1:
      if ptr < self._meta_base[0]:
        miss: pool_slot_loc = new(-1, -1)
        return miss
      if ptr >= self._meta_base[0] + self._meta_capacity[0]:
        miss: pool_slot_loc = new(-1, -1)
        return miss
      hit: pool_slot_loc = new(
        self._meta_block_index[0], ptr - self._meta_base[0]
      )
      return hit
    lo_lane: int = 0
    hi_lane: int = len(self._skip_hi)
    start_meta: int = 0
    while lo_lane < hi_lane:
      mid_lane: int = (lo_lane + hi_lane) // 2
      m_idx: int = self._skip_hi[mid_lane]
      if ptr < self._meta_base[m_idx]:
        hi_lane = mid_lane
      else:
        lo_lane = mid_lane + 1
        start_meta = m_idx
    lo: int = start_meta
    hi: int = n_meta
    while lo < hi:
      mid: int = (lo + hi) // 2
      if ptr < self._meta_base[mid]:
        hi = mid
      elif ptr >= self._meta_base[mid] + self._meta_capacity[mid]:
        lo = mid + 1
      else:
        hit: pool_slot_loc = new(
          self._meta_block_index[mid], ptr - self._meta_base[mid]
        )
        return hit
    miss: pool_slot_loc = new(-1, -1)
    return miss

  def _meta_insert(self, block_index: int, base: Pointer[T], capacity: int):
    pos: int = self._meta_insert_pos(base)
    self._meta_block_index.insert(pos, block_index)
    self._meta_base.insert(pos, base)
    self._meta_capacity.insert(pos, capacity)
    self._skip_hi_append(pos)

  @immutable
  def _meta_insert_pos(self, base: Pointer[T]) -> int:
    n: int = len(self._meta_base)
    lo: int = 0
    hi: int = n
    while lo < hi:
      mid: int = (lo + hi) // 2
      if base < self._meta_base[mid]:
        hi = mid
      else:
        lo = mid + 1
    return lo

  def _pop_free_slot(self) -> pool_slot_loc:
    for b in range(len(self._block_bufs) - 1, -1, -1):
      top: int = self._free_top[b]
      if top > 0:
        top -= 1
        base: int = self._free_base(b)
        offset: int = self._free_data[base + top]
        self._free_top[b] = top
        return new(b, offset)
    return new(-1, -1)

  def _skip_hi_append(self, pos: int):
    """新块 ``base`` 单调递增，插入恒在尾部；仅偶数下标进入跳表。"""
    if pos % 2 == 0:
      self._skip_hi.append(pos)

  @immutable
  def _slot_ptr(self, block_index: int, offset: int) -> Pointer[T]:
    return self._block_bufs[block_index] + offset
