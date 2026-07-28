PY2CPP_IGNORE
#include "py2cpp/ui/layout.h"
#include "py2cpp/ui/window.h"
#include "py2cpp/ui/widget.h"
#include "py2cpp/ui/events.h"
#include "py2cpp/util/list.h"
#include "py2cpp/util/dict.h"
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

namespace py2cpp {
namespace ui {
namespace window {
void ui_theme_ensure_process();
void ui_theme_attach_panel(HWND hwnd, UIWindow& ctx);
void ui_theme_apply_font(HWND hwnd);
void ui_theme_layout_metrics(
    const UIWindow& ctx,
    int* pad_x,
    int* label_w,
    int* row_h,
    int* row_spacing,
    int* slider_h,
    int* edit_w,
    int* edit_h,
    int* slider_w,
    int* form_spacing);
int ui_theme_scale_ctx(const UIWindow& ctx, int px);
HBRUSH ui_theme_panel_brush();
HBRUSH ui_theme_on_ctl_color(HDC hdc);
} // namespace window
namespace layout {
void ui_form_session_reset();
void ui_form_on_window_end(window::UIWindow& win);
PyBool ui_form_on_bn_clicked(window::UIWindow& win, UINT_PTR ctrl_id);
PyBool ui_form_on_en_change(window::UIWindow& win, UINT_PTR ctrl_id);
PyBool ui_form_on_hscroll(window::UIWindow& win, HWND ctrl);
} // namespace layout
} // namespace ui
} // namespace py2cpp

enum UIRowKind {
  UI_ROW_CHECKBOX = 0,
  UI_ROW_LINE_EDIT = 1,
  UI_ROW_INT_EDIT = 2,
  UI_ROW_SLIDER = 3,
};

struct UIRowEntry
{
  UIRowKind kind;
  PyStr label;
  HWND ctrl;
  PyBool bval;
  PyStr sval;
  PyInt ival;
  PyInt lo;
  PyInt hi;
  py2cpp::ui::widget::UICheckBox checkbox;
  py2cpp::ui::widget::UILineEdit line_edit;
  py2cpp::ui::widget::UIIntEdit int_edit;
  py2cpp::ui::widget::UISlider slider;
};

struct UIButtonEntry
{
  PyStr text;
  HWND ctrl;
  py2cpp::ui::widget::UIPushButton widget;
};

typedef PY2CPP_TYPE(PyList)<UIRowEntry> UIFormRowList;
typedef PY2CPP_TYPE(PyList)<UIButtonEntry> UIFormButtonList;

struct UIFormState
{
  UIFormRowList rows;
  UIFormButtonList buttons;
  PyBool applied;
  PyInt64 mounted_handle;
};

static PY2CPP_TYPE(PyList)<UIFormState> _ui_form_state_data;
static PY2CPP_TYPE(PyDict)<PyInt, PyInt> _ui_form_state_index;

static UIFormState& _ui_form_state(UIFormLayout& form)
{
  PyInt key = (PyInt)(intptr_t)&form;
  if (_ui_form_state_index.__contains__(key))
  {
    PyInt idx = _ui_form_state_index.__getitem__(key);
    return _ui_form_state_data.__getitem__(idx);
  }
  UIFormState st;
  st.applied = false;
  st.mounted_handle = (PyInt64)0;
  PyInt idx = _ui_form_state_data.__len__();
  _ui_form_state_data.append(st);
  _ui_form_state_index.__setitem__(key, idx);
  return _ui_form_state_data.__getitem__(idx);
}

static PyInt _ui_form_ctrl_serial = 1;

static HWND _ui_form_ctx_hwnd(const py2cpp::ui::window::UIWindow& self)
{
  return (HWND)(INT_PTR)self.handle;
}

static void _ui_read_edit_text(HWND ctrl, char* buf, int cap)
{
  if ((!ctrl) || (!buf) || (cap <= 0))
  {
    if (buf && (cap > 0))
    {
      buf[0] = '\0';
    }
    return;
  }
  int n = (int)GetWindowTextLengthA(ctrl);
  if (n >= (cap - 1))
  {
    n = cap - 2;
  }
  if (n < 0)
  {
    n = 0;
  }
  GetWindowTextA(ctrl, buf, n + 1);
  buf[n] = '\0';
}

static PyInt _ui_clamp_int(PyInt v, PyInt lo, PyInt hi)
{
  if (v < lo)
  {
    return lo;
  }
  if (v > hi)
  {
    return hi;
  }
  return v;
}

