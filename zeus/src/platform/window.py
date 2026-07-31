"""GLFW 窗口：纯 Python 组合 ``ffi.glfw.glfw3``。"""
from __future__ import annotations

from py2cpp import *
from ffi.glfw.glfw3 import (
  GLFW_CONTEXT_VERSION_MAJOR,
  GLFW_CONTEXT_VERSION_MINOR,
  GLFW_DECORATED,
  GLFW_FALSE,
  GLFW_TRUE,
  GLFW_VISIBLE,
  GLFWwindow_h,
  glfwCreateWindow,
  glfwDestroyWindow,
  glfwHideWindow,
  glfwInit,
  glfwMakeContextCurrent,
  glfwPollEvents,
  glfwSetWindowPos,
  glfwSetWindowSize,
  glfwShowWindow,
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
    return self._create(width, height, title, hidden, True)

  def create_viewport(self, width: int, height: int, title: c_str) -> bool:
    """无边框 Scene View 窗（由编辑器壳对齐到主窗中栏）。"""
    return self._create(width, height, title, False, False)

  def _create(
    self, width: int, height: int, title: c_str, hidden: bool, decorated: bool
  ) -> bool:
    global _glfw_refcount
    if _glfw_refcount == 0:
      if glfwInit() == 0:
        return False
    _glfw_refcount += 1
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 2)
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 1)
    vis: int = GLFW_FALSE if hidden else GLFW_TRUE
    glfwWindowHint(GLFW_VISIBLE, vis)
    dec: int = GLFW_TRUE if decorated else GLFW_FALSE
    glfwWindowHint(GLFW_DECORATED, dec)
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

  def set_bounds_screen(self, x: int, y: int, width: int, height: int) -> None:
    """屏幕坐标下移动/缩放（无边框视口对齐主窗中栏）。"""
    win: GLFWwindow_h = self.handle
    if win == 0:
      return
    if width < 1:
      width = 1
    if height < 1:
      height = 1
    self.width = width
    self.height = height
    glfwSetWindowPos(win, x, y)
    glfwSetWindowSize(win, width, height)

  def show_window(self) -> None:
    win: GLFWwindow_h = self.handle
    if win != 0:
      glfwShowWindow(win)

  def hide_window(self) -> None:
    win: GLFWwindow_h = self.handle
    if win != 0:
      glfwHideWindow(win)

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
