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
#include "ffi/windows.h"

namespace py2cpp {
namespace ui {

static PyBool _ui_flow_ctrl_down()
{
  return (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
}

PyBool ui_flow_on_key(window::PyUIWindow& win, PyInt vk)
{
  if (win.flowShellPtr == 0 || !_ui_flow_ctrl_down())
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
  flow::shell::PyUIFlowShell* sh =
      (flow::shell::PyUIFlowShell*)(INT_PTR)win.flowShellPtr;
  sh->runCanvasMenu(cmd);
  return true;
}

PyBool ui_menu_on_command(window::PyUIWindow& win, UINT_PTR cmd_id)
{
  if (win.flowShellPtr == 0)
  {
    return false;
  }
  py2cpp::ui::flow::shell::PyUIFlowShell* sh =
      (py2cpp::ui::flow::shell::PyUIFlowShell*)(INT_PTR)win.flowShellPtr;
  sh->onMenuCommand((PyInt)cmd_id);
  return true;
}

void ui_flow_shell_on_resize(window::PyUIWindow& win)
{
  if (win.flowShellPtr == 0)
  {
    return;
  }
  flow::shell::PyUIFlowShell* sh = (flow::shell::PyUIFlowShell*)(INT_PTR)win.flowShellPtr;
  sh->layoutShell();
}

}  // namespace ui
}  // namespace py2cpp

PY2CPP_BEGIN_SCOPE

static flow::canvas::PyUIFlowCanvas* _shell_bound_canvas(PyUIFlowShell& sh)
{
  if (sh.boundCanvasPtr == 0)
  {
    return NULL;
  }
  return (flow::canvas::PyUIFlowCanvas*)(INT_PTR)sh.boundCanvasPtr;
}

void PyUIFlowShell::registerShell(window::PyUIWindow& win)
{
  win.flowShellPtr = (PyInt64)((INT_PTR)this);
}

void PyUIFlowShell::bindCanvas(window::PyUIWindow& win, flow::canvas::PyUIFlowCanvas& canvas)
{
  this->boundCanvasPtr = (PyInt64)((INT_PTR)&canvas);
  win.flowCanvasPtr = (PyInt64)((INT_PTR)&canvas);
}

void PyUIFlowShell::invalidateAll()
{
  this->palette.invalidate();
  flow::canvas::PyUIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (cv)
  {
    cv->invalidate();
  }
}

void PyUIFlowShell::layoutShell()
{
  flow::canvas::PyUIFlowCanvas* cv = _shell_bound_canvas(*this);
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
  this->palette.setBounds(0, 0, palette_w, ch);
  PyInt canvas_w = cw - palette_w;
  if (canvas_w < 1)
  {
    canvas_w = 1;
  }
  cv->setBounds(palette_w, 0, canvas_w, ch);
  this->palette.invalidate();
  cv->invalidate();
}

void PyUIFlowShell::runCanvasMenu(PyInt cmd_id)
{
  flow::canvas::PyUIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (!cv)
  {
    return;
  }
  switch (cmd_id)
  {
    case 201:
      cv->deleteSelected();
      break;
    case 202:
      cv->cancelInteraction();
      break;
    case 203:
      cv->undoGraph();
      break;
    case 204:
      cv->redoGraph();
      break;
    case 205:
      cv->clipboardJson = cv->cutSelection();
      break;
    case 206:
      cv->copyToClipboard();
      break;
    case 207:
      cv->pasteFromClipboard();
      break;
    case 208:
      cv->selectAllNodes();
      break;
    case 301:
      cv->zoom = 1.0f;
      cv->panX = 0.0f;
      cv->panY = 0.0f;
      cv->invalidate();
      break;
    default:
      break;
  }
}

void PyUIFlowShell::boundFileNew()
{
  flow::canvas::PyUIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (!cv)
  {
    return;
  }
  cv->history.push(cv->graph);
  cv->graph.clear();
  cv->clearSelection();
  cv->graphChanged();
  cv->invalidate();
}

void PyUIFlowShell::boundFileOpen(PyStr text)
{
  flow::canvas::PyUIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (!cv || !text)
  {
    return;
  }
  flow::serialize::graphFromJson(cv->graph, text);
  cv->clearSelection();
  cv->history.clear();
  cv->graphChanged();
  cv->invalidate();
}

PyStr PyUIFlowShell::boundFileSave()
{
  flow::canvas::PyUIFlowCanvas* cv = _shell_bound_canvas(*this);
  if (!cv)
  {
    return PyStr();
  }
  return flow::serialize::graphToJson(cv->graph);
}

PY2CPP_END_SCOPE

#else

namespace py2cpp {
namespace ui {

PyBool ui_flow_on_key(window::PyUIWindow& win, PyInt vk)
{
  (void)win;
  (void)vk;
  return false;
}

PyBool ui_menu_on_command(window::PyUIWindow& win, UINT_PTR cmd_id)
{
  (void)win;
  (void)cmd_id;
  return false;
}

void ui_flow_shell_on_resize(window::PyUIWindow& win)
{
  (void)win;
}

}  // namespace ui
}  // namespace py2cpp

PY2CPP_BEGIN_SCOPE

void PyUIFlowShell::registerShell(window::PyUIWindow& win)
{
  (void)win;
}

void PyUIFlowShell::bindCanvas(window::PyUIWindow& win, flow::canvas::PyUIFlowCanvas& canvas)
{
  (void)win;
  (void)canvas;
  this->boundCanvasPtr = 0;
}

void PyUIFlowShell::invalidateAll()
{
}

void PyUIFlowShell::layoutShell()
{
}

void PyUIFlowShell::runCanvasMenu(PyInt cmd_id)
{
  (void)cmd_id;
}

void PyUIFlowShell::boundFileNew()
{
}

void PyUIFlowShell::boundFileOpen(PyStr text)
{
  (void)text;
}

PyStr PyUIFlowShell::boundFileSave()
{
  return PyStr();
}

PY2CPP_END_SCOPE

#endif
