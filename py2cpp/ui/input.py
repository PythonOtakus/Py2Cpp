"""Win32 输入辅助（屏幕坐标等）。"""
from ..builtins import *


@native
def cursor_screen_pos() -> (int, int):
  """``GetCursorPos`` → 屏幕坐标。"""
  ...


@native
def shift_down() -> bool:
  """``GetKeyState(VK_SHIFT)``。"""
  ...


@native
def ctrl_down() -> bool:
  """``GetKeyState(VK_CONTROL)``。"""
  ...
