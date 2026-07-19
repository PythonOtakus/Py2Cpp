PY2CPP_IGNORE
#include "py2cpp/ui/canvas.h"
#include "py2cpp/ui/window.h"
PY2CPP_END

#include <math.h>
#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <objidl.h>
#include <gdiplus.h>
#pragma comment(lib, "gdiplus.lib")

static const char* _ui_canvas_class = "Py2CppUICanvas";
static PyBool _ui_canvas_registered = false;
static ULONG_PTR _ui_gdiplus_token = 0;
static PyBool _ui_gdiplus_ready = false;

static void _ui_canvas_ensure_gdiplus()
{
  if (_ui_gdiplus_ready)
  {
    return;
  }
  Gdiplus::GdiplusStartupInput input;
  if (Gdiplus::GdiplusStartup(&_ui_gdiplus_token, &input, NULL) == Gdiplus::Ok)
  {
    _ui_gdiplus_ready = true;
  }
}

static Gdiplus::Color _ui_gdiplus_color(COLORREF col)
{
  return Gdiplus::Color(255, GetRValue(col), GetGValue(col), GetBValue(col));
}

static void _ui_gdiplus_prepare(Gdiplus::Graphics& g)
{
  g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
  g.SetPixelOffsetMode(Gdiplus::PixelOffsetModeHalf);
  g.SetCompositingQuality(Gdiplus::CompositingQualityHighQuality);
}

static void _ui_gdiplus_add_round_rect(
  Gdiplus::GraphicsPath& path,
  Gdiplus::REAL x,
  Gdiplus::REAL y,
  Gdiplus::REAL w,
  Gdiplus::REAL h,
  Gdiplus::REAL radius)
{
  if (w <= 0.0f || h <= 0.0f)
  {
    return;
  }
  Gdiplus::REAL d = radius * 2.0f;
  if (d > w)
  {
    d = w;
  }
  if (d > h)
  {
    d = h;
  }
  if (d < 1.0f)
  {
    path.AddRectangle(Gdiplus::RectF(x, y, w, h));
    return;
  }
  path.AddArc(x, y, d, d, 180.0f, 90.0f);
  path.AddArc(x + w - d, y, d, d, 270.0f, 90.0f);
  path.AddArc(x + w - d, y + h - d, d, d, 0.0f, 90.0f);
  path.AddArc(x, y + h - d, d, d, 90.0f, 90.0f);
  path.CloseFigure();
}

static HWND _ui_canvas_hwnd(const UICanvas& self)
{
  return (HWND)(INT_PTR)self.handle;
}

static void _ui_canvas_set_hwnd(UICanvas& self, HWND hwnd)
{
  self.handle = (PyInt64)((INT_PTR)hwnd);
}

static COLORREF _ui_canvas_rgb(PyInt r, PyInt g, PyInt b)
{
  return RGB(r, g, b);
}

static HFONT _ui_canvas_make_font(const PyStr& name, PyInt size, PyBool bold)
{
  LOGFONTA lf;
  memset(&lf, 0, sizeof(lf));
  lf.lfHeight = -size;
  lf.lfWeight = bold ? FW_BOLD : FW_NORMAL;
  lf.lfCharSet = DEFAULT_CHARSET;
  lf.lfQuality = CLEARTYPE_QUALITY;
  lf.lfPitchAndFamily = FF_DONTCARE;
  name.copy_to_span(PySpan<PyByte>((PyByte*)lf.lfFaceName, (PyInt)sizeof(lf.lfFaceName), 1));
  return CreateFontIndirectA(&lf);
}

static LRESULT CALLBACK _ui_canvas_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp);

static void _ui_canvas_ensure_class()
{
  if (_ui_canvas_registered)
  {
    return;
  }
  WNDCLASSA wc;
  memset(&wc, 0, sizeof(wc));
  wc.lpfnWndProc = _ui_canvas_wndproc;
  wc.hInstance = GetModuleHandleA(NULL);
  wc.lpszClassName = _ui_canvas_class;
  wc.hCursor = LoadCursorA(NULL, IDC_ARROW);
  wc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
  RegisterClassA(&wc);
  _ui_canvas_registered = true;
}

