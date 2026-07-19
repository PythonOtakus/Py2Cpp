PY2CPP_IGNORE
#include "py2cpp/ui/menu.h"
#include "py2cpp/ui/window.h"
PY2CPP_END

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

enum {
  kFlowMenuFileNew = 1,
  kFlowMenuFileOpen = 2,
  kFlowMenuFileSave = 3,
  kFlowMenuFileSaveAs = 4,
  kFlowMenuFileExit = 100,
  kFlowMenuEditDelete = 201,
  kFlowMenuEditDeselect = 202,
  kFlowMenuEditUndo = 203,
  kFlowMenuEditRedo = 204,
  kFlowMenuEditCut = 205,
  kFlowMenuEditCopy = 206,
  kFlowMenuEditPaste = 207,
  kFlowMenuEditSelectAll = 208,
  kFlowMenuViewResetZoom = 301,
  kFlowMenuRunPlay = 401,
  kFlowMenuRunPlaySelected = 402,
  kFlowMenuRunStop = 403,
};

static HMENU _ui_menu_create_flow()
{
  HMENU bar = CreateMenu();
  HMENU file = CreatePopupMenu();
  HMENU edit = CreatePopupMenu();
  HMENU view = CreatePopupMenu();
  HMENU run = CreatePopupMenu();
  AppendMenuA(file, MF_STRING, kFlowMenuFileNew, "&New\tCtrl+N");
  AppendMenuA(file, MF_STRING, kFlowMenuFileOpen, "&Open...\tCtrl+O");
  AppendMenuA(file, MF_STRING, kFlowMenuFileSave, "&Save\tCtrl+S");
  AppendMenuA(file, MF_STRING, kFlowMenuFileSaveAs, "Save &As...\tCtrl+Shift+S");
  AppendMenuA(file, MF_SEPARATOR, 0, NULL);
  AppendMenuA(file, MF_STRING, kFlowMenuFileExit, "E&xit");
  AppendMenuA(edit, MF_STRING, kFlowMenuEditUndo, "&Undo\tCtrl+Z");
  AppendMenuA(edit, MF_STRING, kFlowMenuEditRedo, "&Redo\tCtrl+Y");
  AppendMenuA(edit, MF_SEPARATOR, 0, NULL);
  AppendMenuA(edit, MF_STRING, kFlowMenuEditCut, "Cu&t\tCtrl+X");
  AppendMenuA(edit, MF_STRING, kFlowMenuEditCopy, "&Copy\tCtrl+C");
  AppendMenuA(edit, MF_STRING, kFlowMenuEditPaste, "&Paste\tCtrl+V");
  AppendMenuA(edit, MF_SEPARATOR, 0, NULL);
  AppendMenuA(edit, MF_STRING, kFlowMenuEditSelectAll, "Select &All\tCtrl+A");
  AppendMenuA(edit, MF_STRING, kFlowMenuEditDeselect, "&Deselect\tEsc");
  AppendMenuA(edit, MF_STRING, kFlowMenuEditDelete, "&Delete\tDel");
  AppendMenuA(view, MF_STRING, kFlowMenuViewResetZoom, "Reset &Zoom\tCtrl+0");
  AppendMenuA(run, MF_STRING | MF_GRAYED, kFlowMenuRunPlay, "&Play\tF5");
  AppendMenuA(run, MF_STRING | MF_GRAYED, kFlowMenuRunPlaySelected, "Play from &Selected\tCtrl+F5");
  AppendMenuA(run, MF_STRING | MF_GRAYED, kFlowMenuRunStop, "&Stop\tShift+F5");
  AppendMenuA(bar, MF_POPUP, (UINT_PTR)file, "&File");
  AppendMenuA(bar, MF_POPUP, (UINT_PTR)edit, "&Edit");
  AppendMenuA(bar, MF_POPUP, (UINT_PTR)view, "&View");
  AppendMenuA(bar, MF_POPUP, (UINT_PTR)run, "&Run");
  return bar;
}

PY2CPP_BEGIN_SCOPE

void UIMenuBar::attach(window::UIWindow& win)
{
  HWND hwnd = (HWND)(INT_PTR)win.handle;
  if (!hwnd)
  {
    return;
  }
  HMENU bar = _ui_menu_create_flow();
  this->handle = (PyInt64)((INT_PTR)bar);
  SetMenu(hwnd, bar);
  DrawMenuBar(hwnd);
}

void UIMenuBar::build_flow_default()
{
}

void UIMenuBar::set_run_enabled(PyBool play, PyBool play_sel, PyBool stop)
{
  HMENU bar = (HMENU)(INT_PTR)this->handle;
  if (!bar)
  {
    return;
  }
  HMENU run = GetSubMenu(bar, 3);
  if (!run)
  {
    return;
  }
  EnableMenuItem(run, kFlowMenuRunPlay, MF_BYCOMMAND | (play ? MF_ENABLED : MF_GRAYED));
  EnableMenuItem(run, kFlowMenuRunPlaySelected, MF_BYCOMMAND | (play_sel ? MF_ENABLED : MF_GRAYED));
  EnableMenuItem(run, kFlowMenuRunStop, MF_BYCOMMAND | (stop ? MF_ENABLED : MF_GRAYED));
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

void UIMenuBar::attach(window::UIWindow& win)
{
  (void)win;
}

void UIMenuBar::build_flow_default()
{
}

void UIMenuBar::set_run_enabled(PyBool play, PyBool play_sel, PyBool stop)
{
  (void)play;
  (void)play_sel;
  (void)stop;
}

PY2CPP_END_SCOPE

#endif
