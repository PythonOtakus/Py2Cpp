PY2CPP_IGNORE
#include "py2cpp/text/str.h"
#include <stdio.h>
class PyStr {
PY2CPP_END

char buf[64];
this->copyToSpan(PySpan<PyByte>((PyByte*)buf, (PyInt)sizeof(buf), 1));
PyInt v = 0;
if (sscanf(buf, "%d", &v) != 1)
{
  throw PY2CPP_TYPE(PyValueError)();
}
return v;

PY2CPP_IGNORE
};
PY2CPP_END
