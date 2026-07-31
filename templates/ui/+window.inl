PY2CPP_IGNORE
#include "py2cpp/ui/window.h"
#include "py2cpp/ui/layout.h"
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
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "comctl32.lib")

#pragma comment(linker,"\"/manifestdependency:type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='*' publicKeyToken='6595b64144ccf1df' language='*'\"")

namespace py2cpp {
namespace ui {
namespace layout {
PyBool ui_form_on_bn_clicked(window::UIWindow& win, UINT_PTR ctrl_id);
PyBool ui_form_on_en_change(window::UIWindow& win, UINT_PTR ctrl_id);
PyBool ui_form_on_hscroll(window::UIWindow& win, HWND ctrl);
void ui_form_session_reset();
void ui_form_on_window_end(window::UIWindow& win);
} // namespace layout
PyBool ui_menu_on_command(window::UIWindow& win, UINT_PTR cmd_id);
PyBool ui_flow_on_key(window::UIWindow& win, PyInt vk);
void ui_flow_shell_on_resize(window::UIWindow& win);
} // namespace ui
} // namespace py2cpp

PY2CPP_BEGIN_SCOPE

static PyInt _ui_theme_dpi = 96;
static HFONT _ui_theme_font = NULL;
static HBRUSH _ui_theme_panel_brush = NULL;
static PyBool _ui_theme_process_ready = false;
static COLORREF _ui_theme_text = RGB(0, 0, 0);
static COLORREF _ui_theme_panel = RGB(243, 243, 243);

static COLORREF _ui_color_from_rgb(const PyTuple<PyInt, PyInt, PyInt>& rgb)
{
  return RGB(
      rgb.template get<0>(),
      rgb.template get<1>(),
      rgb.template get<2>());
}

static void _ui_theme_delete_gdi()
{
  if (_ui_theme_font)
  {
    DeleteObject(_ui_theme_font);
    _ui_theme_font = NULL;
  }
  if (_ui_theme_panel_brush)
  {
    DeleteObject(_ui_theme_panel_brush);
    _ui_theme_panel_brush = NULL;
  }
}

static void _ui_theme_ensure_font(const py2cpp::ui::style::UIStyle& style)
{
  if (_ui_theme_font)
  {
    return;
  }
  char face[LF_FACESIZE];
  style.font_name.copy_to_span(PySpan<PyByte>((PyByte*)face, (PyInt)sizeof(face), 1));
  if (!face[0])
  {
    strncpy(face, "Segoe UI", (sizeof(face) - 1));
  }
  LOGFONTA lf;
  memset(&lf, 0, sizeof(lf));
  lf.lfHeight = -MulDiv(style.font_size, _ui_theme_dpi, 96);
  lf.lfWeight = FW_NORMAL;
  lf.lfCharSet = DEFAULT_CHARSET;
  lf.lfQuality = CLEARTYPE_QUALITY;
  strncpy(lf.lfFaceName, face, (sizeof(lf.lfFaceName) - 1));
  _ui_theme_font = CreateFontIndirectA(&lf);
}

static void _ui_theme_ensure_brush()
{
  if (_ui_theme_panel_brush)
  {
    return;
  }
  _ui_theme_panel_brush = CreateSolidBrush(_ui_theme_panel);
}

PyInt ui_theme_scale(PyInt px)
{
  return MulDiv(px, _ui_theme_dpi, 96);
}

PyInt ui_theme_scale_ctx(const UIWindow& ctx, PyInt px)
{
  (void)ctx;
  return ui_theme_scale(px);
}

