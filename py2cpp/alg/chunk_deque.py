"""分块序列容器：``ChunkDeque``（双端队列 + rope / piece table 语义）。

块级 ``@boxing`` 双向链表 + 块内 ``list[Element]``。默认块大小 512。非 ``util/deque``。
"""
from ..builtins import *
from ..core.exceptions import IndexError, StopIteration, ValueError
from ..util.list import list
from .container_mixin import AlgContainerMixin


@boxing
class _ChunkNode[Element]:
  def __init__(self):
    self.data: list[Element] = []
    self.prev: Self = None
    self.next: Self = None


class ChunkDequeIterator[Element]:
  def __init__(self, dq: ChunkDeque[Element]):
    self._dq: ChunkDeque[Element] = dq
    self._index: int = 0

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


class ChunkDeque[Element](AlgContainerMixin):
  """分块双端队列；``splice`` / ``extend`` / ``insert`` 提供可拼接序列（rope）语义。"""

  DEFAULT_BLOCK_SIZE: int @const = 512

  def __init__(self, block_size: int = 512):
    if block_size <= 0:
      raise ValueError("block_size must be positive")
    self._block_size: int = block_size
    self._head: _ChunkNode[Element] = None
    self._tail: _ChunkNode[Element] = None
    self._len: int = 0

  def __del__(self):
    self.clear()

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    self.clear()
    self._block_size = other._block_size
    cur: _ChunkNode[Element] = other._head
    while cur is not None:
      for j in range(len(cur.data)):
        self.append(cur.data[j])
      cur = cur.next

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new(self._block_size)
    out.__copy__(self)
    return out

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    if self._len > 0:
      self.clear()
    else:
      self._head = None
      self._tail = None
      self._len = 0
    self._block_size = other._block_size
    self._head = other._head
    self._tail = other._tail
    self._len = other._len
    other._head = None
    other._tail = None
    other._len = 0

  def append(self, x: Element) -> None:
    if self._tail is not None and len(self._tail.data) < self._block_size:
      self._tail.data.append(x)
    else:
      node: _ChunkNode[Element] = new()
      node.data.append(x)
      if self._tail is not None:
        self._tail.next = node
        node.prev = self._tail
        self._tail = node
      else:
        self._head = node
        self._tail = node
    self._len += 1

  def appendleft(self, x: Element) -> None:
    if self._head is not None and len(self._head.data) < self._block_size:
      self._head.data.insert(0, x)
    else:
      node: _ChunkNode[Element] = new()
      node.data.append(x)
      if self._head is not None:
        node.next = self._head
        self._head.prev = node
        self._head = node
      else:
        self._head = node
        self._tail = node
    self._len += 1

  def clear(self) -> None:
    cur: _ChunkNode[Element] = self._head
    while cur is not None:
      nxt: _ChunkNode[Element] = cur.next
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
    node: _ChunkNode[Element] = self._head
    while node is not None:
      n: int = len(node.data)
      if remain < n:
        return node.data[remain]
      remain -= n
      node = node.next
    raise IndexError("index out of range")

  def __iter__(self) -> ChunkDequeIterator[Element]:
    return new(self)

  def __reversed__(self) -> ChunkDequeReverseIterator[Element]:
    return new(self)

  @immutable
  def __contains__(self, item: Element) -> bool:
    cur: _ChunkNode[Element] = self._head
    while cur is not None:
      for j in range(len(cur.data)):
        if cur.data[j] == item:
          return True
      cur = cur.next
    return False

  def __delitem__(self, index: int) -> None:
    if index < 0:
      index = self._len + index
    if index < 0 or index >= self._len:
      raise IndexError("assignment index out of range")
    remain: int = index
    node: _ChunkNode[Element] = self._head
    off: int = 0
    while node is not None:
      n: int = len(node.data)
      if remain < n:
        off = remain
        break
      remain -= n
      node = node.next
    node.data.pop(off)
    if not node.data:
      self._unlink_node(node)
    self._len -= 1

  def __setitem__(self, i: int, value: Element) -> None:
    if i < 0 or i >= self._len:
      raise IndexError("index out of range")
    remain: int = i
    node: _ChunkNode[Element] = self._head
    while node is not None:
      n: int = len(node.data)
      if remain < n:
        node.data[remain] = value
        return
      remain -= n
      node = node.next
    raise IndexError("index out of range")

  def _unlink_node(self, node: _ChunkNode[Element]) -> None:
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

  def splice(self, splice_pos: int) -> Self:
    """``[0, splice_pos)`` 留本对象，返回 ``[splice_pos, end)`` 新序列。"""
    if splice_pos < 0 or splice_pos > self._len:
      raise IndexError("splice position out of range")
    right: Self = new(self._block_size)
    if splice_pos == self._len:
      return right
    if splice_pos == 0:
      right._head = self._head
      right._tail = self._tail
      right._len = self._len
      self._head = None
      self._tail = None
      self._len = 0
      return right
    remain: int = splice_pos
    node: _ChunkNode[Element] = self._head
    off: int = 0
    while node is not None:
      n: int = len(node.data)
      if remain < n:
        off = remain
        break
      remain -= n
      node = node.next
    if off == 0:
      right._head = node
      right._tail = self._tail
      right._len = self._len - splice_pos
      if node.prev is not None:
        node.prev.next = None
        self._tail = node.prev
      else:
        self._head = None
        self._tail = None
      node.prev = None
      self._len = splice_pos
      return right
    tail_data: list[Element] = []
    for j in range(off, len(node.data)):
      tail_data.append(node.data[j])
    while len(node.data) > off:
      node.data.pop()
    new_node: _ChunkNode[Element] = new()
    new_node.data = tail_data
    new_node.next = node.next
    if node.next is not None:
      node.next.prev = new_node
      right._tail = self._tail
    else:
      right._tail = new_node
    node.next = None
    self._tail = node
    new_node.prev = None
    right._head = new_node
    right._len = self._len - splice_pos
    self._len = splice_pos
    return right

  def extend(self, other: Self) -> None:
    """尾部拼接 ``other`` 的元素（拷贝）；调用方应 ``other.clear()`` 释放原块。"""
    cur: _ChunkNode[Element] = other._head
    while cur is not None:
      for j in range(len(cur.data)):
        self.append(cur.data[j])
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

  @overload
  def pop(self) -> Element:
    if not self:
      raise IndexError("pop from empty ChunkDeque")
    value: Element = self._tail.data.pop()
    if not self._tail.data:
      self._unlink_node(self._tail)
    self._len -= 1
    return value

  @overload
  def pop(self, index: int) -> Element:
    if not self:
      raise IndexError("pop from empty ChunkDeque")
    if index < 0:
      index = self._len + index
    if index < 0 or index >= self._len:
      raise IndexError("pop index out of range")
    if index == self._len - 1:
      return self.pop()
    if index == 0:
      return self.popleft()
    value: Element = self[index]
    del self[index]
    return value

  def popleft(self) -> Element:
    if not self:
      raise IndexError("pop from empty ChunkDeque")
    value: Element = self._head.data.pop(0)
    if not self._head.data:
      self._unlink_node(self._head)
    self._len -= 1
    return value
