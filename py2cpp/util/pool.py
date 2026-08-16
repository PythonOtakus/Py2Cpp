"""``Pool[T]``：多段块对象池（贴近 ``std::hive`` 块复用；非 CPython 标准库）。

``_blockBufs`` 块表 + 栈定长 ``_freeTop`` / ``_freeData``（每块 LIFO 空闲下标，无 ``PyList``）
+ ``_useMark``（在用槽标记）+ ``_meta_*`` / ``_skipHi``（``_skipHiAppend`` 增量维护）。
扩容仅 ``allocArray`` 追加块。``capacity`` 为属性（写代替 ``reserve``）。

``blockCapacity`` ≤ ``Self._BlockCap``；块数 ≤ ``Self._BlockCount``。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from .list import list


class PoolSlotLoc:
  """块下标 + 块内偏移（避免元组解包被译成重复求值）。"""

  def __init__(self, blockIndex: int = 0, offset: int = 0):
    self.blockIndex: int = blockIndex
    self.offset: int = offset


@uncopyable
class Pool[Element]:
  """``blockCapacity`` 为每块槽数（≤ ``Self._BlockCap``）。"""

  _BlockCap: int @const = 64
  _BlockCount: int @const = 32
  _FreeDataLen: int @const = 2048
  _SlotCap: int @const = 2048

  def __init__(self, blockCapacity: int = Self._BlockCap):
    if blockCapacity < 1:
      raise ValueError("Pool blockCapacity must be >= 1")
    if blockCapacity > Self._BlockCap:
      raise ValueError("Pool blockCapacity exceeds Self._BlockCap")
    self._blockCapacity: int = blockCapacity
    self._blockBufs: list[Pointer[Element]] = []
    self._freeTop: int[:_BlockCount] = new()
    self._freeData: int[:_FreeDataLen] = new()
    self._metaBlockIndex: list[int] = []
    self._metaBase: list[Pointer[Element]] = []
    self._metaCapacity: list[int] = []
    self._skipHi: list[int] = []
    self._useMark: int[:_FreeDataLen] = new()
    self._live: int = 0

  def __del__(self):
    self.clear()

  def __move__(self, other: Self):
    self.clear()
    self._blockCapacity = other._blockCapacity
    self._blockBufs = other._blockBufs
    self._freeTop = other._freeTop
    self._freeData = other._freeData
    self._metaBlockIndex = other._metaBlockIndex
    self._metaBase = other._metaBase
    self._metaCapacity = other._metaCapacity
    self._skipHi = other._skipHi
    self._useMark = other._useMark
    self._live = other._live
    other._blockCapacity = Self._BlockCap
    other._blockBufs = []
    other._metaBlockIndex = []
    other._metaBase = []
    other._metaCapacity = []
    other._skipHi = []
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
    return len(self._blockBufs) * self._blockCapacity

  @property.setter
  def capacity(self, need: int) -> None:
    if need < 0:
      raise ValueError("Pool.capacity must be >= 0")
    cur: int = len(self._blockBufs) * self._blockCapacity
    while cur < need:
      self._addBlock()
      cur = len(self._blockBufs) * self._blockCapacity

  def acquire(self) -> Pointer[Element]:
    loc: PoolSlotLoc = self._popFreeSlot()
    if loc.blockIndex < 0:
      self._addBlock()
      loc = self._popFreeSlot()
      if loc.blockIndex < 0:
        raise ValueError("Pool.acquire: no free slot")
    b: int = loc.blockIndex
    self._useMark[self._freeBase(b) + loc.offset] = 1
    self._live += 1
    return self._slotPtr(b, loc.offset)

  def release(self, ptr: Pointer[Element]) -> None:
    loc: PoolSlotLoc = self._locatePtr(ptr)
    if loc.blockIndex < 0:
      raise ValueError("Pool.release: pointer not from this pool")
    destroy(ptr)
    b: int = loc.blockIndex
    self._useMark[self._freeBase(b) + loc.offset] = 0
    top: int = self._freeTop[b]
    if top >= self._blockCapacity:
      raise ValueError("Pool.release: free stack overflow")
    base: int = self._freeBase(b)
    self._freeData[base + top] = loc.offset
    self._freeTop[b] = top + 1
    self._live -= 1

  def clear(self):
    cap: int = self._blockCapacity
    if self._live > 0:
      for bi in range(len(self._blockBufs)):
        base: Pointer[Element] = self._blockBufs[bi]
        markBase: int = self._freeBase(bi)
        for off in range(cap):
          mi: int = markBase + off
          if self._useMark[mi]:
            destroy(base + off)
            self._useMark[mi] = 0
    for bi in range(len(self._blockBufs)):
      freeArray(self._blockBufs[bi])
      self._freeTop[bi] = 0
    self._blockBufs.clear()
    self._metaBlockIndex.clear()
    self._metaBase.clear()
    self._metaCapacity.clear()
    self._skipHi.clear()
    self._live = 0

  def _addBlock(self):
    nBlocks: int = len(self._blockBufs)
    if nBlocks >= Self._BlockCount:
      raise ValueError("Pool: too many blocks (max Self._BlockCount)")
    cap: int = self._blockCapacity
    base: Pointer[Element] = allocArray[Element](cap)
    self._blockBufs.append(base)
    for o in range(cap):
      destroy(base + o)
    self._initFreeStack(nBlocks, cap)
    self._metaInsert(nBlocks, base, cap)

  @immutable
  def _freeBase(self, blockIndex: int) -> int:
    return blockIndex * Self._BlockCap

  def _initFreeStack(self, blockIndex: int, cap: int):
    base: int = self._freeBase(blockIndex)
    top: int = cap
    for o in range(cap):
      self._freeData[base + o] = o
    self._freeTop[blockIndex] = top

  @immutable
  def _locatePtr(self, ptr: Pointer[Element]) -> PoolSlotLoc:
    nMeta: int = len(self._metaBase)
    if nMeta == 0:
      miss: PoolSlotLoc = new(-1, -1)
      return miss
    if nMeta == 1:
      if ptr < self._metaBase[0]:
        miss: PoolSlotLoc = new(-1, -1)
        return miss
      if ptr >= self._metaBase[0] + self._metaCapacity[0]:
        miss: PoolSlotLoc = new(-1, -1)
        return miss
      hit: PoolSlotLoc = new(
        self._metaBlockIndex[0], ptr - self._metaBase[0]
      )
      return hit
    loLane: int = 0
    hiLane: int = len(self._skipHi)
    startMeta: int = 0
    while loLane < hiLane:
      midLane: int = (loLane + hiLane) // 2
      mIdx: int = self._skipHi[midLane]
      if ptr < self._metaBase[mIdx]:
        hiLane = midLane
      else:
        loLane = midLane + 1
        startMeta = mIdx
    lo: int = startMeta
    hi: int = nMeta
    while lo < hi:
      mid: int = (lo + hi) // 2
      if ptr < self._metaBase[mid]:
        hi = mid
      elif ptr >= self._metaBase[mid] + self._metaCapacity[mid]:
        lo = mid + 1
      else:
        hit: PoolSlotLoc = new(
          self._metaBlockIndex[mid], ptr - self._metaBase[mid]
        )
        return hit
    miss: PoolSlotLoc = new(-1, -1)
    return miss

  def _metaInsert(self, blockIndex: int, base: Pointer[Element], capacity: int):
    pos: int = self._metaInsertPos(base)
    self._metaBlockIndex.insert(pos, blockIndex)
    self._metaBase.insert(pos, base)
    self._metaCapacity.insert(pos, capacity)
    self._skipHiAppend(pos)

  @immutable
  def _metaInsertPos(self, base: Pointer[Element]) -> int:
    n: int = len(self._metaBase)
    lo: int = 0
    hi: int = n
    while lo < hi:
      mid: int = (lo + hi) // 2
      if base < self._metaBase[mid]:
        hi = mid
      else:
        lo = mid + 1
    return lo

  def _popFreeSlot(self) -> PoolSlotLoc:
    for b in range(len(self._blockBufs) - 1, -1, -1):
      top: int = self._freeTop[b]
      if top > 0:
        top -= 1
        base: int = self._freeBase(b)
        offset: int = self._freeData[base + top]
        self._freeTop[b] = top
        return new(b, offset)
    return new(-1, -1)

  def _skipHiAppend(self, pos: int):
    """新块 ``base`` 单调递增，插入恒在尾部；仅偶数下标进入跳表。"""
    if pos % 2 == 0:
      self._skipHi.append(pos)

  @immutable
  def _slotPtr(self, blockIndex: int, offset: int) -> Pointer[Element]:
    return self._blockBufs[blockIndex] + offset
