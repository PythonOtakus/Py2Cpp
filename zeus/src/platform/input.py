"""GLFW 输入：纯 Python 组合 ``ffi.glfw.glfw3``。"""
from __future__ import annotations

from py2cpp import *
from ffi.glfw.glfw3 import (
  PyiGlfwKeySpace,
  PyiGlfwMouseButtonLeft,
  PyiGlfwPress,
  PyiGlfwWindow,
  pyiGlfwGetCursorPos,
  pyiGlfwGetKey,
  pyiGlfwGetMouseButton,
)

from .window import Window


def key_down(window: Window, key: int) -> bool:
  """``glfwGetKey`` 是否按下。"""
  win: Pointer[PyiGlfwWindow] = window.handle
  if win is None:
    return False
  return pyiGlfwGetKey(win, key) == PyiGlfwPress


def space_down(window: Window) -> bool:
  return key_down(window, PyiGlfwKeySpace)


def mouse_left_down(window: Window) -> bool:
  win: Pointer[PyiGlfwWindow] = window.handle
  if win is None:
    return False
  return pyiGlfwGetMouseButton(win, PyiGlfwMouseButtonLeft) == PyiGlfwPress


def jump_charge_held(window: Window) -> bool:
  """空格或鼠标左键按住视为蓄力。"""
  return space_down(window) or mouse_left_down(window)


def cursor_pos(window: Window, out_x: Pointer[float64], out_y: Pointer[float64]) -> bool:
  """写入光标客户区坐标（像素）。"""
  win: Pointer[PyiGlfwWindow] = window.handle
  if win is None:
    return False
  pyiGlfwGetCursorPos(win, out_x, out_y)
  return True
