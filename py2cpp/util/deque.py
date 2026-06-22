"""deque[Element]：双端队列，对齐 Python 3.13 ``collections.deque``（双向侵入式链表）。"""
from ..builtins import *
from ..core.exceptions import IndexError, StopIteration, ValueError


@boxing
@native_name("PyDequeNode")
class deque_node[Element]:
  def __init__(self, value: Element, next_node: Self, prev_node: Self):
    self.value: Element = value
    self.next: Self = next_node
    self.prev: Self = prev_node


@native_name("PyDequeIterator")
class deque_iterator[Element]:
  def __init__(self, dq: deque[Element]):
    self._dq: deque[Element] = dq
    self._index: int = 0

  def __iter__(self):
    return self

  def __next__(self) -> Element:
    if self._index >= len(self._dq):
      raise StopIteration
    value: Element = self._dq[self._index]
    self._index += 1
    return value


@native_name("PyDequeReverseIterator")
class deque_reverse_iterator[Element]:
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


@native_name("PyDeque")
class deque[Element]:
  _DEQUE_END: int @const = int.Min

  _UNBOUNDED_MAXLEN: int @const = int.Min

  __repr__ = __str__

  def __init__(self, maxlen: int = Self._UNBOUNDED_MAXLEN):
    self.head: deque_node[Element] = None
    self.tail: deque_node[Element] = None
    self._length: int = 0
    self._maxlen: int = maxlen

  def __del__(self):
    self._clear_nodes()

  def __copy__(self, other: Self):
    """深拷贝节点链（避免默认成员拷贝共享 ``head``/``tail``）。

    复制构造时成员未初始化，须先 ``_reset_empty`` 再 ``extend``。
    """
    self._ensure_active()
    self._ensure_other_active(other)
    if self._length > 0:
      self._clear_nodes()
    else:
      self._reset_empty()
    self._maxlen = other._maxlen
    self.extend(other)

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    if self._length > 0:
      self._clear_nodes()
    else:
      self._reset_empty()
    self.head = other.head
    self.tail = other.tail
    self._length = other._length
    self._maxlen = other._maxlen
    other._reset_empty()

  @immutable
  def __str__(self) -> str:
    if self._length == 0:
      return "deque([])"
    out: str = "deque(["
    cur: deque_node[Element] = self.head
    i: int = 0
    while cur is not None:
      if i > 0:
        out += ", "
      out += repr(cur.value)
      cur = cur.next
      i += 1
    return out + "])"

  @immutable
  def __format__(self, format_spec: str) -> str:
    return str(self)

  def __bool__(self) -> bool:
    return self._length > 0

  @immutable
  def __len__(self) -> int:
    return self._length

  @immutable
  def __getitem__(self, index: int) -> Element:
    index = self._norm_index(index)
    if index < 0 or index >= self._length:
      raise IndexError("deque index out of range")
    cur: deque_node[Element] = self.head
    for _ in range(index):
      cur = cur.next
    return cur.value

  def __setitem__(self, index: int, value: Element):
    index = self._norm_index(index)
    if index < 0 or index >= self._length:
      raise IndexError("deque index out of range")
    cur: deque_node[Element] = self.head
    for _ in range(index):
      cur = cur.next
    cur.value = value

  @immutable
  def __contains__(self, item: Element) -> bool:
    cur: deque_node[Element] = self.head
    while cur is not None:
      if cur.value == item:
        return True
      cur = cur.next
    return False

  def __iter__(self) -> deque_iterator[Element]:
    return new(self)

  def __reversed__(self) -> deque_reverse_iterator[Element]:
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
    self._ensure_active()
    node = deque_node[Element](item, None, self.tail)
    if self.head is None:
      self.head = node
      self.tail = node
    else:
      self.tail.next = node
      self.tail = node
    self._length += 1
    self._trim_right_if_over_maxlen()

  def appendleft(self, item: Element):
    node = deque_node[Element](item, self.head, None)
    if self.head is not None:
      self.head.prev = node
    self.head = node
    if self.tail is None:
      self.tail = node
    self._length += 1
    self._trim_left_if_over_maxlen()

  def clear(self):
    self._clear_nodes()

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new(self._maxlen)
    out.extend(self)
    return out

  @immutable
  def count(self, value: Element) -> int:
    n: int = 0
    cur: deque_node[Element] = self.head
    while cur is not None:
      if cur.value == value:
        n += 1
      cur = cur.next
    return n

  def extend(self, other: Self):
    cur: deque_node[Element] = other.head
    while cur is not None:
      self.append(cur.value)
      cur = cur.next

  def extendleft(self, other: Self):
    cur: deque_node[Element] = other.head
    while cur is not None:
      self.appendleft(cur.value)
      cur = cur.next

  @immutable
  def index(self, value: Element, start: int = 0, end: int = Self._DEQUE_END) -> int:
    start = self._norm_start(start)
    stop: int = self._norm_stop(end)
    cur: deque_node[Element] = self.head
    j: int = 0
    while cur is not None and j < stop:
      if j >= start and cur.value == value:
        return j
      cur = cur.next
      j += 1
    raise ValueError("deque.index(x): x not in deque")

  def insert(self, index: int, item: Element):
    if self._maxlen >= 0 and self._length >= self._maxlen:
      raise IndexError("deque already at its maximum size")
    index = self._norm_index(index)
    if index < 0:
      index = 0
    if index > self._length:
      index = self._length
    if index == 0:
      self.appendleft(item)
      return
    if index == self._length:
      self.append(item)
      return
    cur: deque_node[Element] = self.head
    for _ in range(index):
      cur = cur.next
    node = deque_node[Element](item, cur, cur.prev)
    if cur.prev is not None:
      cur.prev.next = node
    else:
      self.head = node
    cur.prev = node
    self._length += 1

  def pop(self) -> Element:
    if self._length == 0:
      raise IndexError("pop from an empty deque")
    value: Element = self.tail.value
    self._unlink(self.tail)
    return value

  def popleft(self) -> Element:
    if self._length == 0:
      raise IndexError("pop from an empty deque")
    value: Element = self.head.value
    self._unlink(self.head)
    return value

  def remove(self, value: Element):
    cur: deque_node[Element] = self.head
    while cur is not None:
      if cur.value == value:
        self._unlink(cur)
        return
      cur = cur.next
    raise ValueError("deque.remove(x): x not in deque")

  def reverse(self):
    cur: deque_node[Element] = self.head
    while cur is not None:
      nxt: deque_node[Element] = cur.next
      cur.next = cur.prev
      cur.prev = nxt
      cur = nxt
    old_head: deque_node[Element] = self.head
    self.head = self.tail
    self.tail = old_head

  def rotate(self, n: int = 1):
    if self._length <= 1:
      return
    k: int = n % self._length
    if k < 0:
      k = self._length + k
    for _ in range(k):
      self.appendleft(self.pop())

  @immutable
  def maxlen(self) -> int:
    """未限长时返回 ``Self._UNBOUNDED_MAXLEN``（对应 Python ``None``）。"""
    return self._maxlen

  def _clear_nodes(self):
    cur: deque_node[Element] = self.head
    while cur is not None:
      nxt: deque_node[Element] = cur.next
      destroy(cur)
      free(cur)
      cur = nxt
    self.head = None
    self.tail = None
    self._length = 0

  @immutable
  def _ensure_active(self) -> None:
    if self.__moved__:
      raise ValueError("deque used after move")

  @immutable
  def _ensure_other_active(self, other: Self) -> None:
    if other.__moved__:
      raise ValueError("move from moved deque")

  @immutable
  def _norm_index(self, index: int) -> int:
    if index < 0:
      index = self._length + index
    return index

  @immutable
  def _norm_start(self, start: int) -> int:
    if start < 0:
      start = self._length + start
    if start < 0:
      start = 0
    return start

  @immutable
  def _norm_stop(self, end: int) -> int:
    if end == Self._DEQUE_END:
      return self._length
    if end < 0:
      end = self._length + end
    if end > self._length:
      end = self._length
    if end < 0:
      end = 0
    return end

  def _reset_empty(self):
    self.head = None
    self.tail = None
    self._length = 0

  def _trim_left_if_over_maxlen(self):
    while self._maxlen >= 0 and self._length > self._maxlen:
      self.pop()

  def _trim_right_if_over_maxlen(self):
    while self._maxlen >= 0 and self._length > self._maxlen:
      self.popleft()

  def _unlink(self, node: deque_node[Element]):
    if node.prev is not None:
      node.prev.next = node.next
    else:
      self.head = node.next
    if node.next is not None:
      node.next.prev = node.prev
    else:
      self.tail = node.prev
    destroy(node)
    free(node)
    self._length -= 1
