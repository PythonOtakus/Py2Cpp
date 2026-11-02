PY2CPP_IGNORE
#include "py2cpp/numeric/ratio.h"
#include "py2cpp/py_types.h"
PY2CPP_END

#include <cstdint>

PY2CPP_BEGIN_SCOPE

PyUInt64 numeric_ratio_float64Bits(PyFloat64 x)
{
  union
  {
    double d;
    uint64_t u;
  } pun;
  pun.d = (double)x;
  return (PyUInt64)pun.u;
}

PY2CPP_END_SCOPE
