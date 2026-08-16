"""多播委托基类 ``Delegate``（C++：``PyDelegate<Ret, Args...>``）。

用户模块用 ``@delegate`` 定义的具体委托（如 ``FuncDelegate``、``ActionDelegate``）继承该基类；
``+=`` / ``-=`` / ``operator bool`` 在基类中实现。
"""
from ..builtins import *

__all__ = ["Delegate"]


@native
class Delegate:
  """占位基类；运行时逻辑见生成的 ``py2cpp/delegate.h``。"""

  pass
