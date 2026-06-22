
PY2CPP_IGNORE
#include "py2cpp/py_types.h"
#include <type_traits>
#include <utility>
#include "py2cpp/util/tuple.h"
#include "py2cpp/text/str.h"
PY2CPP_END

#include "py_types.h"
#include <type_traits>
#include <utility>

#include "py2cpp/util/tuple.h"
#include "py2cpp/text/str.h"

/* --- ``%`` / ``/`` / ``//``（标量按 Python 3 语义；``str`` 见 ``__mod__(fmt, tuple)``）--- */
PyInt __mod__(PyInt a, PyInt b);
PyFloat __mod__(PyFloat a, PyFloat b);
PyFloat __mod__(PyInt a, PyFloat b);
PyFloat __mod__(PyFloat a, PyInt b);

PyFloat __truediv__(PyInt a, PyInt b);
PyFloat __truediv__(PyFloat a, PyFloat b);
PyFloat __truediv__(PyInt a, PyFloat b);
PyFloat __truediv__(PyFloat a, PyInt b);

PyInt __floordiv__(PyInt a, PyInt b);
PyFloat __floordiv__(PyFloat a, PyFloat b);
PyFloat __floordiv__(PyInt a, PyFloat b);
PyFloat __floordiv__(PyFloat a, PyInt b);

PyTuple<PyInt, PyInt> divmod(PyInt a, PyInt b);
PyTuple<PyFloat, PyFloat> divmod(PyFloat a, PyFloat b);
PyTuple<PyFloat, PyFloat> divmod(PyInt a, PyFloat b);
PyTuple<PyFloat, PyFloat> divmod(PyFloat a, PyInt b);

template<typename... Args>
PY2CPP_TYPE(PyStr) __mod__(const PY2CPP_TYPE(PyStr)& fmt, const PyTuple<Args...>& rhs);

template<typename... Ts>
struct _py2cpp_make_void
{
  using type = void;
};
template<typename... Ts>
using _py2cpp_void_t = typename _py2cpp_make_void<Ts...>::type;

template<typename T, typename U, typename = void>
struct _py2cpp_binop_fwd
{
  static constexpr bool ok = false;
};
template<typename T, typename U>
struct _py2cpp_binop_fwd<T, U, _py2cpp_void_t<decltype(std::declval<T&>().__truediv__(std::declval<U>()))>>
{
  static constexpr bool ok = true;
  using type = decltype(std::declval<T&>().__truediv__(std::declval<U>()));
  static type call(T&& a, U&& b)
  {
    return std::forward<T>(a).__truediv__(std::forward<U>(b));
  }
};
template<typename T, typename U, typename = void>
struct _py2cpp_binop_rev
{
  static constexpr bool ok = false;
};
template<typename T, typename U>
struct _py2cpp_binop_rev<T, U, _py2cpp_void_t<decltype(std::declval<U&>().__rtruediv__(std::declval<T>()))>>
{
  static constexpr bool ok = true;
  using type = decltype(std::declval<U&>().__rtruediv__(std::declval<T>()));
  static type call(T&& a, U&& b)
  {
    return std::forward<U>(b).__rtruediv__(std::forward<T>(a));
  }
};

template<typename T, typename U,
  typename std::enable_if<_py2cpp_binop_fwd<T, U>::ok, int>::type = 0,
  typename R = typename _py2cpp_binop_fwd<T, U>::type>
inline R __truediv__(T&& a, U&& b)
{
  return _py2cpp_binop_fwd<T, U>::call(std::forward<T>(a), std::forward<U>(b));
}

template<typename T, typename U,
  typename std::enable_if<!_py2cpp_binop_fwd<T, U>::ok && _py2cpp_binop_rev<T, U>::ok, int>::type = 0,
  typename R = typename _py2cpp_binop_rev<T, U>::type>
inline R __truediv__(T&& a, U&& b)
{
  return _py2cpp_binop_rev<T, U>::call(std::forward<T>(a), std::forward<U>(b));
}

