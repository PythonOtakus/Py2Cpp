"""容器分配器：``Allocator[T, StackLength]`` 内嵌 SSO/堆存储；``StackLength=0`` 为纯堆（默认）。

``array[T, StackLength]`` 内嵌 ``_alloc: Allocator[T, StackLength]``；``StackLength>0`` 时 ``len≤StackLength`` 用 ``T[:StackLength]``。
"""
from __future__ import annotations

from ..builtins import *


class Allocator[T, StackLength: int = 0]:
  """内嵌分配器：``_ptr`` 持有活跃指针；``StackLength>0`` 时 ``T[:StackLength]`` 作 SSO。"""

  _stack: T[:StackLength]
  _heap: bool = False
  _ptr: Pointer[T] = None

  @immutable
  def is_heap(self) -> bool:
    if StackLength <= 0:
      return self._ptr is not None
    return self._heap

  @immutable
  def ptr(self) -> Pointer[T]:
    return self._ptr

  @immutable
  def stack_buf(self) -> Pointer[T]:
    return self._stack.buf

  def clear_state(self) -> None:
    self._ptr = None
    self._heap = False

  def release(self, old_count: int) -> None:
    if self._ptr is None:
      return
    for i in range(old_count):
      destroy(self._ptr + i)
    if self._heap or StackLength <= 0:
      freeArray(self._ptr)
    self.clear_state()

  def bind_inline(self) -> None:
    self._ptr = self._stack.buf
    self._heap = False

  def allocate(self, size: int) -> Pointer[T]:
    if size <= 0:
      self.clear_state()
      return None
    if StackLength > 0 and size <= StackLength:
      self._ptr = self._stack.buf
      self._heap = False
      for i in range(size):
        init(self._ptr + i, T())
      return self._ptr
    self._ptr = allocRawArray[T](size)
    self._heap = True
    for i in range(size):
      init(self._ptr + i, T())
    return self._ptr

  def copy_from_ptr(self, src: Pointer[T], n: int, active: int) -> None:
    if n <= 0 or src is None:
      self.clear_state()
      return
    copy_n: int = n
    if active >= 0 and active < copy_n:
      copy_n = active
    if StackLength > 0 and n <= StackLength:
      self._ptr = self._stack.buf
      self._heap = False
      for i in range(copy_n):
        init(self._ptr + i, src[i])
    else:
      self._ptr = allocRawArray[T](n)
      self._heap = True
      for i in range(copy_n):
        init(self._ptr + i, src[i])

  def steal_heap(self, p: Pointer[T]) -> None:
    self._ptr = p
    self._heap = True

  def reset_after_move(self) -> None:
    self.clear_state()

  def move_from_inline(self, other: Self, n: int) -> Pointer[T]:
    other_sso: Pointer[T] = other.stack_buf()
    if StackLength > 0 and n <= StackLength:
      self._ptr = self._stack.buf
      self._heap = False
    else:
      self._ptr = allocRawArray[T](n)
      self._heap = True
    for i in range(n):
      init(self._ptr + i, other_sso[i])
      destroy(other_sso + i)
    other.reset_after_move()
    return self._ptr

  def reallocate(
    self,
    new_size: int,
    active: int,
    old_size: int,
    old_buf: Pointer[T],
    copy_n: int,
  ) -> Pointer[T]:
    was_heap: bool = self.is_heap()
    if new_size <= 0:
      if old_buf is not None:
        for j in range(copy_n, old_size):
          if j < active:
            destroy(old_buf + j)
        for i in range(copy_n):
          destroy(old_buf + i)
        if was_heap or StackLength <= 0:
          freeArray(old_buf)
      self.clear_state()
      return None
    if StackLength > 0 and new_size <= StackLength:
      new_buf: Pointer[T] = self._stack.buf
      for i in range(copy_n):
        if old_buf is not None:
          init(new_buf + i, old_buf[i])
      if old_buf is not None:
        for j in range(copy_n, old_size):
          if j < active:
            destroy(old_buf + j)
        for i in range(copy_n):
          destroy(old_buf + i)
        if was_heap:
          freeArray(old_buf)
      self.bind_inline()
      return new_buf
    new_buf: Pointer[T] = allocRawArray[T](new_size)
    for i in range(copy_n):
      if old_buf is not None:
        init(new_buf + i, old_buf[i])
    if old_buf is not None:
      for j in range(copy_n, old_size):
        if j < active:
          destroy(old_buf + j)
      for i in range(copy_n):
        destroy(old_buf + i)
      if was_heap or StackLength <= 0:
        freeArray(old_buf)
    self.steal_heap(new_buf)
    return new_buf
