PY2CPP_IGNORE
#include "py2cpp/ui/file_dialog.h"
PY2CPP_END

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows.h"
#include "ffi/windows/commdlg.h"
#pragma comment(lib, "comdlg32.lib")

static PyStr _ui_pick_file(PyBool save, PyStr title, PyStr default_name)
{
  char path[MAX_PATH] = {};
  if (save && default_name.__len__() > 0)
  {
    default_name.copyToSpanUtf8(PySpan<PyByte>((PyByte*)path, (PyInt)sizeof(path), 1));
  }
  OPENFILENAMEA ofn = {};
  ofn.lStructSize = sizeof(ofn);
  ofn.hwndOwner = NULL;
  ofn.lpstrFilter = "Flow JSON (*.flow.json)\0*.flow.json\0All (*.*)\0*.*\0";
  ofn.lpstrFile = path;
  ofn.nMaxFile = MAX_PATH;
  char tbuf[256];
  title.copyToSpanUtf8(PySpan<PyByte>((PyByte*)tbuf, (PyInt)sizeof(tbuf), 1));
  ofn.lpstrTitle = tbuf;
  PyBool ok = false;
  if (save)
  {
    ofn.Flags = OFN_PATHMUSTEXIST | OFN_OVERWRITEPROMPT;
    ok = GetSaveFileNameA(&ofn) ? true : false;
  }
  else
  {
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST;
    ok = GetOpenFileNameA(&ofn) ? true : false;
  }
  if (!ok)
  {
    return PyStr("");
  }
  return PyStr(path);
}

PY2CPP_BEGIN_SCOPE

PyStr pickOpenFile(const PyStr& title, const PyStr& filter_ext)
{
  (void)filter_ext;
  return _ui_pick_file(false, title, PyStr(""));
}

PyStr pickSaveFile(const PyStr& title, const PyStr& filter_ext, const PyStr& default_name)
{
  (void)filter_ext;
  return _ui_pick_file(true, title, default_name);
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

PyStr pickOpenFile(PyStr title, PyStr filter_ext)
{
  (void)title;
  (void)filter_ext;
  return PyStr("");
}

PyStr pickSaveFile(PyStr title, PyStr filter_ext, PyStr default_name)
{
  (void)title;
  (void)filter_ext;
  (void)default_name;
  return PyStr("");
}

PY2CPP_END_SCOPE

#endif