static void _ui_layout_row(py2cpp::ui::window::UIWindow& self, PyStr label, HWND ctrl, int ctrl_w, int ctrl_h)
{
  HWND parent = _ui_form_ctx_hwnd(self);
  if (!parent)
  {
    return;
  }
  py2cpp::ui::window::ui_theme_ensure_process();
  PyInt pad_x = 0;
  PyInt label_w = 0;
  PyInt row_h = 0;
  PyInt row_spacing = 0;
  PyInt slider_h = 0;
  PyInt edit_w = 0;
  PyInt edit_h = 0;
  PyInt slider_w = 0;
  PyInt form_spacing = 0;
  py2cpp::ui::window::ui_theme_layout_metrics(
      self,
      &pad_x,
      &label_w,
      &row_h,
      &row_spacing,
      &slider_h,
      &edit_w,
      &edit_h,
      &slider_w,
      &form_spacing);
  (void)edit_w;
  (void)edit_h;
  (void)slider_w;
  if (ctrl_h <= 0)
  {
    ctrl_h = row_h;
  }
  int slot_h = row_h;
  if (ctrl_h > slot_h)
  {
    slot_h = ctrl_h;
  }
  char lbuf[256];
  label.copy_to_span(PySpan<PyByte>((PyByte*)lbuf, (PyInt)sizeof(lbuf), 1));
  int y = self.next_y;
  int ctrl_x = pad_x + label_w + form_spacing;
  HWND lbl = CreateWindowExA(
      0,
      "STATIC",
      lbuf,
      WS_CHILD | WS_VISIBLE | SS_LEFT | SS_CENTERIMAGE,
      pad_x,
      y,
      label_w,
      slot_h,
      parent,
      NULL,
      GetModuleHandleA(NULL),
      NULL);
  py2cpp::ui::window::ui_theme_apply_font(lbl);
  if (ctrl)
  {
    SetWindowPos(
        ctrl,
        NULL,
        ctrl_x,
        y + ((slot_h - ctrl_h) / 2),
        ctrl_w,
        ctrl_h,
        SWP_NOZORDER | SWP_SHOWWINDOW);
    py2cpp::ui::window::ui_theme_apply_font(ctrl);
  }
  self.next_y = (PyInt)(y + slot_h + row_spacing);
}

static HWND _ui_create_push_button(HWND parent, const char* text, PyInt width, PyInt height)
{
  UINT_PTR cid = (UINT_PTR)_ui_form_ctrl_serial;
  _ui_form_ctrl_serial = (_ui_form_ctrl_serial + 1);
  return CreateWindowExA(
      0,
      "BUTTON",
      text ? text : "",
      WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
      0,
      0,
      width,
      height,
      parent,
      (HMENU)cid,
      GetModuleHandleA(NULL),
      NULL);
}

static HWND _ui_create_checkbox(HWND parent, PyInt box_w, PyInt box_h, PyBool checked)
{
  UINT_PTR cid = (UINT_PTR)_ui_form_ctrl_serial;
  _ui_form_ctrl_serial = (_ui_form_ctrl_serial + 1);
  HWND ctrl = CreateWindowExA(
      0,
      "BUTTON",
      "",
      WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX,
      0,
      0,
      box_w,
      box_h,
      parent,
      (HMENU)cid,
      GetModuleHandleA(NULL),
      NULL);
  SendMessageA(ctrl, BM_SETCHECK, checked ? BST_CHECKED : BST_UNCHECKED, 0);
  return ctrl;
}

static HWND _ui_create_edit(HWND parent, const char* text, PyInt width, PyInt height)
{
  UINT_PTR cid = (UINT_PTR)_ui_form_ctrl_serial;
  _ui_form_ctrl_serial = (_ui_form_ctrl_serial + 1);
  return CreateWindowExA(
      0,
      "EDIT",
      text ? text : "",
      WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL | ES_LEFT,
      0,
      0,
      width,
      height,
      parent,
      (HMENU)cid,
      GetModuleHandleA(NULL),
      NULL);
}

