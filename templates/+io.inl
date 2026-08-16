PY2CPP_IGNORE
#include "py2cpp/io.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/list.h"
#include "py2cpp/core/iter_result.h"
PY2CPP_END

#include <stdio.h>
#include <string.h>
#if defined(_WIN32)
#include <io.h>
#else
#include <unistd.h>
#endif

static FILE* _io_fp(PyUPtr fp)
{
  return (FILE*)(uintptr_t)fp;
}

PyTextIOWrapper::PyTextIOWrapper(PyStr path, PyStr mode)
{
  _fp = 0;
  _closed = false;
  _owns = true;
  char pbuf[4096];
  char mbuf[16];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  if (mode.__len__() <= 0)
  {
    mbuf[0] = 'r';
    mbuf[1] = '\0';
  }
  else
  {
    mode.copyToSpan(PySpan<PyByte>((PyByte*)mbuf, (PyInt)sizeof(mbuf), 1));
  }
#if defined(_MSC_VER)
#pragma warning(push)
#pragma warning(disable: 4996)
#endif
  _fp = (PyUPtr)(uintptr_t)fopen(pbuf, mbuf);
#if defined(_MSC_VER)
#pragma warning(pop)
#endif
  if (!_fp)
  {
    _closed = true;
  }
}

PyTextIOWrapper::PyTextIOWrapper(PyUPtr fp, PyBool owns)
{
  _fp = fp;
  _closed = (fp == 0);
  _owns = owns;
}

PyTextIOWrapper::PyTextIOWrapper(PyTextIOWrapper&& other)
{
  _fp = other._fp;
  _closed = other._closed;
  _owns = other._owns;
  other._fp = 0;
  other._closed = true;
  other._owns = false;
}

PyTextIOWrapper& PyTextIOWrapper::operator=(PyTextIOWrapper&& other)
{
  if (this != &other)
  {
    this->close();
    _fp = other._fp;
    _closed = other._closed;
    _owns = other._owns;
    other._fp = 0;
    other._closed = true;
    other._owns = false;
  }
  return *this;
}

PyTextIOWrapper::~PyTextIOWrapper()
{
  if ((_fp) && (!_closed) && _owns)
  {
    fclose(_io_fp(_fp));
    _fp = 0;
    _closed = true;
  }
}

void PyTextIOWrapper::close()
{
  if ((_fp) && (!_closed))
  {
    fflush(_io_fp(_fp));
    if (_owns)
    {
      fclose(_io_fp(_fp));
      _fp = 0;
    }
  }
  _closed = true;
}

void PyTextIOWrapper::flush()
{
  if ((_fp) && (!_closed))
  {
    fflush(_io_fp(_fp));
  }
}

PyBool PyTextIOWrapper::isAtty__get() const
{
  if ((!_fp) || _closed)
  {
    return false;
  }
#if defined(_WIN32)
  return (_isatty(_fileno(_io_fp(_fp))) != 0);
#else
  return (isatty(fileno(_io_fp(_fp))) != 0);
#endif
}

PyBool PyTextIOWrapper::__bool__() const
{
  return ((_fp != 0) && (!_closed));
}

PyTextIOWrapper::operator PyBool() const
{
  return __bool__();
}

PyInt PyTextIOWrapper::tell()
{
  if ((!_fp) || (_closed))
  {
    return -1;
  }
  return (int)ftell(_io_fp(_fp));
}

PyInt PyTextIOWrapper::seek(PyInt pos, PyInt whence)
{
  if ((!_fp) || (_closed))
  {
    return -1;
  }
  int origin = SEEK_SET;
  if (whence == 1)
  {
    origin = SEEK_CUR;
  } else if (whence == 2)
  {
    origin = SEEK_END;
  }
  return (fseek(_io_fp(_fp), (long)pos, origin) == 0) ? 0 : -1;
}

PyStr PyTextIOWrapper::read(PyInt size)
{
  if ((!_fp) || (_closed))
  {
    return PyStr("");
  }
  if (size < 0)
  {
    char stack[4096];
    PyArray<PyChar> codes;
    int total = 0;
    while (true)
    {
      int n = (int)fread(stack, 1, (size_t)sizeof(stack), _io_fp(_fp));
      if (n <= 0)
      {
        break;
      }
      int old = codes.__len__();
      codes.reshape((old + n), old);
      for (int i = 0; i < n; i++)
      {
        codes.__setitem__((old + i), (PyChar)(unsigned char)stack[i]);
      }
      total = (total + n);
    }
    if (total <= 0)
    {
      return PyStr("");
    }
    return PyStr(codes);
  }
  char stack[4096];
  int cap = (int)sizeof(stack);
  if ((size >= 0) && (size < cap))
  {
    cap = size;
  }
  if (cap <= 0)
  {
    return PyStr("");
  }
  int n = (int)fread(stack, 1, (size_t)cap, _io_fp(_fp));
  if (n <= 0)
  {
    return PyStr("");
  }
  PyArray<PyChar> codes;
  codes.reshape(n, 0);
  for (int i = 0; i < n; i++)
  {
    codes.__setitem__(i, (PyChar)(unsigned char)stack[i]);
  }
  return PyStr(codes);
}

