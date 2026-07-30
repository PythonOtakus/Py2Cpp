# Zeus 手写 GLFW 子集（非全量生成）；业务经纯 Python 组合调用。
# Spec: docs/c-ffi-pyi.md；C 头：GLFW/glfw3.h

from py2cpp.builtins import *

type GLFWwindow_h = uint64  # C: GLFWwindow
type GLFWmonitor_h = uint64  # C: GLFWmonitor

GLFW_FALSE: int = 0
GLFW_TRUE: int = 1
GLFW_VISIBLE: int = 131076
GLFW_CONTEXT_VERSION_MAJOR: int = 139266
GLFW_CONTEXT_VERSION_MINOR: int = 139267
GLFW_PRESS: int = 1
GLFW_RELEASE: int = 0
GLFW_KEY_ESCAPE: int = 256

@native
@native_name("glfwInit")
def glfwInit() -> int: ...

@native
@native_name("glfwTerminate")
def glfwTerminate() -> None: ...

@native
@native_name("glfwWindowHint")
def glfwWindowHint(hint: int, value: int) -> None: ...

@native
@native_name("glfwCreateWindow")
def glfwCreateWindow(
  width: int,
  height: int,
  title: c_str,
  monitor: GLFWmonitor_h,
  share: GLFWwindow_h,
) -> GLFWwindow_h: ...

@native
@native_name("glfwDestroyWindow")
def glfwDestroyWindow(window: GLFWwindow_h) -> None: ...

@native
@native_name("glfwMakeContextCurrent")
def glfwMakeContextCurrent(window: GLFWwindow_h) -> None: ...

@native
@native_name("glfwSwapBuffers")
def glfwSwapBuffers(window: GLFWwindow_h) -> None: ...

@native
@native_name("glfwPollEvents")
def glfwPollEvents() -> None: ...

@native
@native_name("glfwWindowShouldClose")
def glfwWindowShouldClose(window: GLFWwindow_h) -> int: ...

@native
@native_name("glfwGetKey")
def glfwGetKey(window: GLFWwindow_h, key: int) -> int: ...
