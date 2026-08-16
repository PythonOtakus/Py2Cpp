"""``Proxy[T]``：形式继承 ``T`` 的透明代理（内层 ``_target``；``super`` 访问目标）。"""
from ..builtins import *


@copyable
@native
class Proxy[Element]:
  """C++ 为 ``PyProxy<StorageT>`` 组合存储；未 ``@override`` 的成员由译器剥壳转发。"""

  _target: Element

  def __init__(self, target: Element):
    self._target = target
