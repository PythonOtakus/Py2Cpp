"""异常类型占位（翻译为 C++ 中对应的异常类或错误路径）。

``ExceptionGroup`` 的 ``append`` / ``assign`` / ``clear`` / ``__len__`` 等为 ``@native`` 桩；
``ExcSlot`` 由 ``@union.mro`` 生成；``ExceptionGroup`` 容器逻辑由 ``exception_group_gen`` 注入。
"""
from __future__ import annotations

from ..builtins import *


class Exception:
  """所有内置异常的基类。"""

  @virtual
  def add_note(self, note: str) -> None:
    """PEP 678 子集：为异常附加说明（虚函数触发 ``__class_id__`` 动态派发）。"""
    pass


class StopIteration(Exception):
  """迭代结束；在 C++ 中 ``__next__`` 映射为 ``IterResult`` 的 ``done``，一般不抛此类型。"""

  pass


class TypeError(Exception):
  pass


class KeyError(Exception):
  pass


class IndexError(Exception):
  pass


class ValueError(Exception):
  pass


class StatisticsError(ValueError):
  """统计计算错误（对齐 ``statistics.StatisticsError``）。"""

  pass


class LinAlgError(ValueError):
  """线性代数错误（对齐 ``numpy.linalg.LinAlgError``）。"""

  pass


class RuntimeError(Exception):
  pass


class ReferenceError(Exception):
  """弱引用目标已失效（对齐 CPython ``weakref``）。"""

  pass


class OSError(Exception):
  """操作系统错误（``pathlib`` / ``os`` 子集）。"""

  pass


class FileNotFoundError(OSError):
  pass


class FileExistsError(OSError):
  pass


class AssertionError(Exception):
  """断言失败（``unittest`` 软断言默认仅计数；显式 ``raise AssertionError()`` 可映射为 C++ throw）。"""

  pass


@union.mro
class ExcSlot(base=Exception):
  """``except*`` 单异常槽；MRO 变体与 ``Enum`` 由译器自 MRO 闭集生成；额外枚举式变体用 ``@variant class …``。"""

  @variant
  class Unknown:
    pass


class BaseExceptionGroup(Exception):
  """PEP 654 异常组基类。"""

  pass


@native
class ExceptionGroup(BaseExceptionGroup):
  """``ExceptionGroup(message, exceptions)``（对齐 Python 3.13 子集）。

  ``len(eg)`` / ``if eg`` / ``eg.clear()`` / ``eg.copy_from(other)`` / ``eg.append(exc)``。
  ``except*`` 捕获的 ``as eg`` 绑定为匹配子组；构造 ``ExceptionGroup("", […])`` 由译器展开为
  ``clear`` + 逐元素 ``append``。
  """

  @immutable
  def __len__(self) -> int:
    """子组内异常个数（``len(eg.exceptions)`` 等价）。"""
    ...

  @immutable
  def __bool__(self) -> bool:
    """非空为真（``if eg`` / ``not eg``）。"""
    ...

  def clear(self) -> None:
    """清空槽位。"""
    ...

  def copy_from(self, other: Self) -> None:
    """自 ``other`` 拷贝槽位（``except*`` 拆分内部使用）。"""
    ...

  def append[T: Exception](self, e: T) -> None:
    """追加单个异常（``ExcSlot`` 变体工厂）。"""
    ...