void ui_theme_ensure_process()
{
  if (_ui_theme_process_ready)
  {
    return;
  }
  typedef BOOL (WINAPI *SetCtxFn)(DPI_AWARENESS_CONTEXT);
  HMODULE user32 = GetModuleHandleA("user32.dll");
  if (user32)
  {
    SetCtxFn set_ctx = (SetCtxFn)GetProcAddress(user32, "SetProcessDpiAwarenessContext");
    if (set_ctx)
    {
      set_ctx(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    }
  }
  INITCOMMONCONTROLSEX icc;
  icc.dwSize = sizeof(icc);
  icc.dwICC = ICC_WIN95_CLASSES | ICC_BAR_CLASSES | ICC_STANDARD_CLASSES;
  InitCommonControlsEx(&icc);
  _ui_theme_process_ready = true;
}

void ui_theme_attach_panel(HWND hwnd, UIWindow& ctx)
{
  if (!hwnd)
  {
    return;
  }
  _ui_theme_dpi = GetDpiForWindow(hwnd);
  if (_ui_theme_dpi <= 0)
  {
    _ui_theme_dpi = 96;
  }
  _ui_theme_text = _ui_color_from_rgb(ctx.style.text_color);
  _ui_theme_panel = _ui_color_from_rgb(ctx.style.panel_color);
  _ui_theme_delete_gdi();
  _ui_theme_ensure_font(ctx.style);
  _ui_theme_ensure_brush();
  SendMessageA(hwnd, WM_SETFONT, (WPARAM)_ui_theme_font, TRUE);
  HMODULE dwm = LoadLibraryA("dwmapi.dll");
  if (dwm)
  {
    typedef HRESULT (WINAPI *DwmSetFn)(HWND, DWORD, LPCVOID, DWORD);
    DwmSetFn dwm_set = (DwmSetFn)GetProcAddress(dwm, "DwmSetWindowAttribute");
    if (dwm_set)
    {
      const int corner_pref = 2;
      dwm_set(hwnd, 33, &corner_pref, sizeof(corner_pref));
    }
    FreeLibrary(dwm);
  }
}

void ui_theme_apply_font(HWND hwnd)
{
  if ((!hwnd) || (!_ui_theme_font))
  {
    return;
  }
  SendMessageA(hwnd, WM_SETFONT, (WPARAM)_ui_theme_font, TRUE);
}

void ui_theme_layout_metrics(
    const UIWindow& ctx,
    PyInt* pad_x,
    PyInt* label_w,
    PyInt* row_h,
    PyInt* row_spacing,
    PyInt* slider_h,
    PyInt* edit_w,
    PyInt* edit_h,
    PyInt* slider_w,
    PyInt* form_spacing)
{
  const py2cpp::ui::style::UIStyle& st = ctx.style;
  if (pad_x)
  {
    *pad_x = ui_theme_scale(st.margin.template get<0>() + st.form_origin_x);
  }
  if (label_w)
  {
    *label_w = ui_theme_scale(st.label_size.template get<0>());
  }
  if (row_h)
  {
    *row_h = ui_theme_scale(st.label_size.template get<1>());
  }
  if (row_spacing)
  {
    *row_spacing = ui_theme_scale(st.row_spacing);
  }
  if (slider_h)
  {
    *slider_h = ui_theme_scale(st.slider_size.template get<1>());
  }
  if (edit_w)
  {
    *edit_w = ui_theme_scale(st.edit_size.template get<0>());
  }
  if (edit_h)
  {
    *edit_h = ui_theme_scale(st.edit_size.template get<1>());
  }
  if (slider_w)
  {
    *slider_w = ui_theme_scale(st.slider_size.template get<0>());
  }
  if (form_spacing)
  {
    *form_spacing = ui_theme_scale(st.form_spacing);
  }
}

HBRUSH ui_theme_panel_brush()
{
  _ui_theme_ensure_brush();
  return _ui_theme_panel_brush;
}

COLORREF ui_theme_text_color()
{
  return _ui_theme_text;
}

COLORREF ui_theme_panel_color()
{
  return _ui_theme_panel;
}

HBRUSH ui_theme_on_ctl_color(HDC hdc)
{
  if (!hdc)
  {
    return NULL;
  }
  SetBkColor(hdc, _ui_theme_panel);
  SetTextColor(hdc, _ui_theme_text);
  return ui_theme_panel_brush();
}

HBRUSH ui_theme_on_ctl_color_chrome(HDC hdc)
{
  if (!hdc)
  {
    return NULL;
  }
  SetBkMode(hdc, TRANSPARENT);
  SetTextColor(hdc, _ui_theme_text);
  return (HBRUSH)GetStockObject(NULL_BRUSH);
}

HBRUSH ui_theme_on_ctl_color_static(HDC hdc, HWND ctrl)
{
  if (!hdc)
  {
    return NULL;
  }
  if (ctrl)
  {
    char cls[64];
    if ((GetClassNameA(ctrl, cls, (int)sizeof(cls)) > 0)
        && (strcmp(cls, "msctls_trackbar32") == 0))
        {
      return NULL;
    }
  }
  return ui_theme_on_ctl_color_chrome(hdc);
}

PY2CPP_END_SCOPE


static const char* _ui_panel_class = "Py2CppUIPanel";
static PyBool _ui_panel_registered = false;

static HWND _ui_ctx_hwnd(const UIWindow& self)
{
  return (HWND)(INT_PTR)self.handle;
}

static void _ui_set_ctx_hwnd(UIWindow& self, HWND hwnd)
{
  self.handle = (PyInt64)((INT_PTR)hwnd);
}

static LRESULT CALLBACK _ui_panel_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
  switch (msg)
  {
    case WM_CTLCOLOREDIT: {
      HDC hdc = (HDC)wp;
      HBRUSH brush = ui_theme_on_ctl_color(hdc);
      if (brush)
      {
        return (LRESULT)brush;
      }
      break;
    }
    case WM_CTLCOLORSTATIC: {
      HDC hdc = (HDC)wp;
      HWND ctrl = (HWND)lp;
      HBRUSH brush = ui_theme_on_ctl_color_static(hdc, ctrl);
      if (brush)
      {
        return (LRESULT)brush;
      }
      break;
    }
    case WM_CTLCOLORBTN: {
      HDC hdc = (HDC)wp;
      HBRUSH brush = ui_theme_on_ctl_color_chrome(hdc);
      if (brush)
      {
        return (LRESULT)brush;
      }
      break;
    }
    case WM_COMMAND: {
UIWindow* ctx = (UIWindow*)GetWindowLongPtrA(hwnd, GWLP_USERDATA);
      if (ctx)
      {
        if (py2cpp::ui::ui_menu_on_command(*ctx, (UINT_PTR)LOWORD(wp)))
        {
          return 0;
        }
        if (HIWORD(wp) == BN_CLICKED)
        {
          if (py2cpp::ui::layout::ui_form_on_bn_clicked(*ctx, (UINT_PTR)LOWORD(wp)))
          {
            return 0;
          }
        } else if (HIWORD(wp) == EN_CHANGE)
        {
          if (py2cpp::ui::layout::ui_form_on_en_change(*ctx, (UINT_PTR)LOWORD(wp)))
          {
            return 0;
          }
        }
      }
      break;
    }
    case WM_KEYDOWN: {
      UIWindow* ctx = (UIWindow*)GetWindowLongPtrA(hwnd, GWLP_USERDATA);
      if (ctx)
      {
        if (py2cpp::ui::ui_flow_on_key(*ctx, (PyInt)(UINT)wp))
        {
          return 0;
        }
      }
      break;
    }
    case WM_HSCROLL: {
UIWindow* ctx = (UIWindow*)GetWindowLongPtrA(hwnd, GWLP_USERDATA);
      if (ctx)
      {
        if (py2cpp::ui::layout::ui_form_on_hscroll(*ctx, (HWND)lp))
        {
          return 0;
        }
      }
      break;
    }
    case WM_SIZE: {
UIWindow* ctx = (UIWindow*)GetWindowLongPtrA(hwnd, GWLP_USERDATA);
      if (ctx)
      {
        py2cpp::ui::ui_flow_shell_on_resize(*ctx);
      }
      break;
    }
    case WM_DESTROY: {
UIWindow* ctx = (UIWindow*)GetWindowLongPtrA(hwnd, GWLP_USERDATA);
      if (ctx)
      {
        _ui_set_ctx_hwnd(*ctx, NULL);
      }
      PostQuitMessage(0);
      return 0;
    }
    case WM_CLOSE:
      DestroyWindow(hwnd);
      return 0;
    case WM_MOUSEWHEEL: {
      POINT pt;
      pt.x = (LONG)(short)LOWORD(lp);
      pt.y = (LONG)(short)HIWORD(lp);
      ScreenToClient(hwnd, &pt);
      HWND child = ChildWindowFromPointEx(hwnd, pt, CWP_SKIPINVISIBLE);
      if (child && child != hwnd)
      {
        return SendMessageA(child, msg, wp, lp);
      }
      break;
    }
    default:
      break;
  }
  return DefWindowProcA(hwnd, msg, wp, lp);
}

