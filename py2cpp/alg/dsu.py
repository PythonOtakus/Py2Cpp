"""并查集（Union-Find / DSU）。

公开 API（Python 下标/成员语义，**非** STL）：

| 写法 | 说明 |
|------|------|
| ``x in dsu`` | 顶点下标 ``0 .. n-1`` 是否合法（``__contains__``） |
| ``dsu[x]`` | 代表元（路径压缩，``__getitem__``） |
| ``dsu[a] = b`` | 合并 ``a`` 与 ``b`` 所在集合（``__setitem__``） |
| ``dsu.has(a, b)`` | 是否同一集合 |
| ``dsu.count(x)`` | ``x`` 所在连通块大小 |
| ``len(dsu)`` / ``bool(dsu)`` | 顶点个数 ``n``、是否非空（``n > 0``） |
"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from ..util.mixins import ContainerMixin


class DSU(ContainerMixin):
  """Disjoint Set Union；顶点编号 ``0 .. n-1``。"""

  def __init__(self, n: int):
    if n < 0:
      raise ValueError("n must be non-negative")
    self._n: int = n
    self._parent: int[:] = new(n)
    self._rank: int[:] = new(n)
    self._size: int[:] = new(n)
    for i in range(n):
      self._parent[i] = i
      self._rank[i] = 0
      self._size[i] = 1

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    self._n = other._n
    if other._n == 0:
      self._parent = new(0)
      self._rank = new(0)
      self._size = new(0)
      return
    self._parent = new(other._n)
    self._rank = new(other._n)
    self._size = new(other._n)
    for i in range(other._n):
      self._parent[i] = other._parent[i]
      self._rank[i] = other._rank[i]
      self._size[i] = other._size[i]

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    self._n = other._n
    self._parent = other._parent
    self._rank = other._rank
    self._size = other._size
    other._n = 0
    other._parent = new(0)
    other._rank = new(0)
    other._size = new(0)

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new(0)
    out.__copy__(self)
    return out

  @immutable
  def __len__(self) -> int:
    return self._n

  @immutable
  def __bool__(self) -> bool:
    return self._n > 0

  @immutable
  def __contains__(self, x: int) -> bool:
    return 0 <= x < self._n

  @immutable
  def _check(self, x: int) -> None:
    if x not in self:
      raise IndexError("dsu index out of range")

  def _find_root(self, x: int) -> int:
    p: int = self._parent[x]
    if p != x:
      self._parent[x] = self._find_root(p)
    return self._parent[x]

  def __getitem__(self, x: int) -> int:
    self._check(x)
    return self._find_root(x)

  def __setitem__(self, a: int, b: int) -> None:
    self._check(a)
    self._check(b)
    ra: int = self[a]
    rb: int = self[b]
    if ra == rb:
      return
    if self._rank[ra] < self._rank[rb]:
      ra, rb = rb, ra
    self._parent[rb] = ra
    self._size[ra] += self._size[rb]
    if self._rank[ra] == self._rank[rb]:
      self._rank[ra] += 1

  def has(self, a: int, b: int) -> bool:
    return self[a] == self[b]

  def count(self, x: int) -> int:
    self._check(x)
    root: int = self._find_root(x)
    return self._size[root]
