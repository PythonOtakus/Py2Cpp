PY2CPP_IGNORE
#include <type_traits>
#include "paw/py_types.h"

namespace paw { namespace text { namespace str { class PyStr; } } }
template<typename... Args>
class PyTuple;
template<typename... Args>
PY2CPP_TYPE(PyStr) __mod__(const PY2CPP_TYPE(PyStr)& fmt, const PyTuple<Args...>& rhs);

inline PyInt hash(PyInt v);
template<typename T>
auto hash(T& obj) -> decltype(obj.__hash__());
template<typename T>
auto hash(const T& obj) -> decltype(const_cast<T&>(obj).__hash__());
template<typename T>
auto hash(T* obj) -> decltype(obj->__hash__());
PY2CPP_END
