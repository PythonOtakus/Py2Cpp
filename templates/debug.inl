#include "ffi/crt/stdio.h"
#include <type_traits>

inline void _py2cpp_debug_call(const char* site) {
  ::ffi::crt::stdio::PyiIobuf* err = ::ffi::crt::stdio::pyiAcrtIobFunc(2);
  ::ffi::crt::stdio::pyiFputs("[py2cpp] ", err);
  ::ffi::crt::stdio::pyiFputs(site, err);
  ::ffi::crt::stdio::pyiFputs("\n", err);
}

template<typename T>
typename std::enable_if<!std::is_lvalue_reference<T>::value, T>::type
_py2cpp_debug_wrap_val(const char* site, T value) {
  _py2cpp_debug_call(site);
  return value;
}

template<typename T>
T& _py2cpp_debug_wrap(const char* site, T& value) {
  _py2cpp_debug_call(site);
  return value;
}
