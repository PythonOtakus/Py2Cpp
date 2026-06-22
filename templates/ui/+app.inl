PY2CPP_IGNORE
#include "py2cpp/ui/app.h"
PY2CPP_END

#include <stdio.h>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#pragma comment(lib, "user32.lib")

PY2CPP_BEGIN_SCOPE

PyBool UIApp::is_available()
{
  return true;
}

PyInt UIApp::run()
{
  MSG msg;
  while ((GetMessageA(&msg, NULL, 0, 0) > 0))
  {
    TranslateMessage(&msg);
    DispatchMessageA(&msg);
  }
  return (PyInt)0;
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

PyBool UIApp::is_available()
{
  return false;
}

PyInt UIApp::run()
{
  return (PyInt)0;
}

PY2CPP_END_SCOPE

#endif
