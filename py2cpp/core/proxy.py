"""``Proxy[T]``：形式继承 ``T`` 的透明代理（内层 ``_target``；``super`` 访问目标）。"""
from ..builtins import *


@copyable
@native
@native_name("Py*")
class Proxy[T]:
  """C++ 为 ``PyProxy<StorageT>`` 组合存储；未 ``@override`` 的成员由译器剥壳转发。"""

  _target: T

  def __init__(self, target: T):
    self._target = target
