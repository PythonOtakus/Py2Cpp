#include <stdio.h>
#include <type_traits>

inline void _py2cpp_debug_call(const char* site) {
  fprintf(stderr, "[py2cpp] %s\n", site);
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