static void _ui_ensure_class()
{
  if (_ui_panel_registered)
  {
    return;
  }
  ui_theme_ensure_process();
  WNDCLASSA wc;
  memset(&wc, 0, sizeof(wc));
  wc.lpfnWndProc = _ui_panel_wndproc;
  wc.hInstance = GetModuleHandleA(NULL);
  wc.lpszClassName = _ui_panel_class;
  wc.hCursor = LoadCursorA(NULL, IDC_ARROW);
  wc.hbrBackground = ui_theme_panel_brush();
  RegisterClassA(&wc);
  _ui_panel_registered = true;
}

PY2CPP_BEGIN_SCOPE

void UIWindow::_apply_title()
{
  HWND panel = _ui_ctx_hwnd(*this);
  if (!panel)
  {
    return;
  }
  char tbuf[512];
  title__value.copy_to_span(PySpan<PyByte>((PyByte*)tbuf, (PyInt)sizeof(tbuf), 1));
  SetWindowTextA(panel, tbuf);
}

void UIWindow::show(PyInt width, PyInt height)
{
  py2cpp::ui::layout::ui_form_session_reset();
  _ui_ensure_class();
  char tbuf[512];
  title__value.copy_to_span(PySpan<PyByte>((PyByte*)tbuf, (PyInt)sizeof(tbuf), 1));
  PyBool defer_w = (width < 0);
  PyBool defer_h = (height < 0);
  int w = width;
  int h = height;
  if (defer_w)
  {
    w = 240;
  } else if (w < 240)
  {
    w = 240;
  }
  if (defer_h)
  {
    h = 160;
  } else if (h < 160)
  {
    h = 160;
  }
  RECT r;
  r.left = 0;
  r.top = 0;
  r.right = w;
  r.bottom = h;
  AdjustWindowRect(&r, WS_OVERLAPPEDWINDOW, FALSE);
  int win_w = r.right - r.left;
  int win_h = r.bottom - r.top;
  UINT show = SW_SHOW;
  if (defer_w || defer_h)
  {
    show = SW_HIDE;
  }
  HWND panel = CreateWindowExA(
      0,
      _ui_panel_class,
      tbuf,
      WS_OVERLAPPEDWINDOW,
      CW_USEDEFAULT,
      CW_USEDEFAULT,
      win_w,
      win_h,
      NULL,
      NULL,
      GetModuleHandleA(NULL),
      NULL);
  _ui_set_ctx_hwnd(*this, panel);
  SetWindowLongPtrA(panel, GWLP_USERDATA, (LONG_PTR)this);
  ui_theme_attach_panel(panel, *this);
  next_y = ui_theme_scale_ctx(
      *this, style.margin.template get<1>() + style.form_origin_y);
  active_form = (PyInt64)0;
  ShowWindow(panel, show);
  UpdateWindow(panel);
}

