PY2CPP_IGNORE
#include "py2cpp/util/memory.h"
#include "py2cpp/text/str.h"
PY2CPP_END

#include <cstdint>
#include "ffi/crt/string.h"

PY2CPP_BEGIN_SCOPE

void copyBuf(PyChar* dst, PyChar* src, PyInt n) {
  if ((n <= 0) || (dst == nullptr) || (src == nullptr)) {
    return;
  }
  ::memcpy(
      static_cast<void*>(dst),
      static_cast<const void*>(src),
      static_cast<size_t>(n) * sizeof(PyChar));
}

PyUInt64 loadU64Le(PyChar* p, PyInt off) {
  if (p == nullptr) {
    return (PyUInt64)0;
  }
  PyUInt64 v = 0;
  for (PyInt i = 0; i < 8; ++i) {
    v |= ((PyUInt64)(unsigned char)(unsigned)p[off + i].value) << (PyInt)(i * 8);
  }
  return v;
}

PyUInt64 loadU64LeBytes(PyByte* p, PyInt off) {
  if (p == nullptr) {
    return (PyUInt64)0;
  }
  uint64_t chunk = 0;
  ::memcpy(&chunk, p + off, 8);
  return chunk;
}

PyUInt64 loadU64LeAtAddress(PyUPtr addr) {
  return loadU64LeBytes(reinterpret_cast<PyByte*>(addr), 0);
}

PY2CPP_END_SCOPE
