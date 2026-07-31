"""GLFW 输入：纯 Python 组合 ``ffi.glfw.glfw3``。"""
from __future__ import annotations

from py2cpp import *
from ffi.glfw.glfw3 import (
  GLFW_KEY_SPACE,
  GLFW_MOUSE_BUTTON_LEFT,
  GLFW_PRESS,
  GLFWwindow_h,
  glfwGetKey,
  glfwGetMouseButton,
)

from .window import Window


def key_down(window: Window, key: int) -> bool:
  """``glfwGetKey`` 是否按下。"""
  win: GLFWwindow_h = window.handle
  if win == 0:
    return False
  return glfwGetKey(win, key) == GLFW_PRESS


def space_down(window: Window) -> bool:
  return key_down(window, GLFW_KEY_SPACE)


def mouse_left_down(window: Window) -> bool:
  win: GLFWwindow_h = window.handle
  if win == 0:
    return False
  return glfwGetMouseButton(win, GLFW_MOUSE_BUTTON_LEFT) == GLFW_PRESS


def jump_charge_held(window: Window) -> bool:
  """空格或鼠标左键按住视为蓄力。"""
  return space_down(window) or mouse_left_down(window)