void UIWindow::resize(PyInt width, PyInt height)
{
  HWND panel = _ui_ctx_hwnd(*this);
  if (!panel)
  {
    return;
  }
  if ((width >= 0) && (height >= 0))
  {
    return;
  }
  PyInt pad_x = 0;
  PyInt label_w = 0;
  PyInt row_h = 0;
  PyInt row_spacing = 0;
  PyInt slider_h = 0;
  PyInt edit_w = 0;
  PyInt edit_h = 0;
  PyInt slider_w = 0;
  PyInt form_spacing = 0;
  ui_theme_layout_metrics(
      *this,
      &pad_x,
      &label_w,
      &row_h,
      &row_spacing,
      &slider_h,
      &edit_w,
      &edit_h,
      &slider_w,
      &form_spacing);
  (void)row_h;
  (void)row_spacing;
  (void)slider_h;
  (void)edit_h;
  PyInt box_w = ui_theme_scale_ctx(*this, style.checkbox_size.template get<0>());
  PyInt ctrl_w = edit_w;
  if (slider_w > ctrl_w)
  {
    ctrl_w = slider_w;
  }
  if (box_w > ctrl_w)
  {
    ctrl_w = box_w;
  }
  PyInt btn_w = ui_theme_scale_ctx(*this, style.button_size.template get<0>());
  if (btn_w > ctrl_w)
  {
    ctrl_w = btn_w;
  }
  int client_w = width;
  int client_h = height;
  if (client_w < 0)
  {
    client_w = pad_x + label_w + form_spacing + ctrl_w + pad_x;
    if (client_w < 240)
    {
      client_w = 240;
    }
  }
  if (client_h < 0)
  {
    PyInt bottom = ui_theme_scale_ctx(*this, style.margin.template get<1>());
    client_h = next_y + bottom;
    if (client_h < 160)
    {
      client_h = 160;
    }
  }
  RECT r;
  r.left = 0;
  r.top = 0;
  r.right = client_w;
  r.bottom = client_h;
  AdjustWindowRect(&r, WS_OVERLAPPEDWINDOW, FALSE);
  int win_w = r.right - r.left;
  int win_h = r.bottom - r.top;
  SetWindowPos(
      panel,
      NULL,
      0,
      0,
      win_w,
      win_h,
      SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED);
  ShowWindow(panel, SW_SHOW);
  UpdateWindow(panel);
}

