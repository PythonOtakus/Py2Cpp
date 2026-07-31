"""Qt-like 应用入口：后端可用性与全局事件循环。"""

from ..builtins import *


class UIApp:
  @staticmethod
  @native
  def is_available() -> bool:
    """当前平台 Win32 UI 是否可用（Windows 为 ``True``）。"""
    ...

  @staticmethod
  @native
  def run() -> int:
    """``GetMessage`` 消息循环直至 ``PostQuitMessage``；等价 Qt ``QApplication::exec()``。"""
    ...

  @staticmethod
  @native
  def pump() -> int:
    """非阻塞泵一次：``0``=已退出，``1``=处理了消息，``2``=空闲（可渲染）。"""
    ...
