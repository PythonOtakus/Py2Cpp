#include "ffi/crt/stdio.h"
#include "ffi/crt/string.h"
#include "ffi/crt/stdlib.h"
#ifdef _WIN32
#else
#include "ffi/posix/unistd.h"
extern char** environ;
#endif

PY2CPP_IGNORE
#include "py2cpp/system/environ.h"
#include "py2cpp/text/str.h"
#include "py2cpp/core/exceptions.h"
PY2CPP_END

static void _env_throw_oserror()
{
  throw PY2CPP_TYPE(PyOSError)();
}

static PyStr _env_nchars_to_pystr(const char* p, int n)
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
  ::memcpy(tmp, p, (size_t)n);
  tmp[n] = '\0';
  return PyStr(tmp);
}

static PyBool _env_key_has(const PyStr& key)
{
  char kbuf[4096];
  key.copyToSpan(PySpan<PyByte>((PyByte*)kbuf, (PyInt)sizeof(kbuf), 1));
#ifdef _WIN32
  char vbuf[1];
  DWORD n = ::ffi::windows::windows::pyiGetEnvironmentVariableA(kbuf, vbuf, 1);
  if (n == 0)
  {
    DWORD err = ::ffi::windows::windows::pyiGetLastError();
    if (err == ::ffi::windows::windows::PyiErrorEnvvarNotFound)
    {
      return false;
    }
  }
  return true;
#else
  return (getenv(kbuf) != NULL);
#endif
}

static PyStr _env_get_value(const PyStr& key)
{
  char kbuf[4096];
  key.copyToSpan(PySpan<PyByte>((PyByte*)kbuf, (PyInt)sizeof(kbuf), 1));
#ifdef _WIN32
  char vbuf[32767];
  DWORD n = ::ffi::windows::windows::pyiGetEnvironmentVariableA(kbuf, vbuf, (uint)sizeof(vbuf));
  if (n == 0)
  {
    DWORD err = ::ffi::windows::windows::pyiGetLastError();
    if (err == ::ffi::windows::windows::PyiErrorEnvvarNotFound)
    {
      return PyStr("");
    }
  }
  return PyStr(vbuf);
#else
  const char* v = getenv(kbuf);
  if ((!v))
  {
    return PyStr("");
  }
  return PyStr(v);
#endif
}

PyStr PyEnviron::__getitem__(PyStr key) const
{
  if ((!_env_key_has(key)))
  {
    throw PY2CPP_TYPE(PyKeyError)(key);
  }
  return _env_get_value(key);
}

void PyEnviron::__setitem__(PyStr key, PyStr value)
{
  char kbuf[4096];
  char vbuf[32767];
  key.copyToSpan(PySpan<PyByte>((PyByte*)kbuf, (PyInt)sizeof(kbuf), 1));
  value.copyToSpan(PySpan<PyByte>((PyByte*)vbuf, (PyInt)sizeof(vbuf), 1));
#ifdef _WIN32
  if (::ffi::windows::windows::pyiSetEnvironmentVariableA(kbuf, vbuf) == 0)
  {
    _env_throw_oserror();
  }
#else
  if (setenv(kbuf, vbuf, 1) != 0)
  {
    _env_throw_oserror();
  }
#endif
}

void PyEnviron::__delitem__(PyStr key)
{
  if ((!_env_key_has(key)))
  {
    throw PY2CPP_TYPE(PyKeyError)(key);
  }
  char kbuf[4096];
  key.copyToSpan(PySpan<PyByte>((PyByte*)kbuf, (PyInt)sizeof(kbuf), 1));
#ifdef _WIN32
  if (::ffi::windows::windows::pyiSetEnvironmentVariableA(kbuf, NULL) == 0)
  {
    DWORD err = ::ffi::windows::windows::pyiGetLastError();
    if (err != ::ffi::windows::windows::PyiErrorEnvvarNotFound)
    {
      _env_throw_oserror();
    }
  }
#else
  unsetenv(kbuf);
#endif
}

PyBool PyEnviron::__contains__(PyStr key) const
{
  return _env_key_has(key);
}

PyStr PyEnviron::get(PyStr key, PyStr default_value) const
{
  if (_env_key_has(key))
  {
    return _env_get_value(key);
  }
  return default_value;
}

PY2CPP_TYPE(PyList)<PY2CPP_TYPE(PyStr)> PyEnviron::keys() const
{
  PY2CPP_TYPE(PyList)<PY2CPP_TYPE(PyStr)> out;
#ifdef _WIN32
  char* block = const_cast<char*>(::ffi::windows::windows::pyiGetEnvironmentStrings());
  if ((!block))
  {
    return out;
  }
  char* p = block;
  while ((p[0] != '\0'))
  {
    char* eq = strchr(p, '=');
    if (eq && (eq > p))
    {
      out.append(_env_nchars_to_pystr(p, (int)(eq - p)));
    }
    p += (strlen(p) + 1);
  }
  ::ffi::windows::windows::pyiFreeEnvironmentStringsA(block);
#else
  if (environ)
  {
    int idx = 0;
    while (environ[idx])
    {
      char* entry = environ[idx];
      char* eq = strchr(entry, '=');
      if (eq && (eq > entry))
      {
        out.append(_env_nchars_to_pystr(entry, (int)(eq - entry)));
      }
      idx = (idx + 1);
    }
  }
#endif
  return out;
}
