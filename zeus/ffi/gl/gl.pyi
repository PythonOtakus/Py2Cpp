# Zeus 手写 OpenGL 兼容配置子集；C 头：GL/gl.h（Windows 链 opengl32）。

from py2cpp.builtins import *

GL_COLOR_BUFFER_BIT: int = 16384
GL_DEPTH_BUFFER_BIT: int = 256
GL_DEPTH_TEST: int = 2929
GL_TRIANGLES: int = 4
GL_PROJECTION: int = 5889
GL_MODELVIEW: int = 5888

@native
@native_name("glClearColor")
def glClearColor(red: float64, green: float64, blue: float64, alpha: float64) -> None: ...

@native
@native_name("glClear")
def glClear(mask: int) -> None: ...

@native
@native_name("glViewport")
def glViewport(x: int, y: int, width: int, height: int) -> None: ...

@native
@native_name("glEnable")
def glEnable(cap: int) -> None: ...

@native
@native_name("glMatrixMode")
def glMatrixMode(mode: int) -> None: ...

@native
@native_name("glLoadIdentity")
def glLoadIdentity() -> None: ...

@native
@native_name("glFrustum")
def glFrustum(
  left: float64,
  right: float64,
  bottom: float64,
  top: float64,
  zNear: float64,
  zFar: float64,
) -> None: ...

@native
@native_name("glTranslatef")
def glTranslatef(x: float64, y: float64, z: float64) -> None: ...

@native
@native_name("glRotatef")
def glRotatef(angle: float64, x: float64, y: float64, z: float64) -> None: ...

@native
@native_name("glBegin")
def glBegin(mode: int) -> None: ...

@native
@native_name("glEnd")
def glEnd() -> None: ...

@native
@native_name("glColor3d")
def glColor3d(red: float64, green: float64, blue: float64) -> None: ...

@native
@native_name("glVertex3d")
def glVertex3d(x: float64, y: float64, z: float64) -> None: ...
