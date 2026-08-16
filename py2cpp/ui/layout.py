"""双列表单布局（``UIFormLayout``）；Win32 挂载由 codegen 注入。"""

from ..builtins import *
from .widget import (
  UICheckBox,
  UIFloatEdit,
  UIIntEdit,
  UILineEdit,
  UIPushButton,
  UISlider,
  UIWidget,
)
from .window import UIWindow


@dataclass(eq=False, repr=False)
class UIFormLayout:
  _applied: bool = False

  @native
  def clear(self) -> None:
    """丢弃已登记的行/按钮（下次 ``apply`` 前调用）。"""
    ...

  @native
  def addCheckbox(self, label: str, widget: UICheckBox @ref) -> None:
    ...

  @native
  def addLineEdit(self, label: str, widget: UILineEdit @ref) -> None:
    ...

  @native
  def addIntEdit(self, label: str, widget: UIIntEdit @ref) -> None:
    ...

  @native
  def addFloatEdit(self, label: str, widget: UIFloatEdit @ref) -> None:
    ...

  @native
  def addSlider(self, label: str, widget: UISlider @ref) -> None:
    ...

  @native
  def addButton(self, widget: UIPushButton @ref) -> None:
    ...

  @native
  def apply(self, win: UIWindow @ref) -> None:
    """在 ``win`` 上创建/复用控件；无 ``handle`` 时为 no-op。"""
    ...

  @native
  def syncFromNative(self, win: UIWindow @ref) -> None:
    """自 Win32 读入各 ``UIWidget`` 字段。"""
    ...

  @native
  def rowCount(self) -> int:
    ...

  @native
  def rowBool(self, index: int) -> bool:
    ...

  @native
  def rowStr(self, index: int) -> str:
    ...

  @native
  def rowInt(self, index: int) -> int:
    ...

  @native
  def rowFloat(self, index: int) -> float64:
    ...

  @native
  def setRowBool(self, index: int, value: bool) -> None:
    ...

  @native
  def setRowStr(self, index: int, value: str) -> None:
    ...

  @native
  def setRowInt(self, index: int, value: int) -> None:
    ...

  @native
  def setRowFloat(self, index: int, value: float64) -> None:
    ...

  @native
  def pushRowBool(self, index: int, value: bool) -> None:
    """写对应 checkbox ``checked__set``（触发 postsetter → Win32）。"""
    ...

  @native
  def pushRowStr(self, index: int, value: str) -> None:
    """写对应 line edit ``text__set``。"""
    ...

  @native
  def pushRowInt(self, index: int, value: int) -> None:
    """写对应 int edit / slider ``value__set``。"""
    ...

  @native
  def pushRowFloat(self, index: int, value: float64) -> None:
    """写对应 float edit ``value__set``。"""
    ...

  @native
  def syncToNative(self, win: UIWindow @ref) -> None:
    """将各 ``UIWidget`` 字段写回 Win32。"""
    ...
