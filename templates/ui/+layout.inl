PY2CPP_IGNORE
#include "py2cpp/ui/layout.h"
#include "py2cpp/ui/window.h"
#include "py2cpp/ui/widget.h"
#include "py2cpp/ui/events.h"
#include "py2cpp/util/list.h"
#include "py2cpp/util/dict.h"
PY2CPP_END

#include "ffi/crt/stdio.h"
#include "ffi/crt/stdlib.h"
#include "ffi/crt/string.h"

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows.h"
#include "ffi/windows/commctrl.h"

namespace py2cpp {
namespace ui {
namespace window {
void ui_theme_ensure_process();
void ui_theme_attach_panel(HWND hwnd, PyUIWindow& ctx);
void ui_theme_apply_font(HWND hwnd);
void ui_theme_layout_metrics(
    const PyUIWindow& ctx,
    int* pad_x,
    int* label_w,
    int* row_h,
    int* rowSpacing,
    int* slider_h,
    int* edit_w,
    int* edit_h,
    int* slider_w,
    int* formSpacing);
int ui_theme_scale_ctx(const PyUIWindow& ctx, int px);
HBRUSH ui_theme_panel_brush();
HBRUSH ui_theme_on_ctl_color(HDC hdc);
} // namespace window
namespace layout {
void ui_form_session_reset();
void ui_form_on_window_end(window::PyUIWindow& win);
PyBool ui_form_on_bn_clicked(window::PyUIWindow& win, UINT_PTR ctrl_id);
PyBool ui_form_on_en_change(window::PyUIWindow& win, UINT_PTR ctrl_id);
PyBool ui_form_on_hscroll(window::PyUIWindow& win, HWND ctrl);
} // namespace layout
} // namespace ui
} // namespace py2cpp

enum UIRowKind {
  UI_ROW_CHECKBOX = 0,
  UI_ROW_LINE_EDIT = 1,
  UI_ROW_INT_EDIT = 2,
  UI_ROW_SLIDER = 3,
  UI_ROW_FLOAT_EDIT = 4,
};

struct UIRowEntry
{
  UIRowKind kind;
  PyStr label;
  HWND ctrl;
  PyBool bval;
  PyStr sval;
  PyInt ival;
  PyFloat64 fval;
  PyInt lo;
  PyInt hi;
  py2cpp::ui::widget::PyUICheckBox checkbox;
  py2cpp::ui::widget::PyUILineEdit line_edit;
  py2cpp::ui::widget::PyUIIntEdit int_edit;
  py2cpp::ui::widget::PyUIFloatEdit float_edit;
  py2cpp::ui::widget::PyUISlider slider;
};

