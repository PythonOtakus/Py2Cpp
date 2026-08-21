PY2CPP_IGNORE
#include "py2cpp/text/str.h"
#include "py2cpp/util/tuple.h"
PY2CPP_END

#include <cstdarg>
#include "ffi/crt/stdio.h"

PyStr PyStr::_str_unescape_braces(PyUtf8Ptr fmt)
{
  PyStr out("");
  if (!fmt)
  {
    return out;
  }
  const char* p = fmt;
  while (*p)
  {
    if (p[0] == '{' && p[1] == '{')
    {
      out = out.__add__(PyStr("{"));
      p += 2;
    }
    else if (p[0] == '}' && p[1] == '}')
    {
      out = out.__add__(PyStr("}"));
      p += 2;
    }
    else
    {
      char ch[2] = { p[0], '\0' };
      out = out.__add__(PyStr(ch));
      p += 1;
    }
  }
  return out;
}

PyStr PyStr::_str_format_substitute(PyUtf8Ptr fmt, const PyStr* parts, int n)
{
  PyStr out("");
  if (!fmt)
  {
    return out;
  }
  const char* p = fmt;
  int idx = 0;
  while (*p)
  {
    if (p[0] != '{')
    {
      if (p[0] == '}')
      {
        char ch[2] = { '}', '\0' };
        out = out.__add__(PyStr(ch));
        p += 1;
      }
      else
      {
        char ch[2] = { p[0], '\0' };
        out = out.__add__(PyStr(ch));
        p += 1;
      }
      continue;
    }
    if (p[1] == '{')
    {
      out = out.__add__(PyStr("{"));
      p += 2;
      continue;
    }
    const char* end = p + 1;
    while (*end && *end != '}')
    {
      end++;
    }
    if (*end != '}')
    {
      break;
    }
    if (idx < n)
    {
      out = out.__add__(parts[idx]);
      idx++;
    }
    p = end + 1;
  }
  return out;
}

PyStr::PrintfArg::PrintfArg(const PyStr& s)
{
  s.copyToSpanUtf8(PySpan<PyByte>((PyByte*)data, (PyInt)sizeof(data), 1));
}

PyStr PyStr::percent_format(PyUtf8Ptr fmt, ...)
{
  char buf[512];
  va_list ap;
  va_start(ap, fmt);
  ::ffi::crt::stdio::pyiVsnprintf(buf, sizeof(buf), fmt, reinterpret_cast<PyUtf8Ptr>(ap));
  va_end(ap);
  return PyStr(buf);
}


PyStr::PyStr(PyBool value)
{
  PyStr tmp(value ? (PyUtf8Ptr)"True" : (PyUtf8Ptr)"False");
  (this->_data).__move__(tmp._data);
  this->_hash = tmp._hash;
  this->_hashOk = tmp._hashOk;
}

template<typename T>
struct _PyPercentArg
{
  T value;
  explicit _PyPercentArg(const T& v) : value(v)
  {
  }
  T pass() const
  {
    return value;
  }
};

template<>
struct _PyPercentArg<PyStr>
{
  PyStr::PrintfArg buf;
  explicit _PyPercentArg(const PyStr& s) : buf(s)
  {
  }
  const char* pass() const
  {
    return buf.data;
  }
};

template<>
struct _PyPercentArg<PyBool>
{
  PyBool value;
  explicit _PyPercentArg(PyBool v) : value(v)
  {
  }
  const char* pass() const
  {
    return value ? "True" : "False";
  }
};

template<>
struct _PyPercentArg<PyChar>
{
  PyStr::PrintfArg buf;
  explicit _PyPercentArg(PyChar v) : buf(PyStr(v))
  {
  }
  const char* pass() const
  {
    return buf.data;
  }
};

template<typename T>
auto _py_percent_arg(const T& x) -> decltype(_PyPercentArg<T>(x).pass())
{
  return _PyPercentArg<T>(x).pass();
}

template<typename... Args, std::size_t... Is>
PyStr _str_mod_tuple_impl(const PyStr& fmt, const PyTuple<Args...>& t, std::index_sequence<Is...>)
{
  return PyStr::percent_format(
      PyStr::PrintfArg(fmt).data, _py_percent_arg(t.template get<Is>())...);
}

template<typename... Args>
PyStr PyStr::__mod__(const PyTuple<Args...>& other) const
{
  return _str_mod_tuple_impl(*this, other, std::index_sequence_for<Args...>{});
}

PyStr::PyStr(PY2CPP_TYPE(PyArray)<PyChar, 0>&& data)
{
  this->_hash = 0;
  this->_hashOk = false;
  PyInt n = data.__len__();
  if (n > 0)
  {
    this->_data.reshape(n, 0);
    for (PyInt i = 0; i < n; i += 1)
    {
      this->_data.__setitem__(i, data.__getitem__(i));
    }
  }
  else
  {
    this->_data.reshape(0, 0);
  }
}
