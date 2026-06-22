PY2CPP_IGNORE
#include "py2cpp/text/bytes.h"
PY2CPP_END

PY2CPP_BEGIN_SCOPE

inline PyBytes bytes_from_literal(const unsigned char* data, PyInt n) {
  if (n <= 0) {
    PyArray<PyByte> empty(0);
    return PyBytes(empty);
  }
  PyArray<PyByte> buf(n);
  for (PyInt i = 0; i < n; ++i) {
    buf.__setitem__(i, PyByte(data[i]));
  }
  return PyBytes(buf);
}

PY2CPP_END_SCOPE
