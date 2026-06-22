PY2CPP_IGNORE
#include "py2cpp/util/memory.h"
#include "py2cpp/text/str.h"
PY2CPP_END

#include <stdint.h>
#include <string.h>

PY2CPP_BEGIN_SCOPE

void copy_buf(PyChar* dst, PyChar* src, PyInt n) {
  if ((n <= 0) || (dst == nullptr) || (src == nullptr)) {
    return;
  }
  ::memcpy(
      static_cast<void*>(dst),
      static_cast<const void*>(src),
      static_cast<size_t>(n) * sizeof(PyChar));
}

PyUInt64 load_u64_le(PyChar* p, PyInt off) {
  if (p == nullptr) {
    return (PyUInt64)0;
  }
  PyUInt64 v = 0;
  for (PyInt i = 0; i < 8; ++i) {
    v |= ((PyUInt64)(unsigned char)(unsigned)p[off + i].value) << (PyInt)(i * 8);
  }
  return v;
}

PyUInt64 load_u64_le_bytes(PyByte* p, PyInt off) {
  if (p == nullptr) {
    return (PyUInt64)0;
  }
  uint64_t chunk = 0;
  ::memcpy(&chunk, p + off, 8);
  return chunk;
}

PY2CPP_END_SCOPE