struct UIButtonEntry
{
  PyStr text;
  HWND ctrl;
  py2cpp::ui::widget::PyUIPushButton widget;
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

static UIFormState& _ui_form_state(PyUIFormLayout& form)
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

static HWND _ui_form_ctx_hwnd(const py2cpp::ui::window::PyUIWindow& self)
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

static void _ui_layout_row(py2cpp::ui::window::PyUIWindow& self, PyStr label, HWND ctrl, int ctrl_w, int ctrl_h)
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
  PyInt rowSpacing = 0;
  PyInt slider_h = 0;
  PyInt edit_w = 0;
  PyInt edit_h = 0;
  PyInt slider_w = 0;
  PyInt formSpacing = 0;
  py2cpp::ui::window::ui_theme_layout_metrics(
      self,
      &pad_x,
      &label_w,
      &row_h,
      &rowSpacing,
      &slider_h,
      &edit_w,
      &edit_h,
      &slider_w,
      &formSpacing);
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
  label.copyToSpan(PySpan<PyByte>((PyByte*)lbuf, (PyInt)sizeof(lbuf), 1));
  int y = self.nextY;
  int ctrl_x = pad_x + label_w + formSpacing;
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
  self.nextY = (PyInt)(y + slot_h + rowSpacing);
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
      row.ival = (PyInt)::ffi::crt::stdlib::pyiAtoi(buf);
      break;
    }
    case UI_ROW_FLOAT_EDIT: {
      char buf[64];
      _ui_read_edit_text(row.ctrl, buf, (int)sizeof(buf));
      row.fval = (PyFloat64)::ffi::crt::stdlib::pyiAtof(buf);
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
      row.sval.copyToSpan(PySpan<PyByte>((PyByte*)vbuf, (PyInt)sizeof(vbuf), 1));
      SetWindowTextA(row.ctrl, vbuf);
      break;
    }
    case UI_ROW_INT_EDIT: {
      char vbuf[32];
      ::ffi::crt::stdio::pyiSnprintf(vbuf, sizeof(vbuf), "%d", (int)row.ival);
      SetWindowTextA(row.ctrl, vbuf);
      break;
    }
    case UI_ROW_FLOAT_EDIT: {
      char vbuf[64];
      ::ffi::crt::stdio::pyiSnprintf(vbuf, sizeof(vbuf), "%.6g", (double)row.fval);
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
  py2cpp::ui::widget::PyUIWidget* widget = NULL;
  switch (row.kind)
  {
    case UI_ROW_CHECKBOX:
      widget = reinterpret_cast<py2cpp::ui::widget::PyUIWidget*>(&row.checkbox);
      break;
    case UI_ROW_LINE_EDIT:
      widget = reinterpret_cast<py2cpp::ui::widget::PyUIWidget*>(&row.line_edit);
      break;
    case UI_ROW_INT_EDIT:
      widget = reinterpret_cast<py2cpp::ui::widget::PyUIWidget*>(&row.int_edit);
      break;
    case UI_ROW_FLOAT_EDIT:
      widget = reinterpret_cast<py2cpp::ui::widget::PyUIWidget*>(&row.float_edit);
      break;
    case UI_ROW_SLIDER:
      widget = reinterpret_cast<py2cpp::ui::widget::PyUIWidget*>(&row.slider);
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

static void _ui_mount_row(py2cpp::ui::window::PyUIWindow& win, UIRowEntry& row)
{
  HWND parent = _ui_form_ctx_hwnd(win);
  if (!parent)
  {
    return;
  }
  switch (row.kind)
  {
    case UI_ROW_CHECKBOX: {
      PyInt box_w = py2cpp::ui::window::ui_theme_scale_ctx(win, win.style.checkboxSize.template get<0>());
      PyInt box_h = py2cpp::ui::window::ui_theme_scale_ctx(win, win.style.checkboxSize.template get<1>());
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
      row.sval.copyToSpan(PySpan<PyByte>((PyByte*)vbuf, (PyInt)sizeof(vbuf), 1));
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
      ::ffi::crt::stdio::pyiSnprintf(vbuf, sizeof(vbuf), "%d", (int)row.ival);
      row.ctrl = _ui_create_edit(parent, vbuf, edit_w, edit_h);
      _ui_layout_row(win, row.label, row.ctrl, edit_w, edit_h);
      _ui_row_mount_widget_handle(row);
      break;
    }
    case UI_ROW_FLOAT_EDIT: {
      PyInt edit_w = 0;
      PyInt edit_h = 0;
      py2cpp::ui::window::ui_theme_layout_metrics(
          win, NULL, NULL, NULL, NULL, NULL, &edit_w, &edit_h, NULL, NULL);
      char vbuf[64];
      ::ffi::crt::stdio::pyiSnprintf(vbuf, sizeof(vbuf), "%.6g", (double)row.fval);
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

static void _ui_mount_button(py2cpp::ui::window::PyUIWindow& win, UIButtonEntry& btn)
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
  btn_w = py2cpp::ui::window::ui_theme_scale_ctx(win, win.style.buttonSize.template get<0>());
  if (btn_h <= 0)
  {
    btn_h = py2cpp::ui::window::ui_theme_scale_ctx(win, win.style.buttonSize.template get<1>());
  }
  char lbuf[256];
  btn.text.copyToSpan(PySpan<PyByte>((PyByte*)lbuf, (PyInt)sizeof(lbuf), 1));
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
    case UI_ROW_FLOAT_EDIT: {
      row.float_edit.PY2CPP_SETTER(value)(row.fval);
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

PyBool ui_form_on_bn_clicked(py2cpp::ui::window::PyUIWindow& win, UINT_PTR ctrl_id)
{
  if (!win.activeForm)
  {
    return false;
  }
PyUIFormLayout* form = reinterpret_cast<PyUIFormLayout*>((void*)(INT_PTR)win.activeForm);
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
  form->syncFromNative(win);
  _ui_row_fire_value_changed(*row);
  return true;
}

PyBool ui_form_on_en_change(py2cpp::ui::window::PyUIWindow& win, UINT_PTR ctrl_id)
{
  if (!win.activeForm)
  {
    return false;
  }
PyUIFormLayout* form = reinterpret_cast<PyUIFormLayout*>((void*)(INT_PTR)win.activeForm);
  if (!form)
  {
    return false;
  }
  UIFormState& st = _ui_form_state(*form);
  UIRowEntry* row = _ui_form_find_row_by_ctrl(st, ctrl_id);
  if ((!row)
      || ((row->kind != UI_ROW_LINE_EDIT)
          && (row->kind != UI_ROW_INT_EDIT)
          && (row->kind != UI_ROW_FLOAT_EDIT)))
      {
    return false;
  }
  form->syncFromNative(win);
  _ui_row_fire_value_changed(*row);
  return true;
}

PyBool ui_form_on_hscroll(py2cpp::ui::window::PyUIWindow& win, HWND ctrl)
{
  if ((!win.activeForm) || (!ctrl))
  {
    return false;
  }
PyUIFormLayout* form = reinterpret_cast<PyUIFormLayout*>((void*)(INT_PTR)win.activeForm);
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

void ui_form_on_window_end(py2cpp::ui::window::PyUIWindow& win)
{
  if (!win.activeForm)
  {
    return;
  }
PyUIFormLayout* form = reinterpret_cast<PyUIFormLayout*>((void*)(INT_PTR)win.activeForm);
  if (!form)
  {
    return;
  }
  UIFormState& st = _ui_form_state(*form);
  st.applied = false;
  st.mounted_handle = (PyInt64)0;
  win.activeForm = (PyInt64)0;
}

void PyUIFormLayout::clear()
{
  UIFormState& st = _ui_form_state(*this);
  st.rows.clear();
  st.buttons.clear();
  st.applied = false;
  st.mounted_handle = (PyInt64)0;
  _applied = false;
}

void PyUIFormLayout::addCheckbox(PyStr label, py2cpp::ui::widget::PyUICheckBox& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_CHECKBOX;
  row.label = label;
  row.ctrl = NULL;
  row.bval = widget.PY2CPP_GETTER(checked)();
  row.sval = PyStr("");
  row.ival = 0;
  row.fval = 0.0;
  row.lo = 0;
  row.hi = 0;
  row.checkbox = widget;
  st.rows.append(row);
}

void PyUIFormLayout::addLineEdit(PyStr label, py2cpp::ui::widget::PyUILineEdit& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_LINE_EDIT;
  row.label = label;
  row.ctrl = NULL;
  row.bval = false;
  row.sval = widget.PY2CPP_GETTER(text)();
  row.ival = 0;
  row.fval = 0.0;
  row.lo = 0;
  row.hi = 0;
  row.line_edit = widget;
  st.rows.append(row);
}

void PyUIFormLayout::addIntEdit(PyStr label, py2cpp::ui::widget::PyUIIntEdit& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_INT_EDIT;
  row.label = label;
  row.ctrl = NULL;
  row.bval = false;
  row.sval = PyStr("");
  row.ival = widget.PY2CPP_GETTER(value)();
  row.fval = 0.0;
  row.lo = 0;
  row.hi = 0;
  row.int_edit = widget;
  st.rows.append(row);
}

void PyUIFormLayout::addFloatEdit(PyStr label, py2cpp::ui::widget::PyUIFloatEdit& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_FLOAT_EDIT;
  row.label = label;
  row.ctrl = NULL;
  row.bval = false;
  row.sval = PyStr("");
  row.ival = 0;
  row.fval = widget.PY2CPP_GETTER(value)();
  row.lo = 0;
  row.hi = 0;
  row.float_edit = widget;
  st.rows.append(row);
}

void PyUIFormLayout::addSlider(PyStr label, py2cpp::ui::widget::PyUISlider& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIRowEntry row;
  row.kind = UI_ROW_SLIDER;
  row.label = label;
  row.ctrl = NULL;
  row.bval = false;
  row.sval = PyStr("");
  row.ival = widget.PY2CPP_GETTER(value)();
  row.fval = 0.0;
  row.lo = widget.lo;
  row.hi = widget.hi;
  row.slider = widget;
  st.rows.append(row);
}

void PyUIFormLayout::addButton(py2cpp::ui::widget::PyUIPushButton& widget)
{
  UIFormState& st = _ui_form_state(*this);
  UIButtonEntry btn;
  btn.text = widget.text;
  btn.ctrl = NULL;
  btn.widget = widget;
  st.buttons.append(btn);
}

void PyUIFormLayout::apply(py2cpp::ui::window::PyUIWindow& win)
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
  win.activeForm = (PyInt64)((INT_PTR)this);
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

void PyUIFormLayout::syncFromNative(py2cpp::ui::window::PyUIWindow& win)
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

void PyUIFormLayout::syncToNative(py2cpp::ui::window::PyUIWindow& win)
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

PyInt PyUIFormLayout::rowCount()
{
  UIFormState& st = _ui_form_state(*this);
  return st.rows.__len__();
}

PyBool PyUIFormLayout::rowBool(PyInt index)
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

PyStr PyUIFormLayout::rowStr(PyInt index)
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

PyInt PyUIFormLayout::rowInt(PyInt index)
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

PyFloat64 PyUIFormLayout::rowFloat(PyInt index)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return (PyFloat64)0.0;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_FLOAT_EDIT)
  {
    return (PyFloat64)0.0;
  }
  return row.fval;
}

void PyUIFormLayout::setRowBool(PyInt index, PyBool value)
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

void PyUIFormLayout::setRowStr(PyInt index, PyStr value)
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

void PyUIFormLayout::setRowInt(PyInt index, PyInt value)
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

void PyUIFormLayout::setRowFloat(PyInt index, PyFloat64 value)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_FLOAT_EDIT)
  {
    return;
  }
  row.fval = value;
}

void PyUIFormLayout::pushRowBool(PyInt index, PyBool value)
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

void PyUIFormLayout::pushRowStr(PyInt index, PyStr value)
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

void PyUIFormLayout::pushRowInt(PyInt index, PyInt value)
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

void PyUIFormLayout::pushRowFloat(PyInt index, PyFloat64 value)
{
  UIFormState& st = _ui_form_state(*this);
  if ((index < 0) || (index >= st.rows.__len__()))
  {
    return;
  }
  UIRowEntry& row = st.rows.__getitem__(index);
  if (row.kind != UI_ROW_FLOAT_EDIT)
  {
    return;
  }
  row.fval = value;
  row.float_edit.PY2CPP_SETTER(value)(value);
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

void ui_form_session_reset()
{
}

void ui_form_on_window_end(py2cpp::ui::window::PyUIWindow& win)
{
  (void)win;
}

PyBool ui_form_on_bn_clicked(py2cpp::ui::window::PyUIWindow& win, UINT_PTR ctrl_id)
{
  (void)win;
  (void)ctrl_id;
  return false;
}

PyBool ui_form_on_en_change(py2cpp::ui::window::PyUIWindow& win, UINT_PTR ctrl_id)
{
  (void)win;
  (void)ctrl_id;
  return false;
}

PyBool ui_form_on_hscroll(py2cpp::ui::window::PyUIWindow& win, HWND ctrl)
{
  (void)win;
  (void)ctrl;
  return false;
}

void PyUIFormLayout::clear()
{
  _applied = false;
}

void PyUIFormLayout::addCheckbox(PyStr label, py2cpp::ui::widget::PyUICheckBox& widget)
{
  (void)label;
  (void)widget;
}

void PyUIFormLayout::addLineEdit(PyStr label, py2cpp::ui::widget::PyUILineEdit& widget)
{
  (void)label;
  (void)widget;
}

void PyUIFormLayout::addIntEdit(PyStr label, py2cpp::ui::widget::PyUIIntEdit& widget)
{
  (void)label;
  (void)widget;
}

void PyUIFormLayout::addFloatEdit(PyStr label, py2cpp::ui::widget::PyUIFloatEdit& widget)
{
  (void)label;
  (void)widget;
}

void PyUIFormLayout::addSlider(PyStr label, py2cpp::ui::widget::PyUISlider& widget)
{
  (void)label;
  (void)widget;
}

void PyUIFormLayout::addButton(py2cpp::ui::widget::PyUIPushButton& widget)
{
  (void)widget;
}

void PyUIFormLayout::apply(py2cpp::ui::window::PyUIWindow& win)
{
  (void)win;
  _applied = true;
}

void PyUIFormLayout::syncFromNative(py2cpp::ui::window::PyUIWindow& win)
{
  (void)win;
}

void PyUIFormLayout::syncToNative(py2cpp::ui::window::PyUIWindow& win)
{
  (void)win;
}

PyInt PyUIFormLayout::rowCount()
{
  return (PyInt)0;
}

PyBool PyUIFormLayout::rowBool(PyInt index)
{
  (void)index;
  return false;
}

PyStr PyUIFormLayout::rowStr(PyInt index)
{
  (void)index;
  return PyStr("");
}

PyInt PyUIFormLayout::rowInt(PyInt index)
{
  (void)index;
  return (PyInt)0;
}

PyFloat64 PyUIFormLayout::rowFloat(PyInt index)
{
  (void)index;
  return (PyFloat64)0.0;
}

void PyUIFormLayout::setRowBool(PyInt index, PyBool value)
{
  (void)index;
  (void)value;
}

void PyUIFormLayout::setRowStr(PyInt index, PyStr value)
{
  (void)index;
  (void)value;
}

void PyUIFormLayout::setRowInt(PyInt index, PyInt value)
{
  (void)index;
  (void)value;
}

void PyUIFormLayout::setRowFloat(PyInt index, PyFloat64 value)
{
  (void)index;
  (void)value;
}

void PyUIFormLayout::pushRowBool(PyInt index, PyBool value)
{
  (void)index;
  (void)value;
}

void PyUIFormLayout::pushRowStr(PyInt index, PyStr value)
{
  (void)index;
  (void)value;
}

void PyUIFormLayout::pushRowInt(PyInt index, PyInt value)
{
  (void)index;
  (void)value;
}

void PyUIFormLayout::pushRowFloat(PyInt index, PyFloat64 value)
{
  (void)index;
  (void)value;
}

PY2CPP_END_SCOPE

#endif
