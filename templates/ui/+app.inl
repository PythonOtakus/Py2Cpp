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

PyBool PyUIApp::isAvailable()
{
  return true;
}

PyInt PyUIApp::run()
{
  MSG msg;
  while ((GetMessageA(&msg, NULL, 0, 0) > 0))
  {
    TranslateMessage(&msg);
    DispatchMessageA(&msg);
  }
  return (PyInt)0;
}

PyInt PyUIApp::pump()
{
  MSG msg;
  if (!PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE))
  {
    MsgWaitForMultipleObjects(0, NULL, FALSE, 16, QS_ALLINPUT);
    if (!PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE))
    {
      return (PyInt)2;
    }
  }
  if (msg.message == WM_QUIT)
  {
    return (PyInt)0;
  }
  TranslateMessage(&msg);
  DispatchMessageA(&msg);
  return (PyInt)1;
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

PyBool PyUIApp::isAvailable()
{
  return false;
}

PyInt PyUIApp::run()
{
  return (PyInt)0;
}

PyInt PyUIApp::pump()
{
  return (PyInt)0;
}

PY2CPP_END_SCOPE

#endif
