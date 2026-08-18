PY2CPP_IGNORE
#include "py2cpp/console/native_sys.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/list.h"
#include "py2cpp/util/tuple.h"
PY2CPP_END

#include "ffi/crt/stdio.h"

#include "ffi/crt/string.h"
#if defined(_WIN32)
#pragma comment(lib, "shell32.lib")
#else
#include "ffi/crt/fcntl.h"
#include "ffi/posix/sys/ioctl.h"
#include "ffi/posix/unistd.h"
#endif

static PyStr _console_chars_to_pystr(const PyChar* p, int n)
{
  if ((!p) || (n <= 0))
  {
    return PyStr("");
  }
  char tmp[4096];
  if (n >= (int)sizeof(tmp))
  {
    n = (int)sizeof(tmp) - 1;
  }
  memcpy(tmp, p, (size_t)n);
  tmp[n] = '\0';
  return PyStr(tmp);
}

PY2CPP_BEGIN_SCOPE

PyList<PyStr> py_nativeArgv()
{
  PyList<PyStr> out;
#if defined(_WIN32)
  int argc = 0;
  PyUInt** wargv = reinterpret_cast<PyUInt**>(::ffi::windows::shellapi::pyiCommandLineToArgvW(::ffi::windows::windows::pyiGetCommandLineW(), &argc));
  if (!wargv)
  {
    return out;
  }
  for (int i = 0; i < argc; i++)
  {
    int n = ::ffi::windows::windows::pyiWideCharToMultiByte(::ffi::windows::windows::PyiCpUtf8, 0, wargv[i], -1, nullptr, 0, nullptr, nullptr);
    if (n <= 1)
    {
      out.append(PyStr(""));
      continue;
    }
    char* buf = (char*)malloc((size_t)n);
    if (!buf)
    {
      out.append(PyStr(""));
      continue;
    }
    ::ffi::windows::windows::pyiWideCharToMultiByte(::ffi::windows::windows::PyiCpUtf8, 0, wargv[i], -1, buf, n, nullptr, nullptr);
    out.append(PyStr(buf));
    free(buf);
  }
  ::ffi::windows::windows::pyiLocalFree((PyUPtr)(uintptr_t)wargv);
#else
  int fd = open("/proc/self/cmdline", O_RDONLY);
  if (fd >= 0)
  {
    char buf[4096];
    int n = (int)read(fd, buf, (size_t)sizeof(buf) - 1);
    close(fd);
    if (n > 0)
    {
      int start = 0;
      for (int i = 0; i <= n; i++)
      {
        if ((i == n) || (buf[i] == '\0'))
        {
          if (i > start)
          {
            out.append(_console_chars_to_pystr(buf + start, i - start));
          }
          start = i + 1;
        }
      }
    }
  }
#endif
  return out;
}



PyTuple<PyInt, PyInt> py_nativeTerminalSize()
{
#if defined(_WIN32)
  ::ffi::windows::windows::PyiConsoleScreenBufferInfo info;
  PyUPtr h = ::ffi::windows::windows::pyiGetStdHandle((PyUInt)-11);
  if ((h != (PyUPtr)-1) && ::ffi::windows::windows::pyiGetConsoleScreenBufferInfo(h, &info))
  {
    int cols = (int)(info.srWindow.Right - info.srWindow.Left + 1);
    int rows = (int)(info.srWindow.Bottom - info.srWindow.Top + 1);
    if (cols < 1)
    {
      cols = 80;
    }
    if (rows < 1)
    {
      rows = 24;
    }
    return PyTuple<PyInt, PyInt>(cols, rows);
  }
#else
  struct winsize ws;
  if ((ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == 0) && (ws.ws_col > 0) && (ws.ws_row > 0))
  {
    return PyTuple<PyInt, PyInt>((PyInt)ws.ws_col, (PyInt)ws.ws_row);
  }
#endif
  return PyTuple<PyInt, PyInt>(80, 24);
}

PY2CPP_END_SCOPE
