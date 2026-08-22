"""deque[Element]：双端队列，对齐 Python 3.13 ``collections.deque``（双向侵入式链表）。"""
from ..builtins import *
from ..core.exceptions import IndexError, StopIteration, ValueError
from .mixins import ContainerMixin


@boxing
class DequeNodeUnsafe[Element]:
  def __init__(self, value: Element, nextNode: Self, prevNode: Self):
    self.value: Element = value
    self.next: Self = nextNode
    self.prev: Self = prevNode


class DequeIterator[Element]:
  _index: int = 0

  def __init__(self, dq: deque[Element]):
    self._dq: deque[Element] = dq

  def __iter__(self):
    return self

  def __next__(self) -> Element:
    if self._index >= len(self._dq):
      raise StopIteration
    value: Element = self._dq[self._index]
    self._index += 1
    return value


class DequeReverseIterator[Element]:
  def __init__(self, dq: deque[Element]):
    self._dq: deque[Element] = dq
    self._index: int = len(dq) - 1

  def __iter__(self):
    return self

  def __next__(self) -> Element:
    if self._index < 0:
      raise StopIteration
    value: Element = self._dq[self._index]
    self._index -= 1
    return value


class deque[Element](ContainerMixin):

  _NoMaxLen: int @const = int.Min
  _head: DequeNodeUnsafe[Element] = None
  _tail: DequeNodeUnsafe[Element] = None
  _length: int = 0

  __repr__ = __str__

  def __init__(self, maxLen: int = Self._NoMaxLen):
    self._maxLen: int = maxLen

  def __del__(self):
    self._clearNodes()

  def __copy__(self, other: Self):
    """深拷贝节点链（避免默认成员拷贝共享 ``_head``/``_tail``）。

    复制构造时成员未初始化，须先 ``_resetEmpty`` 再 ``extend``。
    """
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    if self._length > 0:
      self._clearNodes()
    else:
      self._resetEmpty()
    self._maxLen = other._maxLen
    self.extend(other)

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    if self._length > 0:
      self._clearNodes()
    else:
      self._resetEmpty()
    self._head = other._head
    self._tail = other._tail
    self._length = other._length
    self._maxLen = other._maxLen
    other._resetEmpty()

  @immutable
  def __str__(self) -> str:
    if self._length == 0:
      return "deque([])"
    out: str = "deque(["
    cur: DequeNodeUnsafe[Element] = self._head
    i: int = 0
    while cur is not None:
      if i > 0:
        out += ", "
      out += repr(cur.value)
      cur = cur.next
      i += 1
    return out + "])"

  @immutable
  def __format__(self, formatSpec: str) -> str:
    return str(self)

  def __bool__(self) -> bool:
    return self._length > 0

  @immutable
  def __len__(self) -> int:
    return self._length

  @immutable
  def __getitem__(self, index: int) -> Element:
    index = self._normIndex(index)
    if index < 0 or index >= self._length:
      raise IndexError("deque index out of range")
    cur: DequeNodeUnsafe[Element] = self._head
    for _ in range(index):
      cur = cur.next
    return cur.value

  def __setitem__(self, index: int, value: Element):
    index = self._normIndex(index)
    if index < 0 or index >= self._length:
      raise IndexError("deque index out of range")
    cur: DequeNodeUnsafe[Element] = self._head
    for _ in range(index):
      cur = cur.next
    cur.value = value

  @immutable
  def __contains__(self, item: Element) -> bool:
    cur: DequeNodeUnsafe[Element] = self._head
    while cur is not None:
      if cur.value == item:
        return True
      cur = cur.next
    return False

  def __iter__(self) -> DequeIterator[Element]:
    return new(self)

  def __reversed__(self) -> DequeReverseIterator[Element]:
    return new(self)

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = []
    out.extend(self)
    out.extend(other)
    return out

  def __iadd__(self, other: Self) -> Self:
    self.extend(other)
    return self

  @immutable
  def __mul__(self, n: int) -> Self:
    if n <= 0:
      return []
    out: Self = []
    for _ in range(n):
      out.extend(self)
    return out

  @immutable
  def __rmul__(self, n: int) -> Self:
    if n <= 0:
      return []
    out: Self = []
    for _ in range(n):
      out.extend(self)
    return out

  def __imul__(self, n: int) -> Self:
    if n <= 0:
      self.clear()
      return self
    if n == 1:
      return self
    snap: Self = self.copy()
    for _ in range(1, n):
      self.extend(snap)
    return self

  def append(self, item: Element):
    self._ensureActive()
    node = DequeNodeUnsafe[Element](item, None, self._tail)
    if self._head is None:
      self._head = node
      self._tail = node
    else:
      self._tail.next = node
      self._tail = node
    self._length += 1
    self._trimRightIfOverMaxlen()

  def appendLeft(self, item: Element):
    node = DequeNodeUnsafe[Element](item, self._head, None)
    if self._head is not None:
      self._head.prev = node
    self._head = node
    if self._tail is None:
      self._tail = node
    self._length += 1
    self._trimLeftIfOverMaxlen()

  def clear(self):
    self._clearNodes()

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = new(self._maxLen)
    out.extend(self)
    return out

  @immutable
  def count(self, value: Element) -> int:
    n: int = 0
    cur: DequeNodeUnsafe[Element] = self._head
    while cur is not None:
      if cur.value == value:
        n += 1
      cur = cur.next
    return n

  def extend(self, other: Self):
    cur: DequeNodeUnsafe[Element] = other._head
    while cur is not None:
      self.append(cur.value)
      cur = cur.next

  def extendLeft(self, other: Self):
    cur: DequeNodeUnsafe[Element] = other._head
    while cur is not None:
      self.appendLeft(cur.value)
      cur = cur.next

  @immutable
  def index(self, value: Element, start: int = 0, end: int = int.Max) -> int:
    start = self._normStart(start)
    stop: int = self._normStop(end)
    cur: DequeNodeUnsafe[Element] = self._head
    j: int = 0
    while cur is not None and j < stop:
      if j >= start and cur.value == value:
        return j
      cur = cur.next
      j += 1
    raise ValueError("deque.index(x): x not in deque")

  def insert(self, index: int, item: Element):
    if self._maxLen >= 0 and self._length >= self._maxLen:
      raise IndexError("deque already at its maximum size")
    index = self._normIndex(index)
    if index < 0:
      index = 0
    if index > self._length:
      index = self._length
    if index == 0:
      self.appendLeft(item)
      return
    if index == self._length:
      self.append(item)
      return
    cur: DequeNodeUnsafe[Element] = self._head
    for _ in range(index):
      cur = cur.next
    node = DequeNodeUnsafe[Element](item, cur, cur.prev)
    if cur.prev is not None:
      cur.prev.next = node
    else:
      self._head = node
    cur.prev = node
    self._length += 1

  def pop(self) -> Element:
    if self._length == 0:
      raise IndexError("pop from an empty deque")
    value: Element = self._tail.value
    self._unlink(self._tail)
    return value

  def popLeft(self) -> Element:
    if self._length == 0:
      raise IndexError("pop from an empty deque")
    value: Element = self._head.value
    self._unlink(self._head)
    return value

  def remove(self, value: Element):
    cur: DequeNodeUnsafe[Element] = self._head
    while cur is not None:
      if cur.value == value:
        self._unlink(cur)
        return
      cur = cur.next
    raise ValueError("deque.remove(x): x not in deque")

  def reverse(self):
    cur: DequeNodeUnsafe[Element] = self._head
    while cur is not None:
      nxt: DequeNodeUnsafe[Element] = cur.next
      cur.next = cur.prev
      cur.prev = nxt
      cur = nxt
    oldHead: DequeNodeUnsafe[Element] = self._head
    self._head = self._tail
    self._tail = oldHead

  def rotate(self, n: int = 1):
    if self._length <= 1:
      return
    k: int = n % self._length
    if k < 0:
      k = self._length + k
    for _ in range(k):
      self.appendLeft(self.pop())

  @immutable
  def maxLen(self) -> int:
    """未限长时返回 ``Self._NoMaxLen``（对应 Python ``None``）。"""
    return self._maxLen

  def _clearNodes(self):
    cur: DequeNodeUnsafe[Element] = self._head
    while cur is not None:
      nxt: DequeNodeUnsafe[Element] = cur.next
      destroy(cur)
      free(cur)
      cur = nxt
    self._head = None
    self._tail = None
    self._length = 0

  @immutable
  def _normIndex(self, index: int) -> int:
    if index < 0:
      index = self._length + index
    return index

  @immutable
  def _normStart(self, start: int) -> int:
    if start < 0:
      start = self._length + start
    if start < 0:
      start = 0
    return start

  @immutable
  def _normStop(self, end: int) -> int:
    if end == int.Max:
      return self._length
    if end < 0:
      end = self._length + end
    if end > self._length:
      end = self._length
    if end < 0:
      end = 0
    return end

  def _resetEmpty(self):
    self._head = None
    self._tail = None
    self._length = 0

  def _trimLeftIfOverMaxlen(self):
    while self._maxLen >= 0 and self._length > self._maxLen:
      self.pop()

  def _trimRightIfOverMaxlen(self):
    while self._maxLen >= 0 and self._length > self._maxLen:
      self.popLeft()

  def _unlink(self, node: DequeNodeUnsafe[Element]):
    if node.prev is not None:
      node.prev.next = node.next
    else:
      self._head = node.next
    if node.next is not None:
      node.next.prev = node.prev
    else:
      self._tail = node.prev
    destroy(node)
    free(node)
    self._length -= 1
