PY2CPP_IGNORE
#include "py2cpp/ui/input.h"
PY2CPP_END

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

PY2CPP_BEGIN_SCOPE

PyTuple<PyInt, PyInt> cursor_screen_pos()
{
  POINT pt;
  GetCursorPos(&pt);
  return PyTuple<PyInt, PyInt>((PyInt)pt.x, (PyInt)pt.y);
}

PyBool shift_down()
{
  return (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0;
}

PyBool ctrl_down()
{
  return (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

PyTuple<PyInt, PyInt> cursor_screen_pos()
{
  return PyTuple<PyInt, PyInt>(0, 0);
}

PyBool shift_down()
{
  return false;
}

PyBool ctrl_down()
{
  return false;
}

PY2CPP_END_SCOPE

#endif
