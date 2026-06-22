"""``arena``：解码期临时 ``char`` 分配（``json.loads`` 热路径）。

``acquire`` 返回独立 ``allocRawArray`` 缓冲；``adopt_span`` 后须 ``release``，
否则 ``reset`` 会释放。``reserve`` 为容量提示（当前无操作，保留 API）。
"""
from ..builtins import *
from .list import list


@copyable
@native_name("PyArena")
class arena:
  """单次 ``loads`` 作用域内的 ``char`` 堆缓冲池。"""

  def __init__(self):
    self._owned: list[Pointer[char]] = []

  def __del__(self):
    self.reset()

  def reset(self) -> None:
    """释放未 ``release`` 的缓冲。"""
    n: int = len(self._owned)
    for i in range(n):
      freeArray(self._owned[i])
    self._owned = []

  def reserve(self, n: int) -> None:
    """预留提示（占位；``acquire`` 仍独立 ``allocRawArray``）。"""
    if n <= 0:
      return

  def acquire(self, n: int) -> Pointer[char]:
    """分配 ``n`` 个 ``char`` 槽；adopt 前由 ``reset`` 回收。"""
    if n <= 0:
      return None
    p: Pointer[char] = allocRawArray[char](n)
    self._owned.append(p)
    return p

  def release(self, p: Pointer[char]) -> None:
    """``PyStr.adopt_span`` 后从 ``reset`` 列表移除。"""
    if p is None:
      return
    n: int = len(self._owned)
    for i in range(n):
      if self._owned[i] == p:
        last: int = n - 1
        if i < last:
          self._owned[i] = self._owned[last]
        self._owned.pop()
        return
