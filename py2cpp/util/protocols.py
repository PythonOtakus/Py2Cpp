"""容器与序列 ``@protocol`` 概念（``collections.abc`` 子集）。

仅用于翻译期 SFINAE（``Protocol_requires<T>``），不生成 C++ 类、不作继承基类。
"""
from __future__ import annotations

from ..builtins import *


def protocol(cls):
  """与 ``__init__.protocol`` / ``core.protocols.protocol`` 相同。"""
  return cls


class Self:
  """协议方法注解中的当前类型（与 ``core.protocols.Self`` 相同）。"""

  pass


# ---------------------------------------------------------------------------
# 规模与成员（Sized / Container / Collection）
# ---------------------------------------------------------------------------


@protocol
class Sized:
  """``collections.abc.Sized``：支持 ``len(x)`` → ``__len__``。"""

  def __len__(self) -> int: ...


@protocol
class Container[T]:
  """``collections.abc.Container``：支持 ``x in c`` → ``__contains__``。"""

  type Element = ...

  def __contains__(self, item: Element) -> bool: ...


@protocol
class Collection[T]:
  """``collections.abc.Collection``：``Sized`` + ``Iterable`` + ``Container`` 合一探测。"""

  type Element = ...

  def __len__(self) -> int: ...

  def __contains__(self, item: Element) -> bool: ...

  def __iter__(self) -> Iterator[T]: ...


@protocol
class IteratorElement:
  """迭代器须声明 ``type Element = ...``（C++ ``using Element``），且实现 ``__iter__`` / ``__next__``。"""

  type Element = ...

  def __iter__(self) -> Self: ...

  def __next__(self) -> Element: ...


@protocol
class IterableIterator[It: IteratorElement]:
  """``__iter__`` 返回满足 ``IteratorElement`` 的迭代器类型 ``It``。"""

  def __iter__(self) -> It: ...


# ---------------------------------------------------------------------------
# 迭代（Iterable / Iterator）
# ---------------------------------------------------------------------------


@protocol
class Iterable[T]:
  """``collections.abc.Iterable``：支持 ``iter(x)`` → ``__iter__``。"""

  def __iter__(self) -> Iterator[T]: ...


@protocol
class Iterator[T]:
  """``collections.abc.Iterator``：``Iterable`` + ``__next__`` → 产出 ``T``（生成器协议用 ``IterResult``）。"""

  def __iter__(self) -> Self: ...

  def __next__(self) -> T: ...


@protocol
class Reversible[T]:
  """``collections.abc.Reversible``：支持 ``reversed(x)`` → ``__reversed__``。"""

  def __reversed__(self) -> Iterator[T]: ...


# ---------------------------------------------------------------------------
# 判等 / 哈希（dict 键、set 元素等）
# ---------------------------------------------------------------------------


@protocol
class Equatable:
  """判等：探测 ``U == U`` / ``U != U``（结果为 ``PyBool``），用于容器元素、dict 键。"""

  def __eq__(self, other: Self) -> bool: ...

  def __ne__(self, other: Self) -> bool: ...


@protocol
class Comparable:
  """全序比较：探测 ``U < U`` 等表达式（要求结果为 ``PyBool``），不探测成员 ``__lt__``。"""

  def __eq__(self, other: Self) -> bool: ...

  def __ne__(self, other: Self) -> bool: ...

  def __lt__(self, other: Self) -> bool: ...

  def __le__(self, other: Self) -> bool: ...

  def __gt__(self, other: Self) -> bool: ...

  def __ge__(self, other: Self) -> bool: ...


@protocol
class Hashable:
  """``collections.abc.Hashable``：``hash(x)`` → ``__hash__``，返回 ``int``。"""

  def __hash__(self) -> int: ...


@protocol
class DictKey:
  """``dict[K,V]`` 键约束：``Hashable`` + ``Equatable``（``_index`` / ``_find_node`` 所需）。"""

  def __eq__(self, other: Self) -> bool: ...

  def __ne__(self, other: Self) -> bool: ...

  def __hash__(self) -> int: ...


@protocol
class Appendable[T]:
  """实现 ``append`` 的序列容器（``list``、``deque`` 等）：可用 ``[a, b, c]`` 字面量初始化。"""

  type Element = ...

  def append(self, item: Element): ...


@protocol
class MutableMapping[K, V]:
  """实现 ``__setitem__`` 的映射（``dict`` 等）：可用 ``{k: v, ...}`` 字面量初始化。"""

  type Key = ...

  type Value = ...

  def __setitem__(self, key: Key, value: Value): ...