PyStr PyTextIOWrapper::readLine(PyInt size)
{
  if ((!_fp) || (_closed))
  {
    return PyStr("");
  }
  char stack[4096];
  int cap = (int)sizeof(stack);
  if ((size > 0) && (size < cap))
  {
    cap = size;
  }
  if (fgets(stack, cap, _io_fp(_fp)) == nullptr)
  {
    return PyStr("");
  }
  int n = (int)strlen(stack);
  PyArray<PyChar> codes;
  codes.reshape(n, 0);
  for (int i = 0; i < n; i++)
  {
    codes.__setitem__(i, (PyChar)(unsigned char)stack[i]);
  }
  return PyStr(codes);
}

PyInt PyTextIOWrapper::write(PyStr data)
{
  if ((!_fp) || (_closed))
  {
    return -1;
  }
  int n = data.__len__();
  if (n <= 0)
  {
    return 0;
  }
  char stack[4096];
  int at = 0;
  for (int i = 0; i < n; i++)
  {
    if (at >= (int)sizeof(stack))
    {
      if (fwrite(stack, 1, (size_t)at, _io_fp(_fp)) != (size_t)at)
      {
        return -1;
      }
      at = 0;
    }
    stack[at] = (char)data.__getitem__(i);
    at = (at + 1);
  }
  if ((at > 0) && (fwrite(stack, 1, (size_t)at, _io_fp(_fp)) != (size_t)at))
  {
    return -1;
  }
  return n;
}

PyInt PyTextIOWrapper::write(PyArray<PyChar>& src, PyInt end)
{
  if ((!_fp) || (_closed))
  {
    return -1;
  }
  if (end <= 0)
  {
    return 0;
  }
  char stack[4096];
  int at = 0;
  for (int i = 0; i < end; i++)
  {
    if (at >= (int)sizeof(stack))
    {
      if (fwrite(stack, 1, (size_t)at, _io_fp(_fp)) != (size_t)at)
      {
        return -1;
      }
      at = 0;
    }
    stack[at] = (char)src.__getitem__(i);
    at = (at + 1);
  }
  if ((at > 0) && (fwrite(stack, 1, (size_t)at, _io_fp(_fp)) != (size_t)at))
  {
    return -1;
  }
  return end;
}

PyList<PyStr> PyTextIOWrapper::readLines(PyInt hint)
{
  PyList<PyStr> lines;
  while (true)
  {
    PyStr line = readLine(-1);
    if (line.__len__() == 0)
    {
      break;
    }
    lines.append(line);
    if (hint >= 0)
    {
      hint = (hint - line.__len__());
      if (hint <= 0)
      {
        break;
      }
    }
  }
  return lines;
}

void PyTextIOWrapper::writeLines(const PyList<PyStr>& lines)
{
  int n = lines.__len__();
  for (int i = 0; i < n; i++)
  {
    write(lines.__getitem__(i));
  }
}

PyTextIOWrapper& PyTextIOWrapper::__iter__()
{
  return *this;
}

PyIterResult<PyStr, PyStr> PyTextIOWrapper::__next__()
{
  PyStr line = readLine(-1);
  if (line.__len__() == 0)
  {
    return (PyIterResult<PyStr, PyStr>::Return)(PyStr(""));
  }
  return (PyIterResult<PyStr, PyStr>::Yield)(line);
}

PyTextIOWrapper& PyTextIOWrapper::__enter__()
{
  return *this;
}

void PyTextIOWrapper::__exit__()
{
  if (this->_fp)
  {
    fflush(_io_fp(this->_fp));
  }
  this->close();
}

PY2CPP_BEGIN_SCOPE
PyTextIOWrapper py_open(
  const PyStr& path,
  const PyStr& mode,
  const PyStr& encoding
)
{
  (void)encoding;
  return PyTextIOWrapper(path, mode);
}

PyTextIOWrapper py_wrapFp(PyUPtr fp, PyBool owns)
{
  return PyTextIOWrapper(fp, owns);
}

PyTextIOWrapper py_wrapStd(PyInt fd)
{
  FILE* f = nullptr;
#if defined(_MSC_VER)
  if (fd == 0)
  {
    f = __acrt_iob_func(0);
  }
  else if (fd == 1)
  {
    f = __acrt_iob_func(1);
  }
  else if (fd == 2)
  {
    f = __acrt_iob_func(2);
  }
#else
  if (fd == 0)
  {
    f = ::stdin;
  }
  else if (fd == 1)
  {
    f = ::stdout;
  }
  else if (fd == 2)
  {
    f = ::stderr;
  }
#endif
  return PyTextIOWrapper((PyUPtr)(uintptr_t)f, false);
}
PY2CPP_END_SCOPE