PY2CPP_BEGIN_SCOPE

void UIPaintContext::_gdi_fill_rect(
  PyInt64 dc, PyInt x, PyInt y, PyInt w, PyInt h, PyInt r, PyInt g, PyInt b)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  HBRUSH br = CreateSolidBrush(col);
  RECT rc;
  rc.left = x;
  rc.top = y;
  rc.right = x + w;
  rc.bottom = y + h;
  FillRect(hdc, &rc, br);
  DeleteObject(br);
}

void UIPaintContext::_gdi_stroke_rect(
  PyInt64 dc, PyInt x, PyInt y, PyInt w, PyInt h, PyInt r, PyInt g, PyInt b, PyInt pen_w)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  HPEN pen = CreatePen(PS_SOLID, pen_w, col);
  HPEN old_pen = (HPEN)SelectObject(hdc, pen);
  HBRUSH null_br = (HBRUSH)GetStockObject(NULL_BRUSH);
  HBRUSH old_br = (HBRUSH)SelectObject(hdc, null_br);
  Rectangle(hdc, x, y, x + w, y + h);
  SelectObject(hdc, old_pen);
  SelectObject(hdc, old_br);
  DeleteObject(pen);
}

void UIPaintContext::_gdi_draw_line(
  PyInt64 dc,
  PyInt x1,
  PyInt y1,
  PyInt x2,
  PyInt y2,
  PyInt r,
  PyInt g,
  PyInt b,
  PyInt pen_w)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  HPEN pen = CreatePen(PS_SOLID, pen_w, col);
  HPEN old = (HPEN)SelectObject(hdc, pen);
  MoveToEx(hdc, x1, y1, NULL);
  LineTo(hdc, x2, y2);
  SelectObject(hdc, old);
  DeleteObject(pen);
}

void UIPaintContext::_gdi_draw_bezier(
  PyInt64 dc,
  PyInt x1,
  PyInt y1,
  PyInt cx1,
  PyInt cy1,
  PyInt cx2,
  PyInt cy2,
  PyInt x2,
  PyInt y2,
  PyInt r,
  PyInt g,
  PyInt b,
  PyInt pen_w)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  _ui_canvas_ensure_gdiplus();
  if (_ui_gdiplus_ready)
  {
    Gdiplus::Graphics gfx(hdc);
    _ui_gdiplus_prepare(gfx);
    Gdiplus::REAL pw = (Gdiplus::REAL)pen_w;
    if (pw < 1.0f)
    {
      pw = 1.0f;
    }
    Gdiplus::Pen pen(_ui_gdiplus_color(col), pw);
    pen.SetLineCap(Gdiplus::LineCapRound, Gdiplus::LineCapRound, Gdiplus::DashCapRound);
    pen.SetLineJoin(Gdiplus::LineJoinRound);
    gfx.DrawBezier(
      &pen,
      Gdiplus::PointF((Gdiplus::REAL)x1, (Gdiplus::REAL)y1),
      Gdiplus::PointF((Gdiplus::REAL)cx1, (Gdiplus::REAL)cy1),
      Gdiplus::PointF((Gdiplus::REAL)cx2, (Gdiplus::REAL)cy2),
      Gdiplus::PointF((Gdiplus::REAL)x2, (Gdiplus::REAL)y2));
    return;
  }
  POINT pts[4];
  pts[0].x = x1;
  pts[0].y = y1;
  pts[1].x = cx1;
  pts[1].y = cy1;
  pts[2].x = cx2;
  pts[2].y = cy2;
  pts[3].x = x2;
  pts[3].y = y2;
  HPEN pen = CreatePen(PS_SOLID, pen_w, col);
  HPEN old = (HPEN)SelectObject(hdc, pen);
  PolyBezier(hdc, pts, 4);
  SelectObject(hdc, old);
  DeleteObject(pen);
}