static HWND _ui_create_slider(
    HWND parent, PyInt width, PyInt height, PyInt lo, PyInt hi, PyInt value)
{
  py2cpp::ui::window::ui_theme_ensure_process();
  UINT_PTR cid = (UINT_PTR)_ui_form_ctrl_serial;
  _ui_form_ctrl_serial = (_ui_form_ctrl_serial + 1);
  HWND ctrl = CreateWindowExA(
      0,
      TRACKBAR_CLASSA,
      "",
      WS_CHILD | WS_VISIBLE | TBS_HORZ | TBS_TOOLTIPS | TBS_TRANSPARENTBKGND,
      0,
      0,
      width,
      height,
      parent,
      (HMENU)cid,
      GetModuleHandleA(NULL),
      NULL);
  SendMessageA(ctrl, TBM_SETRANGE, (WPARAM)TRUE, (LPARAM)MAKELONG(lo, hi));
  SendMessageA(ctrl, TBM_SETTICFREQ, (WPARAM)0, 0);
  SendMessageA(ctrl, TBM_SETPOS, (WPARAM)TRUE, (LPARAM)_ui_clamp_int(value, lo, hi));
  return ctrl;
}

static void _ui_row_sync_from_native(UIRowEntry& row)
{
  if (!row.ctrl)
  {
    return;
  }
  switch (row.kind)
  {
    case UI_ROW_CHECKBOX: {
      LRESULT st = SendMessageA(row.ctrl, BM_GETCHECK, 0, 0);
      row.bval = (st == BST_CHECKED);
      break;
    }
    case UI_ROW_LINE_EDIT: {
      char buf[512];
      _ui_read_edit_text(row.ctrl, buf, (int)sizeof(buf));
      row.sval = PyStr(buf);
      break;
    }
    case UI_ROW_INT_EDIT: {
      char buf[32];
      _ui_read_edit_text(row.ctrl, buf, (int)sizeof(buf));
      row.ival = (PyInt)atoi(buf);
      break;
    }
    case UI_ROW_SLIDER: {
      LRESULT pos = SendMessageA(row.ctrl, TBM_GETPOS, 0, 0);
      row.ival = _ui_clamp_int((PyInt)pos, row.lo, row.hi);
      break;
    }
    default:
      break;
  }
}

static void _ui_row_sync_to_native(UIRowEntry& row)
{
  if (!row.ctrl)
  {
    return;
  }
  switch (row.kind)
  {
    case UI_ROW_CHECKBOX: {
      SendMessageA(
          row.ctrl,
          BM_SETCHECK,
          (WPARAM)(row.bval ? BST_CHECKED : BST_UNCHECKED),
          0);
      break;
    }
    case UI_ROW_LINE_EDIT: {
      char vbuf[512];
      row.sval.copy_to_span(PySpan<PyByte>((PyByte*)vbuf, (PyInt)sizeof(vbuf), 1));
      SetWindowTextA(row.ctrl, vbuf);
      break;
    }
    case UI_ROW_INT_EDIT: {
      char vbuf[32];
      snprintf(vbuf, sizeof(vbuf), "%d", (int)row.ival);
      SetWindowTextA(row.ctrl, vbuf);
      break;
    }
    case UI_ROW_SLIDER: {
      int want = _ui_clamp_int(row.ival, row.lo, row.hi);
      LRESULT pos = SendMessageA(row.ctrl, TBM_GETPOS, 0, 0);
      if ((int)pos != want)
      {
        SendMessageA(
            row.ctrl,
            TBM_SETPOS,
            (WPARAM)TRUE,
            (LPARAM)want);
      }
      break;
    }
    default:
      break;
  }
}

static void _ui_row_mount_widget_handle(UIRowEntry& row)
{
  if (!row.ctrl)
  {
    return;
  }
  py2cpp::ui::widget::UIWidget* widget = NULL;
  switch (row.kind)
  {
    case UI_ROW_CHECKBOX:
      widget = reinterpret_cast<py2cpp::ui::widget::UIWidget*>(&row.checkbox);
      break;
    case UI_ROW_LINE_EDIT:
      widget = reinterpret_cast<py2cpp::ui::widget::UIWidget*>(&row.line_edit);
      break;
    case UI_ROW_INT_EDIT:
      widget = reinterpret_cast<py2cpp::ui::widget::UIWidget*>(&row.int_edit);
      break;
    case UI_ROW_SLIDER:
      widget = reinterpret_cast<py2cpp::ui::widget::UIWidget*>(&row.slider);
      break;
    default:
      break;
  }
  if (!widget)
  {
    return;
  }
  widget->handle = (PyInt64)((INT_PTR)row.ctrl);
}