template<typename T, typename U, typename = void>
struct _py2cpp_binop_floordiv_fwd
{
  static constexpr bool ok = false;
};
template<typename T, typename U>
struct _py2cpp_binop_floordiv_fwd<T, U, _py2cpp_void_t<decltype(std::declval<T&>().__floordiv__(std::declval<U>()))>>
{
  static constexpr bool ok = true;
  using type = decltype(std::declval<T&>().__floordiv__(std::declval<U>()));
  static type call(T&& a, U&& b)
  {
    return std::forward<T>(a).__floordiv__(std::forward<U>(b));
  }
};
template<typename T, typename U, typename = void>
struct _py2cpp_binop_floordiv_rev
{
  static constexpr bool ok = false;
};
template<typename T, typename U>
struct _py2cpp_binop_floordiv_rev<T, U, _py2cpp_void_t<decltype(std::declval<U&>().__rfloordiv__(std::declval<T>()))>>
{
  static constexpr bool ok = true;
  using type = decltype(std::declval<U&>().__rfloordiv__(std::declval<T>()));
  static type call(T&& a, U&& b)
  {
    return std::forward<U>(b).__rfloordiv__(std::forward<T>(a));
  }
};

template<typename T, typename U,
  typename std::enable_if<_py2cpp_binop_floordiv_fwd<T, U>::ok, int>::type = 0,
  typename R = typename _py2cpp_binop_floordiv_fwd<T, U>::type>
inline R __floordiv__(T&& a, U&& b)
{
  return _py2cpp_binop_floordiv_fwd<T, U>::call(std::forward<T>(a), std::forward<U>(b));
}

template<typename T, typename U,
  typename std::enable_if<!_py2cpp_binop_floordiv_fwd<T, U>::ok && _py2cpp_binop_floordiv_rev<T, U>::ok, int>::type = 0,
  typename R = typename _py2cpp_binop_floordiv_rev<T, U>::type>
inline R __floordiv__(T&& a, U&& b)
{
  return _py2cpp_binop_floordiv_rev<T, U>::call(std::forward<T>(a), std::forward<U>(b));
}

template<typename T, typename U, typename = void>
struct _py2cpp_binop_mod_fwd
{
  static constexpr bool ok = false;
};
template<typename T, typename U>
struct _py2cpp_binop_mod_fwd<T, U, _py2cpp_void_t<decltype(std::declval<T&>().__mod__(std::declval<U>()))>>
{
  static constexpr bool ok = true;
  using type = decltype(std::declval<T&>().__mod__(std::declval<U>()));
  static type call(T&& a, U&& b)
  {
    return std::forward<T>(a).__mod__(std::forward<U>(b));
  }
};
template<typename T, typename U, typename = void>
struct _py2cpp_binop_mod_rev
{
  static constexpr bool ok = false;
};
template<typename T, typename U>
struct _py2cpp_binop_mod_rev<T, U, _py2cpp_void_t<decltype(std::declval<U&>().__rmod__(std::declval<T>()))>>
{
  static constexpr bool ok = true;
  using type = decltype(std::declval<U&>().__rmod__(std::declval<T>()));
  static type call(T&& a, U&& b)
  {
    return std::forward<U>(b).__rmod__(std::forward<T>(a));
  }
};

template<typename T, typename U,
  typename std::enable_if<_py2cpp_binop_mod_fwd<T, U>::ok, int>::type = 0,
  typename R = typename _py2cpp_binop_mod_fwd<T, U>::type>
inline R __mod__(T&& a, U&& b)
{
  return _py2cpp_binop_mod_fwd<T, U>::call(std::forward<T>(a), std::forward<U>(b));
}

template<typename T, typename U,
  typename std::enable_if<!_py2cpp_binop_mod_fwd<T, U>::ok && _py2cpp_binop_mod_rev<T, U>::ok, int>::type = 0,
  typename R = typename _py2cpp_binop_mod_rev<T, U>::type>
inline R __mod__(T&& a, U&& b)
{
  return _py2cpp_binop_mod_rev<T, U>::call(std::forward<T>(a), std::forward<U>(b));
}

/* --- 算术 ``pow``（``PyInt``/``PyFloat`` 标量；其它走 ``__pow__`` / ``__rpow__``）--- */
PyInt pow(PyInt base, PyInt exp);
PyInt pow(PyInt base, PyInt exp, PyInt mod);
PyFloat pow(PyFloat base, PyFloat exp);

