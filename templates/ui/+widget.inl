PY2CPP_IGNORE
#include "py2cpp/ui/widget.h"
PY2CPP_END

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <commctrl.h>

static void _ui_widget_read_edit_text(HWND ctrl, char* buf, int cap)
{
  if ((!ctrl) || (!buf) || (cap <= 0))
  {
    return;
  }
  int n = (int)GetWindowTextA(ctrl, buf, cap);
  if (n < 0)
  {
    buf[0] = '\0';
  }
}

static PyInt _ui_widget_clamp_int(PyInt value, PyInt lo, PyInt hi)
{
  if (value < lo)
  {
    return lo;
  }
  if (value > hi)
  {
    return hi;
  }
  return value;
}

PY2CPP_BEGIN_SCOPE

void UICheckBox::_sync_to_native()
{
  HWND ctrl = (HWND)(INT_PTR)handle;
  if (!ctrl)
  {
    return;
  }
  LRESULT st = SendMessageA(ctrl, BM_GETCHECK, 0, 0);
  PyBool cur = (st == BST_CHECKED);
  if (cur != checked__value)
  {
    SendMessageA(
        ctrl,
        BM_SETCHECK,
        (WPARAM)(checked__value ? BST_CHECKED : BST_UNCHECKED),
        0);
  }
}

void UILineEdit::_sync_to_native()
{
  HWND ctrl = (HWND)(INT_PTR)handle;
  if (!ctrl)
  {
    return;
  }
  char want[512];
  text__value.copy_to_span(PySpan<PyByte>((PyByte*)want, (PyInt)sizeof(want), 1));
  char cur[512];
  _ui_widget_read_edit_text(ctrl, cur, (int)sizeof(cur));
  if (strcmp(cur, want) != 0)
  {
    SetWindowTextA(ctrl, want);
  }
}

void UIIntEdit::_sync_to_native()
{
  HWND ctrl = (HWND)(INT_PTR)handle;
  if (!ctrl)
  {
    return;
  }
  char want[32];
  snprintf(want, sizeof(want), "%d", (int)value__value);
  char cur[32];
  _ui_widget_read_edit_text(ctrl, cur, (int)sizeof(cur));
  if (strcmp(cur, want) != 0)
  {
    SetWindowTextA(ctrl, want);
  }
}

void UIFloatEdit::_sync_to_native()
{
  HWND ctrl = (HWND)(INT_PTR)handle;
  if (!ctrl)
  {
    return;
  }
  char want[64];
  snprintf(want, sizeof(want), "%.6g", (double)value__value);
  char cur[64];
  _ui_widget_read_edit_text(ctrl, cur, (int)sizeof(cur));
  if (strcmp(cur, want) != 0)
  {
    SetWindowTextA(ctrl, want);
  }
}

void UISlider::_sync_to_native()
{
  HWND ctrl = (HWND)(INT_PTR)handle;
  if (!ctrl)
  {
    return;
  }
  int want = _ui_widget_clamp_int(value__value, lo, hi);
  LRESULT pos = SendMessageA(ctrl, TBM_GETPOS, 0, 0);
  if ((int)pos != want)
  {
    SendMessageA(ctrl, TBM_SETPOS, (WPARAM)TRUE, (LPARAM)want);
  }
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

void UICheckBox::_sync_to_native()
{
}

void UILineEdit::_sync_to_native()
{
}

void UIIntEdit::_sync_to_native()
{
}

void UIFloatEdit::_sync_to_native()
{
}

void UISlider::_sync_to_native()
{
}

PY2CPP_END_SCOPE

#endif
