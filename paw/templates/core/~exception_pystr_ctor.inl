PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
#include "py2cpp/text/str.h"
#define ctx_Cls PyValueError
#define ctx_Base PyException
PY2CPP_END

explicit PY2CPP_ECHO(ctx_Cls)() = default;
explicit PY2CPP_ECHO(ctx_Cls)(const PY2CPP_TYPE(PyStr)& msg) : PY2CPP_ECHO(ctx_Base)(msg) {}
