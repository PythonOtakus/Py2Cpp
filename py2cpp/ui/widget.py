"""可挂载 Win32 控件的 ``UIWidget`` 子类。"""

from ..builtins import *
from .events import UIEvent, UIValueChanged


@dataclass(eq=False, repr=False)
class UIObject:
  name: str = ""
  id: int = 0


class UIWidget(UIObject):
  handle: int64 @optional = 0


@dataclass(eq=False, repr=False)
class UICheckBox(UIWidget):
  state_changed: UIValueChanged[bool] = new()

  @native
  def _sync_to_native(self) -> None:
    """``handle`` 非 0 时将 ``checked__value`` 写回 Win32 checkbox。"""
    ...

  checked: bool @property.postsetter(_sync_to_native, state_changed) = False


@dataclass(eq=False, repr=False)
class UILineEdit(UIWidget):
  text_changed: UIValueChanged[str] = new()

  @native
  def _sync_to_native(self) -> None:
    """``handle`` 非 0 时将 ``text__value`` 写回 Win32 edit。"""
    ...

  text: str @property.postsetter(_sync_to_native, text_changed) = ""


@dataclass(eq=False, repr=False)
class UIIntEdit(UIWidget):
  value_changed: UIValueChanged[int] = new()

  @native
  def _sync_to_native(self) -> None:
    """``handle`` 非 0 时将 ``value__value`` 写回 Win32 edit。"""
    ...

  value: int @property.postsetter(_sync_to_native, value_changed) = 0


@dataclass(eq=False, repr=False)
class UISlider(UIWidget):
  lo: int = 0
  hi: int = 100
  value_changed: UIValueChanged[int] = new()

  @native
  def _sync_to_native(self) -> None:
    """``handle`` 非 0 时将 ``value__value`` 写回 Win32 slider。"""
    ...

  value: int @property.postsetter(_sync_to_native, value_changed) = 0


@dataclass(eq=False, repr=False)
class UIPushButton(UIWidget):
  text: str = ""
  clicked: UIEvent = new()
