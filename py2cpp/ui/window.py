"""Win32 顶层窗口（Qt-like ``UIWindow``；事件循环见 ``UIApp``）。

用法::

  from py2cpp.ui.app import UIApp

  if UIApp.isAvailable():
    win: UIWindow = new(title="Title")
    win.show(480, 360)
    obj.drawPanel(win)
    UIApp.run()

``width``/``height`` 为 ``-1`` 时先按最小窗口布局，``drawPanel`` 后须 ``resize``（``createPanel`` / ``showPanel`` 默认 ``-1`` 已内置）。
"""

from ..builtins import *
from .style import UIStyle
from .widget import UIWidget


@dataclass(eq=False, repr=False)
class UIWindow(UIWidget):
  """顶层窗口（``QWidget`` 子类）；原生句柄在 ``handle``。"""

  style: UIStyle = new()
  nextY: int @optional = 10
  activeForm: int64 @optional = 0
  flowShellPtr: int64 @optional = 0
  flowCanvasPtr: int64 @optional = 0
  title: str @property.postsetter(_applyTitle) = ""

  @native
  def _applyTitle(self) -> None:
    """已 ``show`` 时将 ``title__value`` 同步为 Win32 窗口 caption。"""
    ...

  @native
  def show(self, width: int, height: int) -> None:
    """创建并显示顶层窗口；``width``/``height`` 为 ``-1`` 时用最小客户区并隐藏，待 ``resize``。"""
    ...

  @native
  def resize(self, width: int, height: int) -> None:
    """按 ``nextY`` 与 ``style`` 调整客户区；``width``/``height`` 为 ``-1`` 时自适应该维。"""
    ...

  @native
  def close(self) -> None:
    """销毁窗口（不阻塞；测试用）。"""
    ...

  @native
  def clientOriginScreen(self) -> (int, int):
    """客户区左上角的屏幕坐标 ``(x, y)``；未 ``show`` 时 ``(0, 0)``。"""
    ...

  @native
  def clientSize(self) -> (int, int):
    """客户区宽高；未 ``show`` 时 ``(0, 0)``。"""
    ...