template<typename T, typename U>
auto pow(T&& base, U&& exp) -> decltype(std::forward<T>(base).__pow__(std::forward<U>(exp)))
{
  return std::forward<T>(base).__pow__(std::forward<U>(exp));
}

template<typename T, typename U>
auto pow(T&& base, U&& exp) -> decltype(std::forward<U>(exp).__rpow__(std::forward<T>(base)))
{
  return std::forward<U>(exp).__rpow__(std::forward<T>(base));
}

template<typename T, typename U, typename M>
auto pow(T&& base, U&& exp, M&& mod) -> decltype(std::forward<T>(base).__pow__(std::forward<U>(exp), std::forward<M>(mod)))
{
  return std::forward<T>(base).__pow__(std::forward<U>(exp), std::forward<M>(mod));
}

/* --- 模乘 ``modmul(a,b,mod)`` → ``__modmul__(a,b,mod)``（``PyInt`` 等标量见 ``.inl``）--- */
PyInt modmul(PyInt a, PyInt b, PyInt mod);

template<typename T, typename U, typename M>
auto modmul(T&& a, U&& b, M&& mod) -> decltype(std::forward<T>(a).__modmul__(std::forward<U>(b), std::forward<M>(mod)))
{
  return std::forward<T>(a).__modmul__(std::forward<U>(b), std::forward<M>(mod));
}

/* --- len / iter / next / aiter / anext / reversed --- */
template<typename T>
auto len(T& obj) -> decltype(obj.__len__())
{
  return obj.__len__();
}

template<typename T>
auto len(T* obj) -> decltype(obj->__len__())
{
  return obj->__len__();
}

template<typename T>
auto iter(T& obj) -> decltype(obj.__iter__())
{
  return obj.__iter__();
}

template<typename T>
auto iter(T* obj) -> decltype(obj->__iter__())
{
  return obj->__iter__();
}

template<typename It>
auto next(It& it) -> decltype(it.__next__())
{
  return it.__next__();
}

template<typename It>
auto next(It* it) -> decltype(it->__next__())
{
  return it->__next__();
}

template<typename T>
auto aiter(T& obj) -> decltype(obj.__aiter__())
{
  return obj.__aiter__();
}

template<typename T>
auto aiter(T* obj) -> decltype(obj->__aiter__())
{
  return obj->__aiter__();
}

template<typename It>
auto anext(It& it) -> decltype(it.__anext__())
{
  return it.__anext__();
}

template<typename It>
auto anext(It* it) -> decltype(it->__anext__())
{
  return it->__anext__();
}

template<typename T>
auto reversed(T& obj) -> decltype(obj.__reversed__())
{
  return obj.__reversed__();
}

template<typename T>
auto reversed(T* obj) -> decltype(obj->__reversed__())
{
  return obj->__reversed__();
}

/* hash / 成员检测（``x in container`` → ``__contains__(container, x)``） */
inline PyInt hash(PyChar c)
{
  return (PyInt)(int32_t)c;
}

/* ``PyStr`` 须优先于 ``hash(PyInt)``（``PyStr::operator PyInt()`` 会误走整型解析） */
inline PyInt hash(PY2CPP_TYPE(PyStr)& obj)
{
  return obj.__hash__();
}

inline PyInt hash(const PY2CPP_TYPE(PyStr)& obj)
{
  return const_cast<PY2CPP_TYPE(PyStr)&>(obj).__hash__();
}

inline PyInt hash(PyInt v)
{
  return v;
}

template<typename T>
auto hash(T& obj) -> decltype(obj.__hash__())
{
  return obj.__hash__();
}

template<typename T>
auto hash(const T& obj) -> decltype(const_cast<T&>(obj).__hash__())
{
  return const_cast<T&>(obj).__hash__();
}

template<typename T>
auto hash(T* obj) -> decltype(obj->__hash__())
{
  return obj->__hash__();
}

template<typename C, typename Item>
auto __contains__(C& container, const Item& item) -> decltype(container.__contains__(item))
{
  return container.__contains__(item);
}

template<typename C, typename Item>
auto __contains__(C* container, const Item& item) -> decltype(container->__contains__(item))
{
  return container->__contains__(item);
}