void UIWindow::close()
{
  py2cpp::ui::layout::ui_form_on_window_end(*this);
  HWND panel = _ui_ctx_hwnd(*this);
  if (panel)
  {
    DestroyWindow(panel);
    _ui_set_ctx_hwnd(*this, NULL);
  }
}

PyTuple<PyInt, PyInt> UIWindow::client_origin_screen()
{
  HWND panel = _ui_ctx_hwnd(*this);
  if (!panel)
  {
    return PyTuple<PyInt, PyInt>(0, 0);
  }
  POINT pt;
  pt.x = 0;
  pt.y = 0;
  ClientToScreen(panel, &pt);
  return PyTuple<PyInt, PyInt>((PyInt)pt.x, (PyInt)pt.y);
}

PyTuple<PyInt, PyInt> UIWindow::client_size()
{
  HWND panel = _ui_ctx_hwnd(*this);
  if (!panel)
  {
    return PyTuple<PyInt, PyInt>(0, 0);
  }
  RECT rc;
  GetClientRect(panel, &rc);
  return PyTuple<PyInt, PyInt>((PyInt)(rc.right - rc.left), (PyInt)(rc.bottom - rc.top));
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

void UIWindow::_apply_title()
{
}

void UIWindow::show(PyInt width, PyInt height)
{
  (void)width;
  (void)height;
  handle = (PyInt64)0;
  next_y = (PyInt)10;
  active_form = (PyInt64)0;
}

void UIWindow::resize(PyInt width, PyInt height)
{
  (void)width;
  (void)height;
}

void UIWindow::close()
{
  handle = (PyInt64)0;
  active_form = (PyInt64)0;
}

PyTuple<PyInt, PyInt> UIWindow::client_origin_screen()
{
  return PyTuple<PyInt, PyInt>(0, 0);
}

PyTuple<PyInt, PyInt> UIWindow::client_size()
{
  return PyTuple<PyInt, PyInt>(0, 0);
}

PY2CPP_END_SCOPE

#endif
