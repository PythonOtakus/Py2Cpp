"""常用 ``@protocol`` 概念：``collections.abc`` 与 ``numbers``（PEP 3141）子集。

仅用于翻译期 SFINAE（``Protocol_requires<T>``），不生成 C++ 类、不作继承基类。
探测实现见 ``src/codegen/protocol_traits_gen.py``（运算符表达式、``operators.h`` 全局函数、少量成员探测）。
"""
from __future__ import annotations

from ..builtins import *
from .iter_result import IterResult


def protocol(cls):
  """与 ``__init__.protocol`` 相同（``core/protocols`` 在 bootstrap 中单独翻译）。"""
  return cls


class Self:
  """与 ``__init__.Self`` 相同：协议方法注解中的当前类型。"""

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
class Generator[YieldType, SendType, ReturnType]:
  """``typing.Generator`` 子集：``__iter__`` / ``__next__`` / ``send``（PEP 342）。

  生成器函数 ``def f() -> Generator[Y, S, R]: yield ...`` 由 ``generators`` pass 译为 ``*_generator`` 类；
  本协议仅作类型约束与 SFINAE，不生成 C++ 类。
  """

  def __iter__(self) -> Self: ...

  def __next__(self) -> IterResult[YieldType, ReturnType]: ...

  def send(self, value: SendType) -> IterResult[YieldType, ReturnType]: ...


@protocol
class Coroutine[YieldType, SendType, ReturnType]:
  """``typing.Coroutine`` 子集（PEP 492 / 3.13）：``__await__`` + ``__next__`` / ``send``。

  纯 ``async def``（无 ``yield``）译为 ``*_coroutine``；``await`` 脱糖为 ``yield from x.__await__()``。
  """

  def __iter__(self) -> Self: ...

  def __next__(self) -> IterResult[YieldType, ReturnType]: ...

  def __await__(self) -> Self: ...

  def send(self, value: SendType) -> IterResult[YieldType, ReturnType]: ...


@protocol
class AsyncGenerator[YieldType, SendType]:
  """``typing.AsyncGenerator`` 子集（PEP 525 / 3.13）：``__aiter__`` / ``__anext__`` / ``asend``。

  ``async def`` 含 ``yield`` 仍译为 ``*_coroutine``；推荐 ``-> AsyncGenerator[Y,S]`` 作返回注解。
  """

  def __aiter__(self) -> Self: ...

  def __anext__(self) -> IterResult[YieldType, None]: ...

  def asend(self, value: SendType) -> IterResult[YieldType, None]: ...


@protocol
class Awaitable[T]:
  """可被 ``await`` 的对象：``__await__`` 返回迭代器（协程 / 生成器等）。"""

  def __await__(self) -> Iterator[T]: ...


@protocol
class AsyncIterable[T]:
  """``collections.abc.AsyncIterable``：``__aiter__``。"""

  def __aiter__(self) -> AsyncIterator[T]: ...


@protocol
class AsyncIterator[T]:
  """``collections.abc.AsyncIterator``：``__anext__`` → ``IterResult[T, ...]``（同 ``Iterator`` / ``__next__``）。"""

  def __aiter__(self) -> Self: ...

  def __anext__(self) -> IterResult[T, None]: ...


@protocol
class ContextManager[T]:
  """同步上下文管理器（``collections.abc`` 子集）：``with`` 展开为 ``__enter__`` / ``__exit__``。

  ``__exit__`` 无异常三元组（与生成 C++ 一致，见 ``test/misc/test_io.py``）。
  """

  def __enter__(self) -> T: ...

  def __exit__(self): ...


@protocol
class AsyncContextManager[T]:
  """异步上下文管理器：``__aenter__`` / ``__aexit__``（``async with`` 脱糖为 ``yield from``）。"""

  def __aenter__(self) -> Awaitable[T]: ...

  def __aexit__(self) -> Awaitable[None]: ...


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


# ---------------------------------------------------------------------------
# 数值塔（``numbers`` / PEP 3141，对齐 Python 3.13 ``Lib/numbers.py``）
# ---------------------------------------------------------------------------


@protocol
class Number:
  """``numbers.Number``：可哈希（``hash(x)`` → ``__hash__``）。"""

  def __hash__(self) -> int: ...


@protocol
class Complex:
  """``numbers.Complex`` 核心运算（``+`` ``-`` ``*`` ``/`` ``**`` ``==``；``/`` 走 ``::__truediv__``）。"""

  def __eq__(self, other: Self) -> bool: ...

  def __add__(self, other: Self) -> Self: ...

  def __mul__(self, other: Self) -> Self: ...

  def __truediv__(self, other: Self) -> float: ...

  def __pow__(self, other: Self) -> Self: ...

  def __neg__(self) -> Self: ...

  def __pos__(self) -> Self: ...


@protocol
class Real(Complex):
  """``numbers.Real``：实数比较、整除/取模、转 ``float``。"""

  def __lt__(self, other: Self) -> bool: ...

  def __le__(self, other: Self) -> bool: ...

  def __gt__(self, other: Self) -> bool: ...

  def __ge__(self, other: Self) -> bool: ...

  def __floordiv__(self, other: Self) -> Self: ...

  def __mod__(self, other: Self) -> Self: ...

  def __float__(self) -> float: ...


@protocol
class Rational(Real):
  """``numbers.Rational``：``numerator`` / ``denominator`` 字段或 ``@property``（见 ``numbers``）。"""

  denominator: int = ...

  numerator: int = ...


@protocol
class Integral(Real):
  """``numbers.Integral``（不含 ``Rational`` 属性探测）：``int`` 与位运算。"""

  def __lshift__(self, other: Self) -> Self: ...

  def __rshift__(self, other: Self) -> Self: ...

  def __and__(self, other: Self) -> Self: ...

  def __or__(self, other: Self) -> Self: ...

  def __xor__(self, other: Self) -> Self: ...

  def __int__(self) -> int: ...

  def __invert__(self) -> Self: ...


@protocol
class Arithmetic:
  """兼容别名：``Real`` 的 ``%`` / ``/`` / ``//`` 三项（``::__mod__`` 等全局函数）。"""

  def __truediv__(self, other: Self) -> float: ...

  def __floordiv__(self, other: Self) -> Self: ...

  def __mod__(self, other: Self) -> Self: ...


@protocol
class StringFormat:
  """``str %`` 仅 ``::__mod__(fmt, PyTuple<...>)``；单值须 ``makeTuple``，不探测 ``PyStr % int``。"""

  def __mod__(self, other: tuple) -> str: ...


# ---------------------------------------------------------------------------
# 全序比较（Comparable）
# ---------------------------------------------------------------------------


@protocol
class Comparable:
  """全序比较：探测 ``U < U`` 等表达式（要求结果为 ``PyBool``），不探测成员 ``__lt__``。"""

  def __eq__(self, other: Self) -> bool: ...

  def __ne__(self, other: Self) -> bool: ...

  def __lt__(self, other: Self) -> bool: ...

  def __le__(self, other: Self) -> bool: ...

  def __gt__(self, other: Self) -> bool: ...

  def __ge__(self, other: Self) -> bool: ...
