"""Win32 ToolTip 宿主。"""
from ..builtins import *
from .window import UIWindow


@copyable
class UITooltipHost:
  handle: int64 = 0

  @native
  def attach(self, win: UIWindow @ref) -> None:
    """在 ``win`` 上创建 ToolTip 控件。"""
    ...

  @native
  def showAtClient(self, win: UIWindow @ref, text: str, cx: int, cy: int) -> None:
    """在窗口客户区 ``(cx,cy)`` 显示提示。"""
    ...

  @native
  def hide(self) -> None:
    ...