void UIPaintContext::_gdi_draw_text(
  PyInt64 dc,
  PyInt x,
  PyInt y,
  PyInt w,
  PyInt h,
  PyStr text,
  PyInt r,
  PyInt g,
  PyInt b,
  PyStr font_name,
  PyInt font_size,
  PyBool font_bold,
  PyInt text_align)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  HFONT font = _ui_canvas_make_font(font_name, font_size, font_bold);
  HFONT old_font = (HFONT)SelectObject(hdc, font);
  SetBkMode(hdc, TRANSPARENT);
  SetTextColor(hdc, col);
  RECT tr;
  tr.left = x;
  tr.top = y;
  tr.right = x + w;
  tr.bottom = y + h;
  char tbuf[512];
  text.copy_to_span(PySpan<PyByte>((PyByte*)tbuf, (PyInt)sizeof(tbuf), 1));
  UINT fmt = DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS;
  if (text_align == 1)
  {
    fmt |= DT_RIGHT;
  }
  else if (text_align == 2)
  {
    fmt |= DT_CENTER;
  }
  else
  {
    fmt |= DT_LEFT;
  }
  DrawTextA(hdc, tbuf, -1, &tr, fmt);
  SelectObject(hdc, old_font);
  DeleteObject(font);
}

void UIPaintContext::_gdi_fill_ellipse(
  PyInt64 dc, PyInt x1, PyInt y1, PyInt x2, PyInt y2, PyInt r, PyInt g, PyInt b)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  _ui_canvas_ensure_gdiplus();
  if (_ui_gdiplus_ready)
  {
    Gdiplus::Graphics gfx(hdc);
    _ui_gdiplus_prepare(gfx);
    Gdiplus::SolidBrush brush(_ui_gdiplus_color(col));
    gfx.FillEllipse(
      &brush,
      (Gdiplus::REAL)x1,
      (Gdiplus::REAL)y1,
      (Gdiplus::REAL)(x2 - x1),
      (Gdiplus::REAL)(y2 - y1));
    return;
  }
  HBRUSH br = CreateSolidBrush(col);
  HPEN pen = (HPEN)GetStockObject(NULL_PEN);
  HBRUSH oldb = (HBRUSH)SelectObject(hdc, br);
  HPEN oldp = (HPEN)SelectObject(hdc, pen);
  Ellipse(hdc, x1, y1, x2, y2);
  SelectObject(hdc, oldb);
  SelectObject(hdc, oldp);
  DeleteObject(br);
}

void UIPaintContext::_gdi_fill_round_rect(
  PyInt64 dc,
  PyInt x,
  PyInt y,
  PyInt w,
  PyInt h,
  PyInt radius,
  PyInt r,
  PyInt g,
  PyInt b)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  _ui_canvas_ensure_gdiplus();
  if (_ui_gdiplus_ready)
  {
    Gdiplus::Graphics gfx(hdc);
    _ui_gdiplus_prepare(gfx);
    Gdiplus::GraphicsPath path;
    _ui_gdiplus_add_round_rect(
      path,
      (Gdiplus::REAL)x,
      (Gdiplus::REAL)y,
      (Gdiplus::REAL)w,
      (Gdiplus::REAL)h,
      (Gdiplus::REAL)radius);
    Gdiplus::SolidBrush brush(_ui_gdiplus_color(col));
    gfx.FillPath(&brush, &path);
    return;
  }
  PyInt dia = radius * 2;
  if (dia < 2)
  {
    dia = 2;
  }
  HBRUSH br = CreateSolidBrush(col);
  HPEN pen = (HPEN)GetStockObject(NULL_PEN);
  HBRUSH oldb = (HBRUSH)SelectObject(hdc, br);
  HPEN oldp = (HPEN)SelectObject(hdc, pen);
  RoundRect(hdc, x, y, x + w, y + h, dia, dia);
  SelectObject(hdc, oldb);
  SelectObject(hdc, oldp);
  DeleteObject(br);
}

