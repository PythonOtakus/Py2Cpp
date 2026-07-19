PY2CPP_IGNORE
#include "py2cpp/ui/flow/shell.h"
#include "py2cpp/ui/flow/canvas.h"
#include "py2cpp/ui/flow/serialize.h"
#include "py2cpp/ui/window.h"
PY2CPP_END

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

namespace py2cpp {
namespace ui {

static PyBool _ui_flow_ctrl_down()
{
  return (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
}

PyBool ui_flow_on_key(window::UIWindow& win, PyInt vk)
{
  if (win.flow_shell_ptr == 0 || !_ui_flow_ctrl_down())
  {
    return false;
  }
  PyInt cmd = 0;
  switch (vk)
  {
    case 'Z':
      cmd = 203;
      break;
    case 'Y':
      cmd = 204;
      break;
    case 'X':
      cmd = 205;
      break;
    case 'C':
      cmd = 206;
      break;
    case 'V':
      cmd = 207;
      break;
    case 'A':
      cmd = 208;
      break;
    default:
      return false;
  }
  flow::shell::UIFlowShell* sh =
      (flow::shell::UIFlowShell*)(INT_PTR)win.flow_shell_ptr;
  sh->run_canvas_menu(cmd);
  return true;
}

PyBool ui_menu_on_command(window::UIWindow& win, UINT_PTR cmd_id)
{
  if (win.flow_shell_ptr == 0)
  {
    return false;
  }
  py2cpp::ui::flow::shell::UIFlowShell* sh =
      (py2cpp::ui::flow::shell::UIFlowShell*)(INT_PTR)win.flow_shell_ptr;
  sh->on_menu_command((PyInt)cmd_id);
  return true;
}

void ui_flow_shell_on_resize(window::UIWindow& win)
{
  if (win.flow_shell_ptr == 0)
  {
    return;
  }
  flow::shell::UIFlowShell* sh = (flow::shell::UIFlowShell*)(INT_PTR)win.flow_shell_ptr;
  sh->layout_shell();
}

}  // namespace ui
}  // namespace py2cpp

PY2CPP_BEGIN_SCOPE

static flow::canvas::UIFlowCanvas* _shell_bound_canvas(UIFlowShell& sh)
{
  if (sh.bound_canvas_ptr == 0)
  {
    return NULL;
  }
  return (flow::canvas::UIFlowCanvas*)(INT_PTR)sh.bound_canvas_ptr;
}

void UIFlowShell::register_shell(window::UIWindow& win)
{
  win.flow_shell_ptr = (PyInt64)((INT_PTR)this);
}

void UIFlowShell::bind_canvas(window::UIWindow& win, flow::canvas::UIFlowCanvas& canvas)
{
  this->bound_canvas_ptr = (PyInt64)((INT_PTR)&canvas);
  win.flow_canvas_ptr = (PyInt64)((INT_PTR)&canvas);
}

void UIFlowShell::invalidate_all()
{
  this->palette.invalidate();
  flow::canvas::UIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (cv)
  {
    cv->invalidate();
  }
}

void UIFlowShell::layout_shell()
{
  flow::canvas::UIFlowCanvas* cv = _shell_bound_canvas(*this);
  HWND parent = (HWND)(INT_PTR)this->win.handle;
  if (!parent || !cv)
  {
    return;
  }
  RECT rc;
  GetClientRect(parent, &rc);
  PyInt cw = rc.right - rc.left;
  PyInt ch = rc.bottom - rc.top;
  PyInt palette_w = 240;
  if (palette_w > cw)
  {
    palette_w = cw;
  }
  this->palette.set_bounds(0, 0, palette_w, ch);
  PyInt canvas_w = cw - palette_w;
  if (canvas_w < 1)
  {
    canvas_w = 1;
  }
  cv->set_bounds(palette_w, 0, canvas_w, ch);
  this->palette.invalidate();
  cv->invalidate();
}

void UIFlowShell::run_canvas_menu(PyInt cmd_id)
{
  flow::canvas::UIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (!cv)
  {
    return;
  }
  switch (cmd_id)
  {
    case 201:
      cv->delete_selected();
      break;
    case 202:
      cv->cancel_interaction();
      break;
    case 203:
      cv->undo_graph();
      break;
    case 204:
      cv->redo_graph();
      break;
    case 205:
      cv->clipboard_json = cv->cut_selection();
      break;
    case 206:
      cv->copy_to_clipboard();
      break;
    case 207:
      cv->paste_from_clipboard();
      break;
    case 208:
      cv->select_all_nodes();
      break;
    case 301:
      cv->zoom = 1.0f;
      cv->pan_x = 0.0f;
      cv->pan_y = 0.0f;
      cv->invalidate();
      break;
    default:
      break;
  }
}

void UIFlowShell::bound_file_new()
{
  flow::canvas::UIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (!cv)
  {
    return;
  }
  cv->history.push(cv->graph);
  cv->graph.clear();
  cv->clear_selection();
  cv->graph_changed();
  cv->invalidate();
}

void UIFlowShell::bound_file_open(PyStr text)
{
  flow::canvas::UIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (!cv || !text)
  {
    return;
  }
  flow::serialize::graph_from_json(cv->graph, text);
  cv->clear_selection();
  cv->history.clear();
  cv->graph_changed();
  cv->invalidate();
}

PyStr UIFlowShell::bound_file_save()
{
  flow::canvas::UIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (!cv)
  {
    return PyStr();
  }
  return flow::serialize::graph_to_json(cv->graph);
}

PY2CPP_END_SCOPE

#else

namespace py2cpp {
namespace ui {

PyBool ui_flow_on_key(window::UIWindow& win, PyInt vk)
{
  (void)win;
  (void)vk;
  return false;
}

PyBool ui_menu_on_command(window::UIWindow& win, UINT_PTR cmd_id)
{
  (void)win;
  (void)cmd_id;
  return false;
}

void ui_flow_shell_on_resize(window::UIWindow& win)
{
  (void)win;
}

}  // namespace ui
}  // namespace py2cpp

PY2CPP_BEGIN_SCOPE

void UIFlowShell::register_shell(window::UIWindow& win)
{
  (void)win;
}

void UIFlowShell::bind_canvas(window::UIWindow& win, flow::canvas::UIFlowCanvas& canvas)
{
  (void)win;
  (void)canvas;
  this->bound_canvas_ptr = 0;
}

void UIFlowShell::invalidate_all()
{
}

void UIFlowShell::layout_shell()
{
}

void UIFlowShell::run_canvas_menu(PyInt cmd_id)
{
  (void)cmd_id;
}

void UIFlowShell::bound_file_new()
{
}

void UIFlowShell::bound_file_open(PyStr text)
{
  (void)text;
}

PyStr UIFlowShell::bound_file_save()
{
  return PyStr();
}

PY2CPP_END_SCOPE

#endif
