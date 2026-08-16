"""Win32 输入辅助（屏幕坐标等）。"""
from ..builtins import *


@native
def cursorScreenPos() -> (int, int):
  """``GetCursorPos`` → 屏幕坐标。"""
  ...


@native
def shiftDown() -> bool:
  """``GetKeyState(VK_SHIFT)``。"""
  ...


@native
def ctrlDown() -> bool:
  """``GetKeyState(VK_CONTROL)``。"""
  ...
