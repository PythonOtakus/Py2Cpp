"""字典树（``str`` 前缀，``char`` 码点边）。

公开 API（Python 成员语义，对齐 ``alg`` 其它结构）：

| 写法 | 说明 |
|------|------|
| ``trie.add(word)`` | 插入字符串 |
| ``trie.remove(word)`` | 删除一次插入（缺失 ``KeyError``） |
| ``trie.discard(word)`` | 同 ``remove``，缺失不报错 |
| ``trie.clear()`` | 清空 |
| ``trie.update(words)`` / ``trie.update(other)`` | 批量并入（类似 ``set.update``） |
| ``word in trie`` | 是否插入过完整词（``__contains__``） |
| ``trie.startsWith(prefix)`` | 以 ``prefix`` 为前缀的已插入串个数 |
| ``len(trie)`` / ``bool(trie)`` | 已插入串总数（含重复 ``add``） |
"""
from ..builtins import *
from ..core.exceptions import KeyError, ValueError
from ..util.dict import dict
from ..util.list import list
from ..util.mixins import ContainerMixin


class Trie(ContainerMixin):
  """0-based 节点池 + ``dict[char, 子节点]``。"""

  def __init__(self):
    self._next: list[dict[char, int]] = []
    self._pass: list[int] = []
    self._end: list[int] = []
    self._count: int = 0
    self._newNode()

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    nxt: list[dict[char, int]] = []
    pas: list[int] = []
    end: list[int] = []
    self._next = nxt
    self._pass = pas
    self._end = end
    self._count = other._count
    for i in range(len(other._next)):
      child: dict[char, int] = {}
      for k in other._next[i]:
        child[k] = other._next[i][k]
      self._next.append(child)
      self._pass.append(other._pass[i])
      self._end.append(other._end[i])

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._next = other._next
    self._pass = other._pass
    self._end = other._end
    self._count = other._count
    nxt: list[dict[char, int]] = []
    pas: list[int] = []
    end: list[int] = []
    other._next = nxt
    other._pass = pas
    other._end = end
    other._count = 0
    other._newNode()

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = new()
    out.__copy__(self)
    return out

  def _newNode(self) -> int:
    child: dict[char, int] = {}
    self._next.append(child)
    self._pass.append(0)
    self._end.append(0)
    return len(self._next) - 1

  def add(self, word: str) -> None:
    u: int = 0
    for i in range(len(word)):
      self._pass[u] += 1
      c: char = word[i]
      if c not in self._next[u]:
        self._next[u][c] = self._newNode()
      u = self._next[u][c]
    self._pass[u] += 1
    self._end[u] += 1
    self._count += 1

  def remove(self, word: str) -> None:
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
    v: int = 0
    for i in range(len(word)):
      self._pass[v] -= 1
      c2: char = word[i]
      v = self._next[v][c2]
    self._pass[v] -= 1
    self._end[u] -= 1
    self._count -= 1
    cur: int = u
    while len(path) > 1:
      if self._pass[cur] > 0 or self._end[cur] > 0:
        break
      if self._next[cur]:
        break
      parent: int = path[-2]
      idx: int = len(path) - 2
      edge: char = word[idx]
      del self._next[parent][edge]
      path.pop()
      cur = path[-1]

  def discard(self, word: str) -> None:
    if word not in self:
      return
    self.remove(word)

  def clear(self) -> None:
    self._next = []
    self._pass = []
    self._end = []
    self._count = 0
    self._newNode()

  def _mergeFrom(self, src: Self, u: int, prefix: str) -> None:
    if src._end[u] > 0:
      for j in range(src._end[u]):
        self.add(prefix)
    for c in src._next[u]:
      child: str = prefix + c
      self._mergeFrom(src, src._next[u][c], child)

  @overload
  def update(self, other: Self) -> None:
    if other.__moved__:
      raise ValueError("move from moved container")
    self._mergeFrom(other, 0, "")

  @overload
  def update(self, words: list[str]) -> None:
    for i in range(len(words)):
      self.add(words[i])

  @immutable
  def __contains__(self, word: str) -> bool:
    u: int = 0
    for i in range(len(word)):
      c: char = word[i]
      if c not in self._next[u]:
        return False
      u = self._next[u][c]
    return self._end[u] > 0

  @immutable
  def startsWith(self, prefix: str) -> int:
    u: int = 0
    for i in range(len(prefix)):
      c: char = prefix[i]
      if c not in self._next[u]:
        return 0
      u = self._next[u][c]
    return self._pass[u]

  @immutable
  def __len__(self) -> int:
    return self._count

  @immutable
  def __bool__(self) -> bool:
    return self._count > 0