void UIPaintContext::_gdi_stroke_round_rect(
  PyInt64 dc,
  PyInt x,
  PyInt y,
  PyInt w,
  PyInt h,
  PyInt radius,
  PyInt r,
  PyInt g,
  PyInt b,
  PyInt pen_w)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  _ui_canvas_ensure_gdiplus();
  if (_ui_gdiplus_ready)
  {
    Gdiplus::Graphics gfx(hdc);
    _ui_gdiplus_prepare(gfx);
    Gdiplus::GraphicsPath path;
    _ui_gdiplus_add_round_rect(
      path,
      (Gdiplus::REAL)x,
      (Gdiplus::REAL)y,
      (Gdiplus::REAL)w,
      (Gdiplus::REAL)h,
      (Gdiplus::REAL)radius);
    Gdiplus::REAL pw = (Gdiplus::REAL)pen_w;
    if (pw < 1.0f)
    {
      pw = 1.0f;
    }
    Gdiplus::Pen pen(_ui_gdiplus_color(col), pw);
    pen.SetLineJoin(Gdiplus::LineJoinRound);
    gfx.DrawPath(&pen, &path);
    return;
  }
  PyInt dia = radius * 2;
  if (dia < 2)
  {
    dia = 2;
  }
  HPEN pen = CreatePen(PS_SOLID, pen_w, col);
  HPEN old_pen = (HPEN)SelectObject(hdc, pen);
  HBRUSH null_br = (HBRUSH)GetStockObject(NULL_BRUSH);
  HBRUSH old_br = (HBRUSH)SelectObject(hdc, null_br);
  RoundRect(hdc, x, y, x + w, y + h, dia, dia);
  SelectObject(hdc, old_pen);
  SelectObject(hdc, old_br);
  DeleteObject(pen);
}

void UIPaintContext::_gdi_fill_rect_in_round_clip(
  PyInt64 dc,
  PyInt x,
  PyInt y,
  PyInt w,
  PyInt h,
  PyInt round_w,
  PyInt round_h,
  PyInt radius,
  PyInt r,
  PyInt g,
  PyInt b)
{
  HDC hdc = (HDC)(INT_PTR)dc;
  if (!hdc)
  {
    return;
  }
  COLORREF col = _ui_canvas_rgb(r, g, b);
  _ui_canvas_ensure_gdiplus();
  if (_ui_gdiplus_ready)
  {
    Gdiplus::Graphics gfx(hdc);
    _ui_gdiplus_prepare(gfx);
    Gdiplus::GraphicsPath path;
    _ui_gdiplus_add_round_rect(
      path,
      (Gdiplus::REAL)x,
      (Gdiplus::REAL)y,
      (Gdiplus::REAL)round_w,
      (Gdiplus::REAL)round_h,
      (Gdiplus::REAL)radius);
    gfx.SetClip(&path);
    Gdiplus::SolidBrush brush(_ui_gdiplus_color(col));
    gfx.FillRectangle(&brush, (Gdiplus::REAL)x, (Gdiplus::REAL)y, (Gdiplus::REAL)w, (Gdiplus::REAL)h);
    gfx.ResetClip();
    return;
  }
  PyInt dia = radius * 2;
  if (dia < 2)
  {
    dia = 2;
  }
  HRGN rgn = CreateRoundRectRgn(x, y, x + round_w + 1, y + round_h + 1, dia, dia);
  SelectClipRgn(hdc, rgn);
  HBRUSH br = CreateSolidBrush(col);
  RECT rc;
  rc.left = x;
  rc.top = y;
  rc.right = x + w;
  rc.bottom = y + h;
  FillRect(hdc, &rc, br);
  DeleteObject(br);
  SelectClipRgn(hdc, NULL);
  DeleteObject(rgn);
}

