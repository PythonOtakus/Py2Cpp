"""GLFW 窗口：纯 Python 组合 ``ffi.glfw.glfw3``。"""
from __future__ import annotations

from py2cpp import *
from ffi.glfw.glfw3 import (
  GLFW_CONTEXT_VERSION_MAJOR,
  GLFW_CONTEXT_VERSION_MINOR,
  GLFW_FALSE,
  GLFW_TRUE,
  GLFW_VISIBLE,
  GLFWwindow_h,
  glfwCreateWindow,
  glfwDestroyWindow,
  glfwInit,
  glfwMakeContextCurrent,
  glfwPollEvents,
  glfwSwapBuffers,
  glfwTerminate,
  glfwWindowHint,
  glfwWindowShouldClose,
)


_glfw_refcount: int = 0


@refcount
class Window:
  """GLFW 顶层窗口；句柄存 ``handle``（``GLFWwindow*`` 作 ``uint64``）。"""

  handle: uint64 = 0
  width: int = 0
  height: int = 0
  title: str = "Zeus"
  should_close: bool = False

  def create(self, width: int, height: int, title: c_str, hidden: bool) -> bool:
    """创建 OpenGL 上下文窗口；``hidden`` 时不可见（测例用）。"""
    global _glfw_refcount
    if _glfw_refcount == 0:
      if glfwInit() == 0:
        return False
    _glfw_refcount += 1
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 2)
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 1)
    vis: int = GLFW_FALSE if hidden else GLFW_TRUE
    glfwWindowHint(GLFW_VISIBLE, vis)
    win: GLFWwindow_h = glfwCreateWindow(width, height, title, 0, 0)
    if win == 0:
      _glfw_refcount -= 1
      if _glfw_refcount == 0:
        glfwTerminate()
      return False
    self.handle = win
    self.width = width
    self.height = height
    self.title = new(title)
    self.should_close = False
    glfwMakeContextCurrent(win)
    return True

  def poll(self) -> None:
    glfwPollEvents()
    win: GLFWwindow_h = self.handle
    if win != 0:
      self.should_close = glfwWindowShouldClose(win) != 0

  def swap(self) -> None:
    win: GLFWwindow_h = self.handle
    if win != 0:
      glfwSwapBuffers(win)

  def destroy(self) -> None:
    global _glfw_refcount
    win: GLFWwindow_h = self.handle
    if win != 0:
      glfwDestroyWindow(win)
      self.handle = 0
      _glfw_refcount -= 1
      if _glfw_refcount <= 0:
        _glfw_refcount = 0
        glfwTerminate()

  def make_current(self) -> None:
    win: GLFWwindow_h = self.handle
    if win != 0:
      glfwMakeContextCurrent(win)
