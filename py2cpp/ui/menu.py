"""Win32 菜单栏（``UIMenuBar``）。"""
from ..builtins import *
from .window import UIWindow


@copyable
class UIMenuBar:
  """顶层 ``UIWindow`` 菜单；``WM_COMMAND`` 由 ``+menu.inl`` 转发至 ``owner``。"""

  handle: int64 = 0
  _ownerPtr: int64 = 0

  @native
  def attach(self, win: UIWindow @ref) -> None:
    """创建菜单并 ``SetMenu``；``WM_COMMAND`` 转发至 ``win`` 上注册的 ``UIFlowShell``。"""
    ...

  @native
  def buildFlowDefault(self) -> None:
    """File / Edit / View / Run（Run 项默认 grayed）。"""
    ...

  @native
  def setRunEnabled(self, play: bool, playSel: bool, stop: bool) -> None:
    """P2 启用 Run 菜单项。"""
    ...
