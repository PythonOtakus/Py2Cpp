"""可挂载 Win32 控件的 ``UIWidget`` 子类。"""

from ..builtins import *
from ffi.windows import (
  PyiBmGetcheck,
  PyiBmSetcheck,
  PyiBstChecked,
  PyiHwnd,
  PyiWmUser,
  pyiGetWindowTextA,
  pyiSendMessageA,
  pyiSetWindowTextA,
)
from .events import UIEventDelegate, UIValueChangedDelegate


@dataclass(eq=False, repr=False)
class UIObject:
  name: str = ""
  id: int = 0


class UIWidget(UIObject):
  handle: int64 = 0


@immutable
def _widgetHandle(handle: int64) -> Pointer[PyiHwnd]:
  return cast(handle)


@immutable
def _widgetText(handle: int64, cap: int) -> str:
  buf: byte[:] = new(cap)
  n: int = pyiGetWindowTextA(_widgetHandle(handle), buf.view.at(0), cap)
  if n <= 0:
    return ""
  return str.fromSpanBytes(buf.view[:n])


@immutable
def _widgetSetText(handle: int64, value: str) -> None:
  with value.useUtf8() as cvalue:
    pyiSetWindowTextA(_widgetHandle(handle), cvalue)


@dataclass(eq=False, repr=False)
class UICheckBox(UIWidget):
  stateChanged: UIValueChangedDelegate[bool] = new()

  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``checked`` 写回 Win32 checkbox。"""
    if self.handle == 0:
      return
    want: int = PyiBstChecked if self.checked else 0
    if int(pyiSendMessageA(_widgetHandle(self.handle), PyiBmGetcheck, 0, 0)) != want:
      pyiSendMessageA(_widgetHandle(self.handle), PyiBmSetcheck, want, 0)

  checked: bool @property.postsetter(_syncToNative, stateChanged) = False


@dataclass(eq=False, repr=False)
class UILineEdit(UIWidget):
  textChanged: UIValueChangedDelegate[str] = new()

  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``text`` 写回 Win32 edit。"""
    if self.handle == 0:
      return
    if _widgetText(self.handle, 512) != self.text:
      _widgetSetText(self.handle, self.text)

  text: str @property.postsetter(_syncToNative, textChanged) = ""


@dataclass(eq=False, repr=False)
class UIIntEdit(UIWidget):
  valueChanged: UIValueChangedDelegate[int] = new()

  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``value`` 写回 Win32 edit。"""
    if self.handle == 0:
      return
    if _widgetText(self.handle, 32) != str(self.value):
      _widgetSetText(self.handle, str(self.value))

  value: int @property.postsetter(_syncToNative, valueChanged) = 0


@dataclass(eq=False, repr=False)
class UIFloatEdit(UIWidget):
  valueChanged: UIValueChangedDelegate[float64] = new()

  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``value`` 写回 Win32 edit。"""
    if self.handle == 0:
      return
    if _widgetText(self.handle, 64) != str(self.value):
      _widgetSetText(self.handle, str(self.value))

  value: float64 @property.postsetter(_syncToNative, valueChanged) = 0.0


@dataclass(eq=False, repr=False)
class UISlider(UIWidget):
  lo: int = 0
  hi: int = 100
  valueChanged: UIValueChangedDelegate[int] = new()

  def _syncToNative(self) -> None:
    """``handle`` 非 0 时将 ``value`` 写回 Win32 slider。"""
    if self.handle == 0:
      return
    want: int = self.value
    if want < self.lo:
      want = self.lo
    if want > self.hi:
      want = self.hi
    if int(pyiSendMessageA(_widgetHandle(self.handle), PyiWmUser, 0, 0)) != want:
      pyiSendMessageA(_widgetHandle(self.handle), PyiWmUser + 5, 1, want)

  value: int @property.postsetter(_syncToNative, valueChanged) = 0


@dataclass(eq=False, repr=False)
class UIPushButton(UIWidget):
  text: str = ""
  clicked: UIEventDelegate = new()