static void _ui_mount_row(py2cpp::ui::window::UIWindow& win, UIRowEntry& row)
{
  HWND parent = _ui_form_ctx_hwnd(win);
  if (!parent)
  {
    return;
  }
  switch (row.kind)
  {
    case UI_ROW_CHECKBOX: {
      PyInt box_w = py2cpp::ui::window::ui_theme_scale_ctx(win, win.style.checkbox_size.template get<0>());
      PyInt box_h = py2cpp::ui::window::ui_theme_scale_ctx(win, win.style.checkbox_size.template get<1>());
      row.ctrl = _ui_create_checkbox(parent, box_w, box_h, row.bval);
      _ui_layout_row(win, row.label, row.ctrl, box_w, box_h);
      _ui_row_mount_widget_handle(row);
      break;
    }
    case UI_ROW_LINE_EDIT: {
      PyInt edit_w = 0;
      PyInt edit_h = 0;
      py2cpp::ui::window::ui_theme_layout_metrics(
          win, NULL, NULL, NULL, NULL, NULL, &edit_w, &edit_h, NULL, NULL);
      char vbuf[512];
      row.sval.copy_to_span(PySpan<PyByte>((PyByte*)vbuf, (PyInt)sizeof(vbuf), 1));
      row.ctrl = _ui_create_edit(parent, vbuf, edit_w, edit_h);
      _ui_layout_row(win, row.label, row.ctrl, edit_w, edit_h);
      _ui_row_mount_widget_handle(row);
      break;
    }
    case UI_ROW_INT_EDIT: {
      PyInt edit_w = 0;
      PyInt edit_h = 0;
      py2cpp::ui::window::ui_theme_layout_metrics(
          win, NULL, NULL, NULL, NULL, NULL, &edit_w, &edit_h, NULL, NULL);
      char vbuf[32];
      snprintf(vbuf, sizeof(vbuf), "%d", (int)row.ival);
      row.ctrl = _ui_create_edit(parent, vbuf, edit_w, edit_h);
      _ui_layout_row(win, row.label, row.ctrl, edit_w, edit_h);
      _ui_row_mount_widget_handle(row);
      break;
    }
    case UI_ROW_SLIDER: {
      PyInt slider_w = 0;
      PyInt slider_h = 0;
      py2cpp::ui::window::ui_theme_layout_metrics(
          win, NULL, NULL, NULL, NULL, &slider_h, NULL, NULL, &slider_w, NULL);
      row.ctrl = _ui_create_slider(parent, slider_w, slider_h, row.lo, row.hi, row.ival);
      _ui_layout_row(win, row.label, row.ctrl, slider_w, slider_h);
      _ui_row_mount_widget_handle(row);
      break;
    }
    default:
      break;
  }
}

static void _ui_mount_button(py2cpp::ui::window::UIWindow& win, UIButtonEntry& btn)
{
  HWND parent = _ui_form_ctx_hwnd(win);
  if (!parent)
  {
    return;
  }
  PyInt btn_w = 0;
  PyInt btn_h = 0;
  py2cpp::ui::window::ui_theme_layout_metrics(
      win, NULL, NULL, NULL, NULL, NULL, NULL, &btn_h, NULL, NULL);
  btn_w = py2cpp::ui::window::ui_theme_scale_ctx(win, win.style.button_size.template get<0>());
  if (btn_h <= 0)
  {
    btn_h = py2cpp::ui::window::ui_theme_scale_ctx(win, win.style.button_size.template get<1>());
  }
  char lbuf[256];
  btn.text.copy_to_span(PySpan<PyByte>((PyByte*)lbuf, (PyInt)sizeof(lbuf), 1));
  btn.ctrl = _ui_create_push_button(parent, lbuf, btn_w, btn_h);
  btn.widget.handle = (PyInt64)((INT_PTR)btn.ctrl);
  _ui_layout_row(win, PyStr(""), btn.ctrl, btn_w, btn_h);
}

static UIRowEntry* _ui_form_find_row_by_ctrl(UIFormState& st, UINT_PTR ctrl_id)
{
  size_t i = 0;
  while (i < (size_t)st.rows.__len__())
  {
    UIRowEntry& row = st.rows.__getitem__((PyInt)i);
    if (row.ctrl && ((UINT_PTR)GetDlgCtrlID(row.ctrl) == ctrl_id))
    {
      return &row;
    }
    i = (i + 1);
  }
  return NULL;
}

