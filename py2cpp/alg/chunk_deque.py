"""分块序列容器：``ChunkDeque``（双端队列 + rope / piece table 语义）。

块级 ``@boxing`` 双向链表 + 块内 ``list[Element]``。默认块大小 512。非 ``util/deque``。
"""
from ..builtins import *
from ..core.exceptions import IndexError, StopIteration, ValueError
from ..util.list import list
from ..util.mixins import ContainerMixin


@boxing
class _ChunkNodeUnsafe[Element](friends=(ChunkDeque,)):
  prev: Self = None
  next: Self = None

  def __init__(self):
    self._data: list[Element] = []


class ChunkDequeIterator[Element]:
  _index: int = 0

  def __init__(self, dq: ChunkDeque[Element]):
    self._dq: ChunkDeque[Element] = dq

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> Element:
    if self._index >= len(self._dq):
      raise StopIteration
    value: Element = self._dq[self._index]
    self._index += 1
    return value


class ChunkDequeReverseIterator[Element]:
  def __init__(self, dq: ChunkDeque[Element]):
    self._dq: ChunkDeque[Element] = dq
    self._index: int = len(dq) - 1

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> Element:
    if self._index < 0:
      raise StopIteration
    value: Element = self._dq[self._index]
    self._index -= 1
    return value