PyTuple<PyInt, PyInt> UICanvas::_win_parent_client_size(PyInt64 parent)
{
  HWND hwnd = (HWND)(INT_PTR)parent;
  if (!hwnd)
  {
    return PyTuple<PyInt, PyInt>(0, 0);
  }
  RECT rc;
  GetClientRect(hwnd, &rc);
  return PyTuple<PyInt, PyInt>((PyInt)(rc.right - rc.left), (PyInt)(rc.bottom - rc.top));
}

void UICanvas::_win_mount_child(PyInt64 parent, PyInt x, PyInt y, PyInt w, PyInt h)
{
  _ui_canvas_ensure_class();
  HWND parent_hwnd = (HWND)(INT_PTR)parent;
  if (!parent_hwnd)
  {
    return;
  }
  if (_ui_canvas_hwnd(*this))
  {
    DestroyWindow(_ui_canvas_hwnd(*this));
    _ui_canvas_set_hwnd(*this, NULL);
  }
  HWND canvas = CreateWindowExA(
    0,
    _ui_canvas_class,
    "",
    WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
    x,
    y,
    w,
    h,
    parent_hwnd,
    NULL,
    GetModuleHandleA(NULL),
    NULL);
  _ui_canvas_set_hwnd(*this, canvas);
  SetWindowLongPtrA(canvas, GWLP_USERDATA, (LONG_PTR)this);
  ShowWindow(canvas, SW_SHOW);
  UpdateWindow(canvas);
}

PyTuple<PyInt, PyInt> UICanvas::_win_client_size()
{
  HWND canvas = _ui_canvas_hwnd(*this);
  if (!canvas)
  {
    return PyTuple<PyInt, PyInt>(0, 0);
  }
  RECT rc;
  GetClientRect(canvas, &rc);
  return PyTuple<PyInt, PyInt>((PyInt)(rc.right - rc.left), (PyInt)(rc.bottom - rc.top));
}

void UICanvas::set_bounds(PyInt x, PyInt y, PyInt w, PyInt h)
{
  HWND canvas = _ui_canvas_hwnd(*this);
  if (!canvas)
  {
    return;
  }
  MoveWindow(canvas, x, y, w, h, TRUE);
}

PyTuple<PyInt, PyInt> UICanvas::client_from_screen(PyInt scr_x, PyInt scr_y)
{
  HWND canvas = _ui_canvas_hwnd(*this);
  if (!canvas)
  {
    return PyTuple<PyInt, PyInt>(0, 0);
  }
  POINT pt;
  pt.x = (LONG)scr_x;
  pt.y = (LONG)scr_y;
  ScreenToClient(canvas, &pt);
  return PyTuple<PyInt, PyInt>((PyInt)pt.x, (PyInt)pt.y);
}

void UICanvas::invalidate()
{
  HWND canvas = _ui_canvas_hwnd(*this);
  if (!canvas)
  {
    return;
  }
  InvalidateRect(canvas, NULL, FALSE);
}

PY2CPP_END_SCOPE

