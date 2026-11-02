PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
#include "py2cpp/text/str.h"

namespace py2cpp
{
namespace core
{
namespace exceptions
{

class PyException
{
PY2CPP_END

PY2CPP_INJECT_CLASS(PyException)
  const PyException* __cause__;

  explicit PyException() : __cause__(nullptr) {}
  explicit PyException(const PY2CPP_TYPE(PyStr)& /*msg*/) : __cause__(nullptr) {}
  PyException(const PyException& o) : __cause__(o.__cause__) {}
  PY2CPP_INCLUDE("~exception_convert_ctor_decls.inl")
PY2CPP_END

PY2CPP_IGNORE
};

class PyBaseExceptionGroup : public PyException
{
PY2CPP_END

PY2CPP_INJECT_CLASS(PyBaseExceptionGroup)
  explicit PyBaseExceptionGroup() = default;
PY2CPP_END

PY2CPP_IGNORE
};

} // namespace exceptions
} // namespace core
} // namespace py2cpp
PY2CPP_END