class ChunkDeque[Element](ContainerMixin):
  """分块双端队列；``splice`` / ``extend`` / ``insert`` 提供可拼接序列（rope）语义。"""

  DefaultBlockSize: int @const = 512
  _blockSize: int = DefaultBlockSize
  _head: _ChunkNodeUnsafe[Element] = None
  _tail: _ChunkNodeUnsafe[Element] = None
  _len: int = 0

  def __init__(self, blockSize: int = 512):
    if blockSize <= 0:
      raise ValueError("blockSize must be positive")
    self._blockSize: int = blockSize

  def __del__(self):
    self.clear()

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self.clear()
    self._blockSize = other._blockSize
    cur: _ChunkNodeUnsafe[Element] = other._head
    while cur is not None:
      for j in range(len(cur._data)):
        self.append(cur._data[j])
      cur = cur.next

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = new(self._blockSize)
    out.__copy__(self)
    return out

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    if self._len > 0:
      self.clear()
    else:
      self._head = None
      self._tail = None
      self._len = 0
    self._blockSize = other._blockSize
    self._head = other._head
    self._tail = other._tail
    self._len = other._len
    other._head = None
    other._tail = None
    other._len = 0

  def append(self, x: Element) -> None:
    if self._tail is not None and len(self._tail._data) < self._blockSize:
      self._tail._data.append(x)
    else:
      node: _ChunkNodeUnsafe[Element] = new()
      node._data.append(x)
      if self._tail is not None:
        self._tail.next = node
        node.prev = self._tail
        self._tail = node
      else:
        self._head = node
        self._tail = node
    self._len += 1

  def appendLeft(self, x: Element) -> None:
    if self._head is not None and len(self._head._data) < self._blockSize:
      self._head._data.insert(0, x)
    else:
      node: _ChunkNodeUnsafe[Element] = new()
      node._data.append(x)
      if self._head is not None:
        node.next = self._head
        self._head.prev = node
        self._head = node
      else:
        self._head = node
        self._tail = node
    self._len += 1

  def clear(self) -> None:
    cur: _ChunkNodeUnsafe[Element] = self._head
    while cur is not None:
      nxt: _ChunkNodeUnsafe[Element] = cur.next
      destroy(cur)
      free(cur)
      cur = nxt
    self._head = None
    self._tail = None
    self._len = 0

  @immutable
  def __len__(self) -> int:
    return self._len

  @immutable
  def __bool__(self) -> bool:
    return self._len > 0

  @immutable
  def __getitem__(self, i: int) -> Element:
    if i < 0 or i >= self._len:
      raise IndexError("index out of range")
    remain: int = i
    node: _ChunkNodeUnsafe[Element] = self._head
    while node is not None:
      n: int = len(node._data)
      if remain < n:
        return node._data[remain]
      remain -= n
      node = node.next
    raise IndexError("index out of range")

  def __iter__(self) -> ChunkDequeIterator[Element]:
    return new(self)

  def __reversed__(self) -> ChunkDequeReverseIterator[Element]:
    return new(self)

  @immutable
  def __contains__(self, item: Element) -> bool:
    cur: _ChunkNodeUnsafe[Element] = self._head
    while cur is not None:
      for j in range(len(cur._data)):
        if cur._data[j] == item:
          return True
      cur = cur.next
    return False

  def __delitem__(self, index: int) -> None:
    if index < 0:
      index = self._len + index
    if index < 0 or index >= self._len:
      raise IndexError("assignment index out of range")
    remain: int = index
    node: _ChunkNodeUnsafe[Element] = self._head
    off: int = 0
    while node is not None:
      n: int = len(node._data)
      if remain < n:
        off = remain
        break
      remain -= n
      node = node.next
    node._data.pop(off)
    if not node._data:
      self._unlinkNode(node)
    self._len -= 1

  def __setitem__(self, i: int, value: Element) -> None:
    if i < 0 or i >= self._len:
      raise IndexError("index out of range")
    remain: int = i
    node: _ChunkNodeUnsafe[Element] = self._head
    while node is not None:
      n: int = len(node._data)
      if remain < n:
        node._data[remain] = value
        return
      remain -= n
      node = node.next
    raise IndexError("index out of range")

  def _unlinkNode(self, node: _ChunkNodeUnsafe[Element]) -> None:
    if node.prev is not None:
      node.prev.next = node.next
    else:
      self._head = node.next
    if node.next is not None:
      node.next.prev = node.prev
    else:
      self._tail = node.prev
    node.prev = None
    node.next = None
    destroy(node)
    free(node)

  def splice(self, splicePos: int) -> Self:
    """``[0, splicePos)`` 留本对象，返回 ``[splicePos, end)`` 新序列。"""
    if splicePos < 0 or splicePos > self._len:
      raise IndexError("splice position out of range")
    right: Self = new(self._blockSize)
    if splicePos == self._len:
      return right
    if splicePos == 0:
      right._head = self._head
      right._tail = self._tail
      right._len = self._len
      self._head = None
      self._tail = None
      self._len = 0
      return right
    remain: int = splicePos
    node: _ChunkNodeUnsafe[Element] = self._head
    off: int = 0
    while node is not None:
      n: int = len(node._data)
      if remain < n:
        off = remain
        break
      remain -= n
      node = node.next
    if off == 0:
      right._head = node
      right._tail = self._tail
      right._len = self._len - splicePos
      if node.prev is not None:
        node.prev.next = None
        self._tail = node.prev
      else:
        self._head = None
        self._tail = None
      node.prev = None
      self._len = splicePos
      return right
    tailData: list[Element] = []
    for j in range(off, len(node._data)):
      tailData.append(node._data[j])
    while len(node._data) > off:
      node._data.pop()
    newNode: _ChunkNodeUnsafe[Element] = new()
    newNode._data = tailData
    newNode.next = node.next
    if node.next is not None:
      node.next.prev = newNode
      right._tail = self._tail
    else:
      right._tail = newNode
    node.next = None
    self._tail = node
    newNode.prev = None
    right._head = newNode
    right._len = self._len - splicePos
    self._len = splicePos
    return right

  def extend(self, other: Self) -> None:
    """尾部拼接 ``other`` 的元素（拷贝）；调用方应 ``other.clear()`` 释放原块。"""
    cur: _ChunkNodeUnsafe[Element] = other._head
    while cur is not None:
      for j in range(len(cur._data)):
        self.append(cur._data[j])
      cur = cur.next

  def insert(self, pos: int, x: Element) -> None:
    if pos < 0 or pos > self._len:
      raise IndexError("insert position out of range")
    if pos == self._len:
      self.append(x)
      return
    right: Self = self.splice(pos)
    self.append(x)
    self.extend(right)
    right.clear()

  def pop(self, index: int = -1) -> Element:
    if not self:
      raise IndexError("pop from empty ChunkDeque")
    if index < 0:
      index = self._len + index
    if index < 0 or index >= self._len:
      raise IndexError("pop index out of range")
    if index == self._len - 1:
      value: Element = self._tail._data.pop()
      if not self._tail._data:
        self._unlinkNode(self._tail)
      self._len -= 1
      return value
    if index == 0:
      return self.popLeft()
    value: Element = self[index]
    del self[index]
    return value

  def popLeft(self) -> Element:
    if not self:
      raise IndexError("pop from empty ChunkDeque")
    value: Element = self._head._data.pop(0)
    if not self._head._data:
      self._unlinkNode(self._head)
    self._len -= 1
    return value
