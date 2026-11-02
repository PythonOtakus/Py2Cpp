PY2CPP_IGNORE
#include "py2cpp/ui/tooltip.h"
#include "py2cpp/ui/window.h"
PY2CPP_END

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows.h"
#include "ffi/windows/commctrl.h"

PY2CPP_BEGIN_SCOPE

void PyUITooltipHost::attach(window::PyUIWindow& win)
{
  InitCommonControls();
  HWND parent = (HWND)(INT_PTR)win.handle;
  if (!parent)
  {
    return;
  }
  HWND tip = CreateWindowExA(
      0,
      TOOLTIPS_CLASSA,
      NULL,
      WS_POPUP | TTS_NOPREFIX | TTS_ALWAYSTIP,
      CW_USEDEFAULT,
      CW_USEDEFAULT,
      CW_USEDEFAULT,
      CW_USEDEFAULT,
      parent,
      NULL,
      GetModuleHandleA(NULL),
      NULL);
  this->handle = (PyInt64)((INT_PTR)tip);
}

void PyUITooltipHost::showAtClient(window::PyUIWindow& win, PyStr text, PyInt cx, PyInt cy)
{
  HWND tip = (HWND)(INT_PTR)this->handle;
  HWND parent = (HWND)(INT_PTR)win.handle;
  if ((!tip) || (!parent))
  {
    return;
  }
  char tbuf[512];
  text.copyToSpanUtf8(PySpan<PyByte>((PyByte*)tbuf, (PyInt)sizeof(tbuf), 1));
  TOOLINFOA ti = {};
  ti.cbSize = sizeof(ti);
  ti.uFlags = TTF_TRACK | TTF_SUBCLASS;
  ti.hwnd = parent;
  ti.lpszText = tbuf;
  SendMessageA(tip, TTM_ADDTOOLA, 0, (LPARAM)&ti);
  SendMessageA(tip, TTM_TRACKPOSITION, 0, (LPARAM)MAKELONG(cx + 12, cy + 20));
  SendMessageA(tip, TTM_TRACKACTIVATE, (WPARAM)TRUE, (LPARAM)&ti);
}

void PyUITooltipHost::hide()
{
  HWND tip = (HWND)(INT_PTR)this->handle;
  if (!tip)
  {
    return;
  }
  TOOLINFOA ti = {};
  ti.cbSize = sizeof(ti);
  SendMessageA(tip, TTM_TRACKACTIVATE, (WPARAM)FALSE, (LPARAM)&ti);
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

void PyUITooltipHost::attach(window::PyUIWindow& win)
{
  (void)win;
}

void PyUITooltipHost::showAtClient(window::PyUIWindow& win, PyStr text, PyInt cx, PyInt cy)
{
  (void)win;
  (void)text;
  (void)cx;
  (void)cy;
}

void PyUITooltipHost::hide()
{
}

PY2CPP_END_SCOPE

#endif
