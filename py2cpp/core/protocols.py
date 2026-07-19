"""语言级 ``@protocol`` 概念：生成器、协程、上下文管理器与 ``str %`` 等。

容器协议见 ``util.protocols``；数值塔见 ``numeric.protocols``。
仅用于翻译期 SFINAE（``Protocol_requires<T>``），不生成 C++ 类、不作继承基类。
"""
from __future__ import annotations

from ..builtins import *
from ..util.protocols import Iterator
from .iter_result import IterResult


def protocol(cls):
  """与 ``__init__.protocol`` 相同（``core/protocols`` 在 bootstrap 中单独翻译）。"""
  return cls


class Self:
  """与 ``__init__.Self`` 相同：协议方法注解中的当前类型。"""

  pass


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
class StringFormat:
  """``str %`` 仅 ``::__mod__(fmt, PyTuple<...>)``；单值须 ``makeTuple``，不探测 ``PyStr % int``。"""

  def __mod__(self, other: tuple) -> str: ...
