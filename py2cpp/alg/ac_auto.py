"""Aho–Corasick 自动机（多模式 ``str`` 匹配，``char`` 码点边）。

公开 API（对齐 ``alg`` 其它结构）：

| 写法 | 说明 |
|------|------|
| ``ac.add(word)`` / ``add(word, flush=False)`` | 插入模式串（可重复，计次）；默认 ``flush=True`` 立即建 ``fail`` |
| ``ac.remove(word)`` / ``remove(word, flush=False)`` | 删除一次模式（缺失 ``KeyError``）；默认 ``flush=True`` |
| ``ac.discard(word)`` / ``discard(word, flush=False)`` | 同 ``remove``，缺失不报错 |
| ``ac.clear()`` | 清空 |
| ``word in ac`` | 是否曾 ``add`` 过该完整模式（``__contains__``，走 Trie 边） |
| ``ac.flush()`` | BFS 建 ``fail`` 链（批量 ``add`` 后须 ``flush``） |
| ``ac.update(words)`` / ``ac.update(other)`` | 批量并入模式（类似 ``set.update``；末尾统一 ``flush``） |
| ``ac.count(text)`` | 文本中匹配总次数（含重叠；未 ``flush`` 时 ``count`` 自动 ``flush``） |
| ``len(ac)`` / ``bool(ac)`` | 已 ``add`` 的模式串总数 |
"""
from ..builtins import *
from ..core.exceptions import KeyError
from ..util.dict import dict
from ..util.list import list
from ..util.mixins import ContainerMixin


class ACAuto(ContainerMixin):
  """Trie 图 + ``fail`` 链；独立实现，不继承 ``Trie``。"""

  def __init__(self):
    self._next: list[dict[char, int]] = []
    self._end: list[int] = []
    self._fail: list[int] = []
    self._count: int = 0
    self._flushed: bool = False
    self._new_node()

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    nxt: list[dict[char, int]] = []
    end: list[int] = []
    fail: list[int] = []
    self._next = nxt
    self._end = end
    self._fail = fail
    self._count = other._count
    self._flushed = other._flushed
    for i in range(len(other._next)):
      child: dict[char, int] = {}
      for k in other._next[i]:
        child[k] = other._next[i][k]
      self._next.append(child)
      self._end.append(other._end[i])
      self._fail.append(other._fail[i])

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    self._next = other._next
    self._end = other._end
    self._fail = other._fail
    self._count = other._count
    self._flushed = other._flushed
    nxt: list[dict[char, int]] = []
    end: list[int] = []
    fail: list[int] = []
    other._next = nxt
    other._end = end
    other._fail = fail
    other._count = 0
    other._flushed = False
    other._new_node()

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new()
    out.__copy__(self)
    return out

  def _new_node(self) -> int:
    child: dict[char, int] = {}
    self._next.append(child)
    self._end.append(0)
    self._fail.append(0)
    return len(self._next) - 1

  def add(self, word: str, flush: bool = True) -> None:
    u: int = 0
    for i in range(len(word)):
      c: char = word[i]
      if c not in self._next[u]:
        self._next[u][c] = self._new_node()
      u = self._next[u][c]
    self._end[u] += 1
    self._count += 1
    self._flushed = False
    if flush:
      self.flush()

  def remove(self, word: str, flush: bool = True) -> None:
    u: int = 0
    path: list[int] = []
    path.append(u)
    for i in range(len(word)):
      c: char = word[i]
      if c not in self._next[u]:
        raise KeyError("remove")
      u = self._next[u][c]
      path.append(u)
    if self._end[u] == 0:
      raise KeyError("remove")
    self._end[u] -= 1
    self._count -= 1
    self._flushed = False
    cur: int = u
    while len(path) > 1:
      if self._end[cur] > 0:
        break
      if self._next[cur]:
        break
      parent: int = path[-2]
      idx: int = len(path) - 2
      edge: char = word[idx]
      del self._next[parent][edge]
      path.pop()
      cur = path[-1]
    if flush:
      self.flush()

  def discard(self, word: str, flush: bool = True) -> None:
    if word not in self:
      return
    self.remove(word, flush)

  def clear(self) -> None:
    self._next = []
    self._end = []
    self._fail = []
    self._count = 0
    self._flushed = True
    self._new_node()

  def _merge_from(self, src: Self, u: int, prefix: str) -> None:
    if src._end[u] > 0:
      for j in range(src._end[u]):
        self.add(prefix, False)
    for c in src._next[u]:
      child: str = prefix + c
      self._merge_from(src, src._next[u][c], child)

  @overload
  def update(self, other: Self) -> None:
    self._ensure_other_active(other)
    self._merge_from(other, 0, "")
    self.flush()

  @overload
  def update(self, words: list[str]) -> None:
    for i in range(len(words)):
      self.add(words[i], False)
    self.flush()

  @immutable
  def __contains__(self, word: str) -> bool:
    u: int = 0
    for i in range(len(word)):
      c: char = word[i]
      if c not in self._next[u]:
        return False
      u = self._next[u][c]
    return self._end[u] > 0

  def flush(self) -> None:
    if self._flushed:
      return
    n: int = len(self._next)
    for i in range(n):
      self._fail[i] = 0
    q: list[int] = []
    for c in self._next[0]:
      v: int = self._next[0][c]
      self._fail[v] = 0
      q.append(v)
    head: int = 0
    while head < len(q):
      u: int = q[head]
      head += 1
      for c in self._next[u]:
        v: int = self._next[u][c]
        f: int = self._fail[u]
        while f != 0 and c not in self._next[f]:
          f = self._fail[f]
        if c in self._next[f]:
          self._fail[v] = self._next[f][c]
        else:
          self._fail[v] = 0
        q.append(v)
    self._flushed = True

  def _ensure_flushed(self) -> None:
    if not self._flushed:
      self.flush()

  def count(self, text: str) -> int:
    self._ensure_flushed()
    u: int = 0
    total: int = 0
    for i in range(len(text)):
      c: char = text[i]
      while u != 0 and c not in self._next[u]:
        u = self._fail[u]
      if c in self._next[u]:
        u = self._next[u][c]
      v: int = u
      while v != 0:
        total += self._end[v]
        v = self._fail[v]
    return total

  @immutable
  def __len__(self) -> int:
    return self._count

  @immutable
  def __bool__(self) -> bool:
    return self._count > 0
