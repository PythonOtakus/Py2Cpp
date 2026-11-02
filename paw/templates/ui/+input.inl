PY2CPP_IGNORE
#include "py2cpp/ui/input.h"
PY2CPP_END

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows.h"

PY2CPP_BEGIN_SCOPE

PyTuple<PyInt, PyInt> cursorScreenPos()
{
  POINT pt;
  GetCursorPos(&pt);
  return PyTuple<PyInt, PyInt>((PyInt)pt.x, (PyInt)pt.y);
}

PyBool shiftDown()
{
  return (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0;
}

PyBool ctrlDown()
{
  return (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

PyTuple<PyInt, PyInt> cursorScreenPos()
{
  return PyTuple<PyInt, PyInt>(0, 0);
}

PyBool shiftDown()
{
  return false;
}

PyBool ctrlDown()
{
  return false;
}

PY2CPP_END_SCOPE

#endif
