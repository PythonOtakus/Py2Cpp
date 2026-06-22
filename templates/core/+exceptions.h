PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
#include "py2cpp/text/str.h"

namespace py2cpp
{
namespace core
{
namespace exceptions
{

class Exception
{
PY2CPP_END

PY2CPP_INJECT_CLASS(Exception)
  const Exception* __cause__;

  explicit Exception() : __cause__(nullptr) {}
  explicit Exception(const PY2CPP_TYPE(PyStr)& /*msg*/) : __cause__(nullptr) {}
  Exception(const Exception& o) : __cause__(o.__cause__) {}
  PY2CPP_INCLUDE("~exception_convert_ctor_decls.inl")
PY2CPP_END

PY2CPP_IGNORE
};

class BaseExceptionGroup : public Exception
{
PY2CPP_END

PY2CPP_INJECT_CLASS(BaseExceptionGroup)
  explicit BaseExceptionGroup() = default;
PY2CPP_END

PY2CPP_IGNORE
};

} // namespace exceptions
} // namespace core
} // namespace py2cpp
PY2CPP_END
