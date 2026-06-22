"""双列表单布局（``UIFormLayout``）；Win32 挂载由 codegen 注入。"""

from ..builtins import *
from .widget import UICheckBox, UIIntEdit, UILineEdit, UIPushButton, UISlider, UIWidget
from .window import UIWindow


@dataclass(eq=False, repr=False)
class UIFormLayout:
  _applied: bool = False

  @native
  def clear(self) -> None:
    """丢弃已登记的行/按钮（下次 ``apply`` 前调用）。"""
    ...

  @native
  def add_checkbox(self, label: str, widget: UICheckBox @ref) -> None:
    ...

  @native
  def add_line_edit(self, label: str, widget: UILineEdit @ref) -> None:
    ...

  @native
  def add_int_edit(self, label: str, widget: UIIntEdit @ref) -> None:
    ...

  @native
  def add_slider(self, label: str, widget: UISlider @ref) -> None:
    ...

  @native
  def add_button(self, widget: UIPushButton @ref) -> None:
    ...

  @native
  def apply(self, win: UIWindow @ref) -> None:
    """在 ``win`` 上创建/复用控件；无 ``handle`` 时为 no-op。"""
    ...

  @native
  def sync_from_native(self, win: UIWindow @ref) -> None:
    """自 Win32 读入各 ``UIWidget`` 字段。"""
    ...

  @native
  def row_count(self) -> int:
    ...

  @native
  def row_bool(self, index: int) -> bool:
    ...

  @native
  def row_str(self, index: int) -> str:
    ...

  @native
  def row_int(self, index: int) -> int:
    ...

  @native
  def set_row_bool(self, index: int, value: bool) -> None:
    ...

  @native
  def set_row_str(self, index: int, value: str) -> None:
    ...

  @native
  def set_row_int(self, index: int, value: int) -> None:
    ...

  @native
  def push_row_bool(self, index: int, value: bool) -> None:
    """写对应 checkbox ``checked__set``（触发 postsetter → Win32）。"""
    ...

  @native
  def push_row_str(self, index: int, value: str) -> None:
    """写对应 line edit ``text__set``。"""
    ...

  @native
  def push_row_int(self, index: int, value: int) -> None:
    """写对应 int edit / slider ``value__set``。"""
    ...

  @native
  def sync_to_native(self, win: UIWindow @ref) -> None:
    """将各 ``UIWidget`` 字段写回 Win32。"""
    ...
