"""GLFW 输入：纯 Python 组合 ``ffi.glfw.glfw3``。"""
from __future__ import annotations

from py2cpp import *
from ffi.glfw.glfw3 import GLFW_PRESS, GLFWwindow_h, glfwGetKey

from .window import Window


def key_down(window: Window, key: int) -> bool:
  """``glfwGetKey`` 是否按下。"""
  win: GLFWwindow_h = window.handle
  if win == 0:
    return False
  return glfwGetKey(win, key) == GLFW_PRESS