static LRESULT CALLBACK _ui_canvas_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
  UICanvas* ctx = (UICanvas*)GetWindowLongPtrA(hwnd, GWLP_USERDATA);
  switch (msg)
  {
    case WM_ERASEBKGND:
      return 1;
    case WM_PAINT: {
      PAINTSTRUCT ps;
      HDC hdc = BeginPaint(hwnd, &ps);
      RECT rc;
      GetClientRect(hwnd, &rc);
      PyInt cw = rc.right - rc.left;
      PyInt ch = rc.bottom - rc.top;
      HDC mem = CreateCompatibleDC(hdc);
      HBITMAP bmp = CreateCompatibleBitmap(hdc, cw, ch);
      HBITMAP old_bmp = (HBITMAP)SelectObject(mem, bmp);
      if (ctx)
      {
        ctx->paint_frame((PyInt64)(INT_PTR)mem, cw, ch);
      }
      else
      {
        HBRUSH bg = CreateSolidBrush(RGB(32, 32, 32));
        FillRect(mem, &rc, bg);
        DeleteObject(bg);
      }
      BitBlt(hdc, 0, 0, cw, ch, mem, 0, 0, SRCCOPY);
      SelectObject(mem, old_bmp);
      DeleteObject(bmp);
      DeleteDC(mem);
      EndPaint(hwnd, &ps);
      return 0;
    }
    case WM_LBUTTONDOWN:
    case WM_RBUTTONDOWN:
    case WM_MBUTTONDOWN: {
      if (!ctx)
      {
        break;
      }
      PyInt btn = 1;
      if (msg == WM_RBUTTONDOWN)
      {
        btn = 2;
      }
      else if (msg == WM_MBUTTONDOWN)
      {
        btn = 4;
      }
      SetCapture(hwnd);
      SetFocus(hwnd);
      ctx->on_pointer_down(btn, (PyInt)(short)LOWORD(lp), (PyInt)(short)HIWORD(lp));
      return 0;
    }
    case WM_MOUSEMOVE: {
      if (!ctx)
      {
        break;
      }
      PyInt btn = 0;
      if (wp & MK_LBUTTON)
      {
        btn = 1;
      }
      else if (wp & MK_RBUTTON)
      {
        btn = 2;
      }
      else if (wp & MK_MBUTTON)
      {
        btn = 4;
      }
      ctx->on_pointer_move(btn, (PyInt)(short)LOWORD(lp), (PyInt)(short)HIWORD(lp));
      return 0;
    }
    case WM_LBUTTONUP:
    case WM_RBUTTONUP:
    case WM_MBUTTONUP: {
      if (!ctx)
      {
        break;
      }
      ReleaseCapture();
      PyInt btn = 1;
      if (msg == WM_RBUTTONUP)
      {
        btn = 2;
      }
      else if (msg == WM_MBUTTONUP)
      {
        btn = 4;
      }
      ctx->on_pointer_up(btn, (PyInt)(short)LOWORD(lp), (PyInt)(short)HIWORD(lp));
      return 0;
    }
    case WM_MOUSEWHEEL: {
      if (!ctx)
      {
        break;
      }
      POINT pt;
      pt.x = (LONG)(short)LOWORD(lp);
      pt.y = (LONG)(short)HIWORD(lp);
      ScreenToClient(hwnd, &pt);
      ctx->on_wheel((PyInt)(short)HIWORD(wp), (PyInt)pt.x, (PyInt)pt.y);
      return 0;
    }
    case WM_KEYDOWN: {
      if (!ctx)
      {
        break;
      }
      ctx->on_key((PyInt)(UINT)wp);
      return 0;
    }
    default:
      break;
  }
  return DefWindowProcA(hwnd, msg, wp, lp);
}

#else

PY2CPP_BEGIN_SCOPE

void UIPaintContext::_gdi_fill_rect(
  PyInt64 dc, PyInt x, PyInt y, PyInt w, PyInt h, PyInt r, PyInt g, PyInt b)
{
  (void)dc;
  (void)x;
  (void)y;
  (void)w;
  (void)h;
  (void)r;
  (void)g;
  (void)b;
}

void UIPaintContext::_gdi_stroke_rect(
  PyInt64 dc, PyInt x, PyInt y, PyInt w, PyInt h, PyInt r, PyInt g, PyInt b, PyInt pen_w)
{
  (void)dc;
  (void)x;
  (void)y;
  (void)w;
  (void)h;
  (void)r;
  (void)g;
  (void)b;
  (void)pen_w;
}

void UIPaintContext::_gdi_draw_line(
  PyInt64 dc,
  PyInt x1,
  PyInt y1,
  PyInt x2,
  PyInt y2,
  PyInt r,
  PyInt g,
  PyInt b,
  PyInt pen_w)
{
  (void)dc;
  (void)x1;
  (void)y1;
  (void)x2;
  (void)y2;
  (void)r;
  (void)g;
  (void)b;
  (void)pen_w;
}

