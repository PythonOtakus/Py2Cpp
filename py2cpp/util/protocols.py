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
# 规模与成员（SizedType / ContainerType / CollectionType）
# ---------------------------------------------------------------------------


@protocol
class SizedType:
  """``collections.abc.SizedType``：支持 ``len(x)`` → ``__len__``。"""

  def __len__(self) -> int: ...


@protocol
class ContainerType[Element]:
  """``collections.abc.ContainerType``：支持 ``x in c`` → ``__contains__``。"""

  type Element = ...

  def __contains__(self, item: Element) -> bool: ...


@protocol
class CollectionType[Element]:
  """``collections.abc.CollectionType``：``SizedType`` + ``IterableType`` + ``ContainerType`` 合一探测。"""

  type Element = ...

  def __len__(self) -> int: ...

  def __contains__(self, item: Element) -> bool: ...

  def __iter__(self) -> IteratorType[Element]: ...


@protocol
class IteratorElementType:
  """迭代器须声明 ``type Element = ...``（C++ ``using Element``），且实现 ``__iter__`` / ``__next__``。"""

  type Element = ...

  def __iter__(self) -> Self: ...

  def __next__(self) -> Element: ...


@protocol
class IterableIteratorType[It: IteratorElementType]:
  """``__iter__`` 返回满足 ``IteratorElementType`` 的迭代器类型 ``It``。"""

  def __iter__(self) -> It: ...


# ---------------------------------------------------------------------------
# 迭代（IterableType / IteratorType）
# ---------------------------------------------------------------------------


@protocol
class IterableType[Element]:
  """``collections.abc.IterableType``：支持 ``iter(x)`` → ``__iter__``。"""

  def __iter__(self) -> IteratorType[Element]: ...


@protocol
class IteratorType[Element]:
  """``collections.abc.IteratorType``：``IterableType`` + ``__next__`` → 产出 ``T``（生成器协议用 ``IterResult``）。"""

  def __iter__(self) -> Self: ...

  def __next__(self) -> Element: ...


@protocol
class ReversibleType[Element]:
  """``collections.abc.ReversibleType``：支持 ``reversed(x)`` → ``__reversed__``。"""

  def __reversed__(self) -> IteratorType[Element]: ...


# ---------------------------------------------------------------------------
# 判等 / 哈希（dict 键、set 元素等）
# ---------------------------------------------------------------------------


@protocol
class EquatableType:
  """判等：探测 ``U == U`` / ``U != U``（结果为 ``PyBool``），用于容器元素、dict 键。"""

  def __eq__(self, other: Self) -> bool: ...

  def __ne__(self, other: Self) -> bool: ...


@protocol
class ComparableType:
  """全序比较：探测 ``U < U`` 等表达式（要求结果为 ``PyBool``），不探测成员 ``__lt__``。"""

  def __eq__(self, other: Self) -> bool: ...

  def __ne__(self, other: Self) -> bool: ...

  def __lt__(self, other: Self) -> bool: ...

  def __le__(self, other: Self) -> bool: ...

  def __gt__(self, other: Self) -> bool: ...

  def __ge__(self, other: Self) -> bool: ...


@protocol
class HashableType:
  """``collections.abc.HashableType``：``hash(x)`` → ``__hash__``，返回 ``int``。"""

  def __hash__(self) -> int: ...


@protocol
class DictKeyType:
  """``dict[K,V]`` 键约束：``HashableType`` + ``EquatableType``（``_index`` / ``_findNode`` 所需）。"""

  def __eq__(self, other: Self) -> bool: ...

  def __ne__(self, other: Self) -> bool: ...

  def __hash__(self) -> int: ...


@protocol
class AppendableType[Element]:
  """实现 ``append`` 的序列容器（``list``、``deque`` 等）：可用 ``[a, b, c]`` 字面量初始化。"""

  type Element = ...

  def append(self, item: Element): ...


@protocol
class MutableMappingType[Key, Value]:
  """实现 ``__setitem__`` 的映射（``dict`` 等）：可用 ``{k: v, ...}`` 字面量初始化。"""

  type Key = ...

  type Value = ...

  def __setitem__(self, key: Key, value: Value): ...
