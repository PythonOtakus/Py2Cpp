PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
#define var_Name ValueError
class Exception {
PY2CPP_END

PY2CPP_BEGIN( for var_Name in exception_type_names )
explicit Exception(const PY2CPP_ECHO(var_Name)& o);
PY2CPP_END

PY2CPP_IGNORE
};
PY2CPP_END