void UIPaintContext::_gdi_draw_bezier(
  PyInt64 dc,
  PyInt x1,
  PyInt y1,
  PyInt cx1,
  PyInt cy1,
  PyInt cx2,
  PyInt cy2,
  PyInt x2,
  PyInt y2,
  PyInt r,
  PyInt g,
  PyInt b,
  PyInt pen_w)
{
  (void)dc;
  (void)x1;
  (void)y1;
  (void)cx1;
  (void)cy1;
  (void)cx2;
  (void)cy2;
  (void)x2;
  (void)y2;
  (void)r;
  (void)g;
  (void)b;
  (void)pen_w;
}

void UIPaintContext::_gdi_draw_text(
  PyInt64 dc,
  PyInt x,
  PyInt y,
  PyInt w,
  PyInt h,
  PyStr text,
  PyInt r,
  PyInt g,
  PyInt b,
  PyStr font_name,
  PyInt font_size,
  PyBool font_bold,
  PyInt text_align)
{
  (void)dc;
  (void)x;
  (void)y;
  (void)w;
  (void)h;
  (void)text;
  (void)r;
  (void)g;
  (void)b;
  (void)font_name;
  (void)font_size;
  (void)font_bold;
  (void)text_align;
}

void UIPaintContext::_gdi_fill_ellipse(
  PyInt64 dc, PyInt x1, PyInt y1, PyInt x2, PyInt y2, PyInt r, PyInt g, PyInt b)
{
  (void)dc;
  (void)x1;
  (void)y1;
  (void)x2;
  (void)y2;
  (void)r;
  (void)g;
  (void)b;
}

void UIPaintContext::_gdi_fill_round_rect(
  PyInt64 dc,
  PyInt x,
  PyInt y,
  PyInt w,
  PyInt h,
  PyInt radius,
  PyInt r,
  PyInt g,
  PyInt b)
{
  (void)dc;
  (void)x;
  (void)y;
  (void)w;
  (void)h;
  (void)radius;
  (void)r;
  (void)g;
  (void)b;
}

void UIPaintContext::_gdi_stroke_round_rect(
  PyInt64 dc,
  PyInt x,
  PyInt y,
  PyInt w,
  PyInt h,
  PyInt radius,
  PyInt r,
  PyInt g,
  PyInt b,
  PyInt pen_w)
{
  (void)dc;
  (void)x;
  (void)y;
  (void)w;
  (void)h;
  (void)radius;
  (void)r;
  (void)g;
  (void)b;
  (void)pen_w;
}

void UIPaintContext::_gdi_fill_rect_in_round_clip(
  PyInt64 dc,
  PyInt x,
  PyInt y,
  PyInt w,
  PyInt h,
  PyInt round_w,
  PyInt round_h,
  PyInt radius,
  PyInt r,
  PyInt g,
  PyInt b)
{
  (void)dc;
  (void)x;
  (void)y;
  (void)w;
  (void)h;
  (void)round_w;
  (void)round_h;
  (void)radius;
  (void)r;
  (void)g;
  (void)b;
}

PyTuple<PyInt, PyInt> UICanvas::_win_parent_client_size(PyInt64 parent)
{
  (void)parent;
  return PyTuple<PyInt, PyInt>(0, 0);
}

void UICanvas::_win_mount_child(PyInt64 parent, PyInt x, PyInt y, PyInt w, PyInt h)
{
  (void)parent;
  (void)x;
  (void)y;
  (void)w;
  (void)h;
}

PyTuple<PyInt, PyInt> UICanvas::_win_client_size()
{
  return PyTuple<PyInt, PyInt>(0, 0);
}

void UICanvas::set_bounds(PyInt x, PyInt y, PyInt w, PyInt h)
{
  (void)x;
  (void)y;
  (void)w;
  (void)h;
}

PyTuple<PyInt, PyInt> UICanvas::client_from_screen(PyInt scr_x, PyInt scr_y)
{
  (void)scr_x;
  (void)scr_y;
  return PyTuple<PyInt, PyInt>(0, 0);
}

void UICanvas::invalidate()
{
}

PY2CPP_END_SCOPE

#endif
