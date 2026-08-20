"""GLFW 窗口：纯 Python 组合 ``ffi.glfw.glfw3``。"""
from __future__ import annotations

from py2cpp import *
from ffi.glfw.glfw3 import (
  PyiGlfwContextVersionMajor,
  PyiGlfwContextVersionMinor,
  PyiGlfwDecorated,
  PyiGlfwFalse,
  PyiGlfwTrue,
  PyiGlfwVisible,
  PyiGlfwWindow,
  pyiGlfwCreateWindow,
  pyiGlfwDestroyWindow,
  pyiGlfwHideWindow,
  pyiGlfwInit,
  pyiGlfwMakeContextCurrent,
  pyiGlfwPollEvents,
  pyiGlfwSetWindowPos,
  pyiGlfwSetWindowSize,
  pyiGlfwShowWindow,
  pyiGlfwSwapBuffers,
  pyiGlfwTerminate,
  pyiGlfwWindowHint,
  pyiGlfwWindowShouldClose,
)


_glfw_refcount: int = 0


@refcount
class Window:
  """GLFW 顶层窗口；``handle`` 为 ``GLFWwindow*``。"""

  handle: Pointer[PyiGlfwWindow] = None
  width: int = 0
  height: int = 0
  title: str = "Zeus"
  should_close: bool = False

  def create(self, width: int, height: int, title: utf8ptr, hidden: bool) -> bool:
    """创建 OpenGL 上下文窗口；``hidden`` 时不可见（测例用）。"""
    return self._create(width, height, title, hidden, True)

  def create_viewport(self, width: int, height: int, title: utf8ptr) -> bool:
    """无边框 Scene View 窗（由编辑器壳对齐到主窗中栏）。"""
    return self._create(width, height, title, False, False)

  def _create(
    self, width: int, height: int, title: utf8ptr, hidden: bool, decorated: bool
  ) -> bool:
    global _glfw_refcount
    if _glfw_refcount == 0:
      if pyiGlfwInit() == 0:
        return False
    _glfw_refcount += 1
    pyiGlfwWindowHint(PyiGlfwContextVersionMajor, 2)
    pyiGlfwWindowHint(PyiGlfwContextVersionMinor, 1)
    vis: int = PyiGlfwFalse if hidden else PyiGlfwTrue
    pyiGlfwWindowHint(PyiGlfwVisible, vis)
    dec: int = PyiGlfwTrue if decorated else PyiGlfwFalse
    pyiGlfwWindowHint(PyiGlfwDecorated, dec)
    win: Pointer[PyiGlfwWindow] = pyiGlfwCreateWindow(
      width, height, title, None, None
    )
    if win is None:
      _glfw_refcount -= 1
      if _glfw_refcount == 0:
        pyiGlfwTerminate()
      return False
    self.handle = win
    self.width = width
    self.height = height
    self.title = new(title)
    self.should_close = False
    pyiGlfwMakeContextCurrent(win)
    return True

  def set_bounds_screen(self, x: int, y: int, width: int, height: int) -> None:
    """屏幕坐标下移动/缩放（无边框视口对齐主窗中栏）。"""
    win: Pointer[PyiGlfwWindow] = self.handle
    if win is None:
      return
    if width < 1:
      width = 1
    if height < 1:
      height = 1
    self.width = width
    self.height = height
    pyiGlfwSetWindowPos(win, x, y)
    pyiGlfwSetWindowSize(win, width, height)

  def show_window(self) -> None:
    win: Pointer[PyiGlfwWindow] = self.handle
    if win is not None:
      pyiGlfwShowWindow(win)

  def hide_window(self) -> None:
    win: Pointer[PyiGlfwWindow] = self.handle
    if win is not None:
      pyiGlfwHideWindow(win)

  def poll(self) -> None:
    pyiGlfwPollEvents()
    win: Pointer[PyiGlfwWindow] = self.handle
    if win is not None:
      self.should_close = pyiGlfwWindowShouldClose(win) != 0

  def swap(self) -> None:
    win: Pointer[PyiGlfwWindow] = self.handle
    if win is not None:
      pyiGlfwSwapBuffers(win)

  def destroy(self) -> None:
    global _glfw_refcount
    win: Pointer[PyiGlfwWindow] = self.handle
    if win is not None:
      pyiGlfwDestroyWindow(win)
      self.handle = None
      _glfw_refcount -= 1
      if _glfw_refcount <= 0:
        _glfw_refcount = 0
        pyiGlfwTerminate()

  def make_current(self) -> None:
    win: Pointer[PyiGlfwWindow] = self.handle
    if win is not None:
      pyiGlfwMakeContextCurrent(win)
