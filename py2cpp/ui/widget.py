"""可挂载 Win32 控件的 ``UIWidget`` 子类。"""

from ..builtins import *
from .events import UIEventDelegate, UIValueChangedDelegate


@dataclass(eq=False, repr=False)
class UIObject:
  name: str = ""
  id: int = 0


class UIWidget(UIObject):
  handle: int64 = 0


@dataclass(eq=False, repr=False)
class UICheckBox(UIWidget):
  stateChanged: UIValueChangedDelegate[bool] = new()

  @native
  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``checked__value`` 写回 Win32 checkbox。"""
    ...

  checked: bool @property.postsetter(_syncToNative, stateChanged) = False


@dataclass(eq=False, repr=False)
class UILineEdit(UIWidget):
  textChanged: UIValueChangedDelegate[str] = new()

  @native
  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``text__value`` 写回 Win32 edit。"""
    ...

  text: str @property.postsetter(_syncToNative, textChanged) = ""


@dataclass(eq=False, repr=False)
class UIIntEdit(UIWidget):
  valueChanged: UIValueChangedDelegate[int] = new()

  @native
  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``value__value`` 写回 Win32 edit。"""
    ...

  value: int @property.postsetter(_syncToNative, valueChanged) = 0


@dataclass(eq=False, repr=False)
class UIFloatEdit(UIWidget):
  valueChanged: UIValueChangedDelegate[float64] = new()

  @native
  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``value__value`` 写回 Win32 edit。"""
    ...

  value: float64 @property.postsetter(_syncToNative, valueChanged) = 0.0


@dataclass(eq=False, repr=False)
class UISlider(UIWidget):
  lo: int = 0
  hi: int = 100
  valueChanged: UIValueChangedDelegate[int] = new()

  @native
  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``value__value`` 写回 Win32 slider。"""
    ...

  value: int @property.postsetter(_syncToNative, valueChanged) = 0


@dataclass(eq=False, repr=False)
class UIPushButton(UIWidget):
  text: str = ""
  clicked: UIEventDelegate = new()
