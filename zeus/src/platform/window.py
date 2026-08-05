"""GLFW 窗口：纯 Python 组合 ``ffi.glfw.glfw3``。"""
from __future__ import annotations

from py2cpp import *
from ffi.glfw.glfw3 import (
  Pyi_GLFW_CONTEXT_VERSION_MAJOR,
  Pyi_GLFW_CONTEXT_VERSION_MINOR,
  Pyi_GLFW_DECORATED,
  Pyi_GLFW_FALSE,
  Pyi_GLFW_TRUE,
  Pyi_GLFW_VISIBLE,
  Pyi_GLFWwindow,
  Pyi_glfwCreateWindow,
  Pyi_glfwDestroyWindow,
  Pyi_glfwHideWindow,
  Pyi_glfwInit,
  Pyi_glfwMakeContextCurrent,
  Pyi_glfwPollEvents,
  Pyi_glfwSetWindowPos,
  Pyi_glfwSetWindowSize,
  Pyi_glfwShowWindow,
  Pyi_glfwSwapBuffers,
  Pyi_glfwTerminate,
  Pyi_glfwWindowHint,
  Pyi_glfwWindowShouldClose,
)


_glfw_refcount: int = 0


@refcount
class Window:
  """GLFW 顶层窗口；``handle`` 为 ``GLFWwindow*``。"""

  handle: Pointer[Pyi_GLFWwindow] = None
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
      if Pyi_glfwInit() == 0:
        return False
    _glfw_refcount += 1
    Pyi_glfwWindowHint(Pyi_GLFW_CONTEXT_VERSION_MAJOR, 2)
    Pyi_glfwWindowHint(Pyi_GLFW_CONTEXT_VERSION_MINOR, 1)
    vis: int = Pyi_GLFW_FALSE if hidden else Pyi_GLFW_TRUE
    Pyi_glfwWindowHint(Pyi_GLFW_VISIBLE, vis)
    dec: int = Pyi_GLFW_TRUE if decorated else Pyi_GLFW_FALSE
    Pyi_glfwWindowHint(Pyi_GLFW_DECORATED, dec)
    win: Pointer[Pyi_GLFWwindow] = Pyi_glfwCreateWindow(
      width, height, title, None, None
    )
    if win is None:
      _glfw_refcount -= 1
      if _glfw_refcount == 0:
        Pyi_glfwTerminate()
      return False
    self.handle = win
    self.width = width
    self.height = height
    self.title = new(title)
    self.should_close = False
    Pyi_glfwMakeContextCurrent(win)
    return True

  def set_bounds_screen(self, x: int, y: int, width: int, height: int) -> None:
    """屏幕坐标下移动/缩放（无边框视口对齐主窗中栏）。"""
    win: Pointer[Pyi_GLFWwindow] = self.handle
    if win is None:
      return
    if width < 1:
      width = 1
    if height < 1:
      height = 1
    self.width = width
    self.height = height
    Pyi_glfwSetWindowPos(win, x, y)
    Pyi_glfwSetWindowSize(win, width, height)

  def show_window(self) -> None:
    win: Pointer[Pyi_GLFWwindow] = self.handle
    if win is not None:
      Pyi_glfwShowWindow(win)

  def hide_window(self) -> None:
    win: Pointer[Pyi_GLFWwindow] = self.handle
    if win is not None:
      Pyi_glfwHideWindow(win)

  def poll(self) -> None:
    Pyi_glfwPollEvents()
    win: Pointer[Pyi_GLFWwindow] = self.handle
    if win is not None:
      self.should_close = Pyi_glfwWindowShouldClose(win) != 0

  def swap(self) -> None:
    win: Pointer[Pyi_GLFWwindow] = self.handle
    if win is not None:
      Pyi_glfwSwapBuffers(win)

  def destroy(self) -> None:
    global _glfw_refcount
    win: Pointer[Pyi_GLFWwindow] = self.handle
    if win is not None:
      Pyi_glfwDestroyWindow(win)
      self.handle = None
      _glfw_refcount -= 1
      if _glfw_refcount <= 0:
        _glfw_refcount = 0
        Pyi_glfwTerminate()

  def make_current(self) -> None:
    win: Pointer[Pyi_GLFWwindow] = self.handle
    if win is not None:
      Pyi_glfwMakeContextCurrent(win)