static UIRowEntry* _ui_form_find_row_by_hwnd(UIFormState& st, HWND ctrl)
{
  size_t i = 0;
  while (i < (size_t)st.rows.__len__())
  {
    UIRowEntry& row = st.rows.__getitem__((PyInt)i);
    if (row.ctrl == ctrl)
    {
      return &row;
    }
    i = (i + 1);
  }
  return NULL;
}

static void _ui_row_fire_value_changed(UIRowEntry& row)
{
  switch (row.kind)
  {
    case UI_ROW_CHECKBOX: {
      row.checkbox.PY2CPP_SETTER(checked)(row.bval);
      break;
    }
    case UI_ROW_LINE_EDIT: {
      row.line_edit.PY2CPP_SETTER(text)(row.sval);
      break;
    }
    case UI_ROW_INT_EDIT: {
      row.int_edit.PY2CPP_SETTER(value)(row.ival);
      break;
    }
    case UI_ROW_SLIDER: {
      row.slider.PY2CPP_SETTER(value)(row.ival);
      break;
    }
    default:
      break;
  }
}

PY2CPP_BEGIN_SCOPE

PyBool ui_form_on_bn_clicked(py2cpp::ui::window::UIWindow& win, UINT_PTR ctrl_id)
{
  if (!win.active_form)
  {
    return false;
  }
UIFormLayout* form = reinterpret_cast<UIFormLayout*>((void*)(INT_PTR)win.active_form);
  if (!form)
  {
    return false;
  }
  UIFormState& st = _ui_form_state(*form);
  size_t i = 0;
  while (i < (size_t)st.buttons.__len__())
  {
    UIButtonEntry& b = st.buttons.__getitem__((PyInt)i);
    if (b.ctrl && ((UINT_PTR)GetDlgCtrlID(b.ctrl) == ctrl_id))
    {
      if (b.widget.clicked)
      {
        b.widget.clicked();
      }
      return true;
    }
    i = (i + 1);
  }
  UIRowEntry* row = _ui_form_find_row_by_ctrl(st, ctrl_id);
  if ((!row) || (row->kind != UI_ROW_CHECKBOX))
  {
    return false;
  }
  form->sync_from_native(win);
  _ui_row_fire_value_changed(*row);
  return true;
}

PyBool ui_form_on_en_change(py2cpp::ui::window::UIWindow& win, UINT_PTR ctrl_id)
{
  if (!win.active_form)
  {
    return false;
  }
UIFormLayout* form = reinterpret_cast<UIFormLayout*>((void*)(INT_PTR)win.active_form);
  if (!form)
  {
    return false;
  }
  UIFormState& st = _ui_form_state(*form);
  UIRowEntry* row = _ui_form_find_row_by_ctrl(st, ctrl_id);
  if ((!row)
      || ((row->kind != UI_ROW_LINE_EDIT) && (row->kind != UI_ROW_INT_EDIT)))
      {
    return false;
  }
  form->sync_from_native(win);
  _ui_row_fire_value_changed(*row);
  return true;
}

PyBool ui_form_on_hscroll(py2cpp::ui::window::UIWindow& win, HWND ctrl)
{
  if ((!win.active_form) || (!ctrl))
  {
    return false;
  }
UIFormLayout* form = reinterpret_cast<UIFormLayout*>((void*)(INT_PTR)win.active_form);
  if (!form)
  {
    return false;
  }
  UIFormState& st = _ui_form_state(*form);
  UIRowEntry* row = _ui_form_find_row_by_hwnd(st, ctrl);
  if ((!row) || (row->kind != UI_ROW_SLIDER))
  {
    return false;
  }
  _ui_row_sync_from_native(*row);
  _ui_row_fire_value_changed(*row);
  return true;
}

void ui_form_session_reset()
{
  _ui_form_ctrl_serial = 1;
}

void ui_form_on_window_end(py2cpp::ui::window::UIWindow& win)
{
  if (!win.active_form)
  {
    return;
  }
UIFormLayout* form = reinterpret_cast<UIFormLayout*>((void*)(INT_PTR)win.active_form);
  if (!form)
  {
    return;
  }
  UIFormState& st = _ui_form_state(*form);
  st.applied = false;
  st.mounted_handle = (PyInt64)0;
  win.active_form = (PyInt64)0;
}