/* repr：标量在 .inl；自定义类型转发成员 __repr__（str 用构造/operator PyStr） */
PY2CPP_TYPE(PyStr) repr(PyInt v);
PY2CPP_TYPE(PyStr) repr(PyFloat v);
PY2CPP_TYPE(PyStr) repr(PyBool v);
PY2CPP_TYPE(PyStr) repr(PyChar v);

template<typename T>
auto repr(const T& obj) -> decltype(static_cast<PY2CPP_TYPE(PyStr)>(obj.__repr__()))
{
  return static_cast<PY2CPP_TYPE(PyStr)>(obj.__repr__());
}

template<typename T>
auto repr(T* obj) -> decltype(static_cast<PY2CPP_TYPE(PyStr)>(obj->__repr__()))
{
  return static_cast<PY2CPP_TYPE(PyStr)>(obj->__repr__());
}

template<typename T>
auto repr(const T* obj) -> decltype(static_cast<PY2CPP_TYPE(PyStr)>(obj->__repr__()))
{
  return static_cast<PY2CPP_TYPE(PyStr)>(obj->__repr__());
}

/* format(value, format_spec) → value.__format__(PyStr(format_spec)) */
PY2CPP_TYPE(PyStr) format(PyInt v, c_str format_spec = "");
PY2CPP_TYPE(PyStr) format(PyFloat v, c_str format_spec = "");
PY2CPP_TYPE(PyStr) format(PyBool v, c_str format_spec = "");
PY2CPP_TYPE(PyStr) format(PyChar v, c_str format_spec = "");
PY2CPP_TYPE(PyStr) format(const PY2CPP_TYPE(PyStr)& v, c_str format_spec = "");

template<typename T>
auto format(const T& obj, c_str format_spec) -> decltype(obj.__format__(PY2CPP_TYPE(PyStr)(format_spec ? format_spec : "")))
{
  return obj.__format__(PY2CPP_TYPE(PyStr)(format_spec ? format_spec : ""));
}

/* --- ``int64`` / ``float64`` 高精度标量 --- */
PyInt64 __mod__(PyInt64 a, PyInt64 b);
PyInt64 __mod__(PyInt a, PyInt64 b);
PyInt64 __mod__(PyInt64 a, PyInt b);

PyFloat64 __truediv__(PyInt64 a, PyInt64 b);
PyFloat64 __truediv__(PyFloat64 a, PyFloat64 b);
PyFloat64 __truediv__(PyInt64 a, PyFloat64 b);
PyFloat64 __truediv__(PyFloat64 a, PyInt64 b);
PyFloat64 __truediv__(PyInt a, PyInt64 b);
PyFloat64 __truediv__(PyInt64 a, PyInt b);
PyFloat64 __truediv__(PyFloat a, PyFloat64 b);
PyFloat64 __truediv__(PyFloat64 a, PyFloat b);

PyInt64 __floordiv__(PyInt64 a, PyInt64 b);
PyInt64 __floordiv__(PyInt a, PyInt64 b);
PyInt64 __floordiv__(PyInt64 a, PyInt b);
PyFloat64 __floordiv__(PyFloat64 a, PyFloat64 b);
PyFloat64 __floordiv__(PyFloat a, PyFloat64 b);
PyFloat64 __floordiv__(PyFloat64 a, PyFloat b);

PyInt64 __pow__(PyInt64 base, PyInt64 exp);
PyInt64 __modmul__(PyInt64 a, PyInt64 b, PyInt64 mod);
PyInt64 modmul(PyInt64 a, PyInt64 b, PyInt64 mod);
PyFloat64 __pow__(PyFloat64 base, PyFloat64 exp);
PyFloat64 __pow__(PyInt64 base, PyFloat64 exp);
PyFloat64 __pow__(PyFloat64 base, PyInt64 exp);

inline PyInt64 hash(PyInt64 v);
PY2CPP_TYPE(PyStr) repr(PyInt64 v);
PY2CPP_TYPE(PyStr) repr(PyFloat64 v);
PY2CPP_TYPE(PyStr) format(PyInt64 v, c_str format_spec = "");
PY2CPP_TYPE(PyStr) format(PyFloat64 v, c_str format_spec = "");

/* ``chr`` / ``ord``（``ord('x')`` 译期折叠为 ``PyChar``；运行时仅 ``chr``） */
PY2CPP_TYPE(PyStr) chr(PyInt i);
