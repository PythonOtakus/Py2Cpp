"""GLFW 输入：纯 Python 组合 ``ffi.glfw.glfw3``。"""
from __future__ import annotations

from py2cpp import *
from ffi.glfw.glfw3 import (
  Pyi_GLFW_KEY_SPACE,
  Pyi_GLFW_MOUSE_BUTTON_LEFT,
  Pyi_GLFW_PRESS,
  Pyi_GLFWwindow,
  Pyi_glfwGetCursorPos,
  Pyi_glfwGetKey,
  Pyi_glfwGetMouseButton,
)

from .window import Window


def key_down(window: Window, key: int) -> bool:
  """``glfwGetKey`` 是否按下。"""
  win: Pointer[Pyi_GLFWwindow] = window.handle
  if win is None:
    return False
  return Pyi_glfwGetKey(win, key) == Pyi_GLFW_PRESS


def space_down(window: Window) -> bool:
  return key_down(window, Pyi_GLFW_KEY_SPACE)


def mouse_left_down(window: Window) -> bool:
  win: Pointer[Pyi_GLFWwindow] = window.handle
  if win is None:
    return False
  return Pyi_glfwGetMouseButton(win, Pyi_GLFW_MOUSE_BUTTON_LEFT) == Pyi_GLFW_PRESS


def jump_charge_held(window: Window) -> bool:
  """空格或鼠标左键按住视为蓄力。"""
  return space_down(window) or mouse_left_down(window)


def cursor_pos(window: Window, out_x: Pointer[float64], out_y: Pointer[float64]) -> bool:
  """写入光标客户区坐标（像素）。"""
  win: Pointer[Pyi_GLFWwindow] = window.handle
  if win is None:
    return False
  Pyi_glfwGetCursorPos(win, out_x, out_y)
  return True
