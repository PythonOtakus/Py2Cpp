PY2CPP_IGNORE
#include <type_traits>
#include "py2cpp/py_types.h"
PY2CPP_END

template<typename U, bool IsClass = std::is_class<U>::value>
struct _Compare_ops_no_pybool_only {
  static constexpr bool ok = true;
};
template<typename U>
struct _Compare_ops_no_pybool_only<U, true> {
  static constexpr bool ok =
    !std::is_convertible<const U&, PyBool>::value ||
    std::is_same<decltype(std::declval<U&>().__eq__(std::declval<const U&>())), PyBool>::value;
};