void UIFormLayout::clear()
{
  UIFormState& st = _ui_form_state(*this);
  st.rows.clear();
  st.buttons.clear();
  st.applied = false;
  st.mounted_handle = (PyInt64)0;
  _applied = false;
}

void UIFormLayout::add_checkbox(PyStr label, py2cpp::ui::widget::UICheckBox& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_CHECKBOX;
  row.label = label;
  row.ctrl = NULL;
  row.bval = widget.PY2CPP_GETTER(checked)();
  row.sval = PyStr("");
  row.ival = 0;
  row.lo = 0;
  row.hi = 0;
  row.checkbox = widget;
  st.rows.append(row);
}

void UIFormLayout::add_line_edit(PyStr label, py2cpp::ui::widget::UILineEdit& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_LINE_EDIT;
  row.label = label;
  row.ctrl = NULL;
  row.bval = false;
  row.sval = widget.PY2CPP_GETTER(text)();
  row.ival = 0;
  row.lo = 0;
  row.hi = 0;
  row.line_edit = widget;
  st.rows.append(row);
}

void UIFormLayout::add_int_edit(PyStr label, py2cpp::ui::widget::UIIntEdit& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_INT_EDIT;
  row.label = label;
  row.ctrl = NULL;
  row.bval = false;
  row.sval = PyStr("");
  row.ival = widget.PY2CPP_GETTER(value)();
  row.lo = 0;
  row.hi = 0;
  row.int_edit = widget;
  st.rows.append(row);
}

void UIFormLayout::add_slider(PyStr label, py2cpp::ui::widget::UISlider& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_SLIDER;
  row.label = label;
  row.ctrl = NULL;
  row.bval = false;
  row.sval = PyStr("");
  row.ival = widget.PY2CPP_GETTER(value)();
  row.lo = widget.lo;
  row.hi = widget.hi;
  row.slider = widget;
  st.rows.append(row);
}

void UIFormLayout::add_button(py2cpp::ui::widget::UIPushButton& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIButtonEntry btn;
  btn.text = widget.text;
  btn.ctrl = NULL;
  btn.widget = widget;
  st.buttons.append(btn);
}

void UIFormLayout::apply(py2cpp::ui::window::UIWindow& win)
{
  HWND parent = _ui_form_ctx_hwnd(win);
  if (!parent)
  {
    return;
  }
  UIFormState& st = _ui_form_state(*this);
  if (st.applied && (st.mounted_handle == win.handle))
  {
    return;
  }
  st.applied = true;
  st.mounted_handle = win.handle;
  win.active_form = (PyInt64)((INT_PTR)this);
  size_t i = 0;
  while (i < (size_t)st.rows.__len__())
  {
    _ui_mount_row(win, st.rows.__getitem__((PyInt)i));
    i = (i + 1);
  }
  i = 0;
  while (i < (size_t)st.buttons.__len__())
  {
    _ui_mount_button(win, st.buttons.__getitem__((PyInt)i));
    i = (i + 1);
  }
  _applied = true;
}

void UIFormLayout::sync_from_native(py2cpp::ui::window::UIWindow& win)
{
  (void)win;
  UIFormState& st = _ui_form_state(*this);
  size_t i = 0;
  while (i < (size_t)st.rows.__len__())
  {
    _ui_row_sync_from_native(st.rows.__getitem__((PyInt)i));
    i = (i + 1);
  }
}

void UIFormLayout::sync_to_native(py2cpp::ui::window::UIWindow& win)
{
  (void)win;
  UIFormState& st = _ui_form_state(*this);
  size_t i = 0;
  while (i < (size_t)st.rows.__len__())
  {
    _ui_row_sync_to_native(st.rows.__getitem__((PyInt)i));
    i = (i + 1);
  }
}

PyInt UIFormLayout::row_count()
{
  UIFormState& st = _ui_form_state(*this);
  return st.rows.__len__();
}

PyBool UIFormLayout::row_bool(PyInt index)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return false;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_CHECKBOX)
  {
    return false;
  }
  return row.bval;
}

PyStr UIFormLayout::row_str(PyInt index)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return PyStr("");
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_LINE_EDIT)
  {
    return PyStr("");
  }
  return row.sval;
}

PyInt UIFormLayout::row_int(PyInt index)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return (PyInt)0;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind == UI_ROW_INT_EDIT || row.kind == UI_ROW_SLIDER)
  {
    return row.ival;
  }
  return (PyInt)0;
}

