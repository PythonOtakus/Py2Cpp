"""``range`` / ``RangeIterator``：对齐 CPython 3.13 不可变整数序列。"""
from ..builtins import *
from ..core.exceptions import IndexError, StopIteration, ValueError


class RangeIterator:
  def __init__(self, start: int, stop: int, step: int):
    self._current: int = start
    self._stop: int = stop
    self._step: int = step

  def __iter__(self):
    return self

  def __next__(self) -> int:
    if self._step > 0:
      if self._current >= self._stop:
        raise StopIteration
    else:
      if self._current <= self._stop:
        raise StopIteration
    value: int = self._current
    self._current += self._step
    return value

  @immutable
  def __length_hint__(self) -> int:
    if self._step > 0:
      if self._current >= self._stop:
        return 0
      n: int = self._stop - self._current
      return (n + self._step - 1) // self._step
    if self._current <= self._stop:
      return 0
    n = self._current - self._stop
    return (n - self._step - 1) // (-self._step)


class range(
  friends=(RangeIterator,),
):
  @overload
  def __init__(self, stop: int):
    self._start: int = 0
    self._stop: int = stop
    self._step: int = 1

  @overload
  def __init__(self, start: int, stop: int, step: int = 1):
    if step == 0:
      raise ValueError("range() arg 3 must not be zero")
    self._start: int = start
    self._stop: int = stop
    self._step: int = step

  @property
  @immutable
  def start(self) -> int:
    return self._start

  @property
  @immutable
  def stop(self) -> int:
    return self._stop

  @property
  @immutable
  def step(self) -> int:
    return self._step

  @immutable
  def __len__(self) -> int:
    if self._step > 0:
      n: int = self._stop - self._start
      if n <= 0:
        return 0
      return (n + self._step - 1) // self._step
    n = self._start - self._stop
    if n <= 0:
      return 0
    return (n - self._step - 1) // (-self._step)

  @immutable
  def __bool__(self) -> bool:
    return len(self) != 0

  @immutable
  def __contains__(self, value: int) -> bool:
    if self._step > 0:
      if value < self._start or value >= self._stop:
        return False
    else:
      if value > self._start or value <= self._stop:
        return False
    diff: int = value - self._start
    if self._step > 0:
      return diff % self._step == 0
    return (-diff) % (-self._step) == 0

  @immutable
  def __getitem__(self, index: int) -> int:
    n: int = len(self)
    if index < 0:
      index += n
    if index < 0 or index >= n:
      raise IndexError("range object index out of range")
    return self._start + index * self._step

  @immutable
  def count(self, value: int) -> int:
    if value in self:
      return 1
    return 0

  @immutable
  def index(self, value: int) -> int:
    if value not in self:
      raise ValueError(f"{value} is not in range")
    return (value - self._start) // self._step

  @immutable
  def __eq__(self, other: Self) -> bool:
    n: int = len(self)
    if n != len(other):
      return False
    if n == 0:
      return True
    return self._start == other.start and self._step == other.step

  @immutable
  def __reversed__(self) -> RangeIterator:
    n: int = len(self)
    if n == 0:
      return new(self._start, self._start, self._step)
    last: int = self._start + (n - 1) * self._step
    return new(last, self._start - self._step, -self._step)

  @immutable
  def __str__(self) -> str:
    return repr(self)

  @immutable
  def __repr__(self) -> str:
    out: str = "range("
    out += str(self._start)
    out += ", "
    out += str(self._stop)
    if self._step != 1:
      out += ", "
      out += str(self._step)
    out += ")"
    return out

  def __iter__(self) -> RangeIterator:
    return new(self._start, self._stop, self._step)