void UIFormLayout::set_row_bool(PyInt index, PyBool value)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_CHECKBOX)
  {
    return;
  }
  row.bval = value;
}

void UIFormLayout::set_row_str(PyInt index, PyStr value)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_LINE_EDIT)
  {
    return;
  }
  row.sval = value;
}

void UIFormLayout::set_row_int(PyInt index, PyInt value)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind == UI_ROW_INT_EDIT || row.kind == UI_ROW_SLIDER)
  {
    row.ival = value;
  }
}

void UIFormLayout::push_row_bool(PyInt index, PyBool value)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_CHECKBOX)
  {
    return;
  }
  row.bval = value;
  row.checkbox.PY2CPP_SETTER(checked)(value);
}

void UIFormLayout::push_row_str(PyInt index, PyStr value)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_LINE_EDIT)
  {
    return;
  }
  row.sval = value;
  row.line_edit.PY2CPP_SETTER(text)(value);
}

void UIFormLayout::push_row_int(PyInt index, PyInt value)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind == UI_ROW_INT_EDIT)
  {
    row.ival = value;
    row.int_edit.PY2CPP_SETTER(value)(value);
    return;
  }
  if (row.kind == UI_ROW_SLIDER)
  {
    row.ival = value;
    row.slider.PY2CPP_SETTER(value)(value);
  }
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

void ui_form_session_reset()
{
}

void ui_form_on_window_end(py2cpp::ui::window::UIWindow& win)
{
  (void)win;
}

PyBool ui_form_on_bn_clicked(py2cpp::ui::window::UIWindow& win, UINT_PTR ctrl_id)
{
  (void)win;
  (void)ctrl_id;
  return false;
}

PyBool ui_form_on_en_change(py2cpp::ui::window::UIWindow& win, UINT_PTR ctrl_id)
{
  (void)win;
  (void)ctrl_id;
  return false;
}

PyBool ui_form_on_hscroll(py2cpp::ui::window::UIWindow& win, HWND ctrl)
{
  (void)win;
  (void)ctrl;
  return false;
}

void UIFormLayout::clear()
{
  _applied = false;
}

void UIFormLayout::add_checkbox(PyStr label, py2cpp::ui::widget::UICheckBox& widget)
{
  (void)label;
  (void)widget;
}

void UIFormLayout::add_line_edit(PyStr label, py2cpp::ui::widget::UILineEdit& widget)
{
  (void)label;
  (void)widget;
}

void UIFormLayout::add_int_edit(PyStr label, py2cpp::ui::widget::UIIntEdit& widget)
{
  (void)label;
  (void)widget;
}

void UIFormLayout::add_slider(PyStr label, py2cpp::ui::widget::UISlider& widget)
{
  (void)label;
  (void)widget;
}

void UIFormLayout::add_button(py2cpp::ui::widget::UIPushButton& widget)
{
  (void)widget;
}

void UIFormLayout::apply(py2cpp::ui::window::UIWindow& win)
{
  (void)win;
  _applied = true;
}

void UIFormLayout::sync_from_native(py2cpp::ui::window::UIWindow& win)
{
  (void)win;
}

void UIFormLayout::sync_to_native(py2cpp::ui::window::UIWindow& win)
{
  (void)win;
}

PyInt UIFormLayout::row_count()
{
  return (PyInt)0;
}

PyBool UIFormLayout::row_bool(PyInt index)
{
  (void)index;
  return false;
}

PyStr UIFormLayout::row_str(PyInt index)
{
  (void)index;
  return PyStr("");
}

PyInt UIFormLayout::row_int(PyInt index)
{
  (void)index;
  return (PyInt)0;
}

void UIFormLayout::set_row_bool(PyInt index, PyBool value)
{
  (void)index;
  (void)value;
}

void UIFormLayout::set_row_str(PyInt index, PyStr value)
{
  (void)index;
  (void)value;
}

void UIFormLayout::set_row_int(PyInt index, PyInt value)
{
  (void)index;
  (void)value;
}

void UIFormLayout::push_row_bool(PyInt index, PyBool value)
{
  (void)index;
  (void)value;
}

void UIFormLayout::push_row_str(PyInt index, PyStr value)
{
  (void)index;
  (void)value;
}

void UIFormLayout::push_row_int(PyInt index, PyInt value)
{
  (void)index;
  (void)value;
}

PY2CPP_END_SCOPE

#endif
