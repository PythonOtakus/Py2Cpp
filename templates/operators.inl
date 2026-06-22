
#include <stdio.h>
#include <math.h>

PY2CPP_IGNORE
#include "py2cpp/operators.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/tuple.h"
PY2CPP_END

inline PyInt _py_int_mod(PyInt a, PyInt b)
{
  PyInt r = a % b;
  if (r != 0 && ((r < 0) != (b < 0)))
  {
    r += b;
  }
  return r;
}

inline PyInt _py_int_mod_mul(PyInt a, PyInt b, PyInt mod)
{
  PyInt64 p = (PyInt64)a * (PyInt64)b;
  PyInt64 m = (PyInt64)mod;
  PyInt64 r = p % m;
  if (r != 0 && ((r < 0) != (m < 0)))
  {
    r += m;
  }
  return (PyInt)r;
}

inline PyInt _py_int_floordiv(PyInt a, PyInt b)
{
  PyInt q = a / b;
  PyInt r = a % b;
  if (r != 0 && ((r < 0) != (b < 0)))
  {
    q -= 1;
  }
  return q;
}

inline PyInt __mod__(PyInt a, PyInt b)
{
  return _py_int_mod(a, b);
}

inline PyFloat __mod__(PyFloat a, PyFloat b)
{
  double q = floor((double)a / (double)b);
  return (PyFloat)((double)a - q * (double)b);
}

inline PyFloat __mod__(PyInt a, PyFloat b)
{
  return __mod__((PyFloat)a, b);
}

inline PyFloat __mod__(PyFloat a, PyInt b)
{
  return __mod__(a, (PyFloat)b);
}

inline PyFloat __truediv__(PyInt a, PyInt b)
{
  return (PyFloat)a / (PyFloat)b;
}

inline PyFloat __truediv__(PyFloat a, PyFloat b)
{
  return a / b;
}

inline PyFloat __truediv__(PyInt a, PyFloat b)
{
  return (PyFloat)a / b;
}

inline PyFloat __truediv__(PyFloat a, PyInt b)
{
  return a / b;
}

inline PyInt __floordiv__(PyInt a, PyInt b)
{
  return _py_int_floordiv(a, b);
}

inline PyFloat __floordiv__(PyFloat a, PyFloat b)
{
  return (PyFloat)floor((double)a / (double)b);
}

inline PyFloat __floordiv__(PyInt a, PyFloat b)
{
  return __floordiv__((PyFloat)a, b);
}

inline PyFloat __floordiv__(PyFloat a, PyInt b)
{
  return __floordiv__(a, (PyFloat)b);
}

inline PyTuple<PyInt, PyInt> divmod(PyInt a, PyInt b)
{
  return PyTuple<PyInt, PyInt>(::__floordiv__(a, b), ::__mod__(a, b));
}

inline PyTuple<PyFloat, PyFloat> divmod(PyFloat a, PyFloat b)
{
  return PyTuple<PyFloat, PyFloat>(::__floordiv__(a, b), ::__mod__(a, b));
}

inline PyTuple<PyFloat, PyFloat> divmod(PyInt a, PyFloat b)
{
  return PyTuple<PyFloat, PyFloat>(::__floordiv__(a, b), ::__mod__(a, b));
}

inline PyTuple<PyFloat, PyFloat> divmod(PyFloat a, PyInt b)
{
  return PyTuple<PyFloat, PyFloat>(::__floordiv__(a, b), ::__mod__(a, b));
}

template<typename... Args>
inline PY2CPP_TYPE(PyStr) __mod__(const PY2CPP_TYPE(PyStr)& fmt, const PyTuple<Args...>& rhs)
{
  return fmt.__mod__(rhs);
}

inline PyInt __modmul__(PyInt a, PyInt b, PyInt mod)
{
  return _py_int_mod_mul(a, b, mod);
}

inline PyInt modmul(PyInt a, PyInt b, PyInt mod)
{
  return __modmul__(a, b, mod);
}

inline PyInt _py_int_mod_inverse(PyInt a, PyInt mod)
{
  a = __mod__(a, mod);
  if (mod < 0)
  {
    mod = -mod;
  }
  PyInt64 t = 0;
  PyInt64 newt = 1;
  PyInt64 r = mod;
  PyInt64 newr = a;
  while (newr != 0)
  {
    PyInt64 q = r / newr;
    PyInt64 tr = newt;
    newt = t - q * newt;
    t = tr;
    PyInt64 rr = newr;
    newr = r - q * newr;
    r = rr;
  }
  if (r != 1)
  {
    throw PY2CPP_TYPE(ValueError)();
  }
  PyInt64 out = t % mod;
  if (out < 0)
  {
    out += mod;
  }
  return (PyInt)out;
}

inline PyInt _py_int_pow_mod(PyInt base, PyInt exp, PyInt mod)
{
  if (mod == 0)
  {
    throw PY2CPP_TYPE(ValueError)();
  }
  if (mod == 1)
  {
    return 0;
  }
  if (exp == 0 && base == 0)
  {
    throw PY2CPP_TYPE(ValueError)();
  }
  base = __mod__(base, mod);
  if (exp < 0)
  {
    base = _py_int_mod_inverse(base, mod);
    exp = -exp;
  }
  PyInt result = 1;
  PyInt b = base;
  PyInt e = exp;
  while (e > 0)
  {
    if (e & 1)
    {
      result = _py_int_mod_mul(result, b, mod);
    }
    b = _py_int_mod_mul(b, b, mod);
    e >>= 1;
  }
  return result;
}

inline PyInt _py_pow_int(PyInt base, PyInt exp)
{
  if (exp < 0)
  {
    return 0;
  }
  PyInt out = 1;
  for (PyInt i = 0; i < exp; ++i)
  {
    out *= base;
  }
  return out;
}

inline PyFloat _py_pow_float(PyFloat base, PyFloat exp)
{
  return (PyFloat)::pow((double)base, (double)exp);
}

namespace py2cpp {

namespace detail {

template<typename T, typename U>
auto py_cmp_dispatch(T const& a, U const& b, int)
  -> decltype(a.__cmp__(b), PyInt())
{
  return a.__cmp__(b);
}

template<typename T, typename U>
PyInt py_cmp_dispatch(T const& a, U const& b, long)
{
  if (a < b)
  {
    return -1;
  }
  if (a > b)
  {
    return 1;
  }
  return 0;
}

} // namespace detail

inline PyInt py_cmp(PyInt a, PyInt b)
{
  if (a < b)
  {
    return -1;
  }
  if (a > b)
  {
    return 1;
  }
  return 0;
}

inline PyInt py_cmp(PyFloat a, PyFloat b)
{
  if (a < b)
  {
    return -1;
  }
  if (a > b)
  {
    return 1;
  }
  return 0;
}

inline PyInt py_cmp(const PY2CPP_TYPE(PyStr)& a, const PY2CPP_TYPE(PyStr)& b)
{
  if (a < b)
  {
    return -1;
  }
  if (a > b)
  {
    return 1;
  }
  return 0;
}

template<typename T0, typename T1>
PyInt py_cmp(T0 a, T1 b)
{
  return detail::py_cmp_dispatch(a, b, 0);
}

} // namespace py2cpp

inline PyInt pow(PyInt base, PyInt exp)
{
  return _py_pow_int(base, exp);
}

inline PyInt pow(PyInt base, PyInt exp, PyInt mod)
{
  return _py_int_pow_mod(base, exp, mod);
}

inline PyFloat pow(PyFloat base, PyFloat exp)
{
  return _py_pow_float(base, exp);
}

inline PY2CPP_TYPE(PyStr) repr(PyInt v)
{
  char buf[64];
  snprintf(buf, sizeof(buf), "%d", v);
  return PY2CPP_TYPE(PyStr)(buf);
}

inline PY2CPP_TYPE(PyStr) repr(PyFloat v)
{
  char buf[64];
  snprintf(buf, sizeof(buf), "%g", v);
  return PY2CPP_TYPE(PyStr)(buf);
}

inline PY2CPP_TYPE(PyStr) repr(PyBool v)
{
  return PY2CPP_TYPE(PyStr)(v ? "True" : "False");
}

inline PY2CPP_TYPE(PyStr) repr(PyChar v)
{
  return (PY2CPP_TYPE(PyStr)("'")).__add__(PY2CPP_TYPE(PyStr)::repr_char(v)).__add__(PY2CPP_TYPE(PyStr)("'"));
}

static bool str_format_spec_empty(c_str spec)
{
  return (!spec || !spec[0]);
}

static void str_format_printf_spec(c_str spec, char* buf, size_t cap)
{
  if (!buf || cap == 0)
  {
    return;
  }
  buf[0] = '\0';
  if (str_format_spec_empty(spec))
  {
    return;
  }
  if (spec[0] == '%')
  {
    snprintf(buf, cap, "%s", spec);
  }
  else
  {
    snprintf(buf, cap, "%%%s", spec);
  }
}

inline PY2CPP_TYPE(PyStr) format(PyInt v, c_str format_spec)
{
  if (str_format_spec_empty(format_spec))
  {
    return PY2CPP_TYPE(PyStr)(v);
  }
  char fmt[64];
  str_format_printf_spec(format_spec, fmt, sizeof(fmt));
  return PY2CPP_TYPE(PyStr)::percent_format(fmt, v);
}

inline PY2CPP_TYPE(PyStr) format(PyFloat v, c_str format_spec)
{
  if (str_format_spec_empty(format_spec))
  {
    return PY2CPP_TYPE(PyStr)(v);
  }
  char fmt[64];
  str_format_printf_spec(format_spec, fmt, sizeof(fmt));
  return PY2CPP_TYPE(PyStr)::percent_format(fmt, v);
}

inline PY2CPP_TYPE(PyStr) format(PyBool v, c_str format_spec)
{
  if (str_format_spec_empty(format_spec))
  {
    return PY2CPP_TYPE(PyStr)(v ? "True" : "False");
  }
  char fmt[64];
  str_format_printf_spec(format_spec, fmt, sizeof(fmt));
  return PY2CPP_TYPE(PyStr)::percent_format(fmt, v ? "True" : "False");
}

inline PY2CPP_TYPE(PyStr) format(PyChar v, c_str format_spec)
{
  if (str_format_spec_empty(format_spec))
  {
    return PY2CPP_TYPE(PyStr)(v);
  }
  char fmt[64];
  str_format_printf_spec(format_spec, fmt, sizeof(fmt));
  return PY2CPP_TYPE(PyStr)::percent_format(fmt, (int)(int32_t)v);
}

inline PY2CPP_TYPE(PyStr) format(const PY2CPP_TYPE(PyStr)& v, c_str format_spec)
{
  (void)format_spec;
  return v;
}

inline PyInt64 _py_i64_mod(PyInt64 a, PyInt64 b) {
  PyInt64 r = a % b;
  if (r != 0 && ((r < 0) != (b < 0))) {
    r += b;
  }
  return r;
}

inline PyInt64 _py_i64_floordiv(PyInt64 a, PyInt64 b) {
  PyInt64 q = a / b;
  PyInt64 r = a % b;
  if (r != 0 && ((r < 0) != (b < 0))) {
    q -= 1;
  }
  return q;
}

inline PyInt64 __modmul__(PyInt64 a, PyInt64 b, PyInt64 mod) {
  a = _py_i64_mod(a, mod);
  b = _py_i64_mod(b, mod);
  if (mod > 0 && mod <= (PyInt64)0xFFFFFFFFLL) {
    return _py_i64_mod(a * b, mod);
  }
  PyInt64 res = 0;
  while (b > 0) {
    if (b & 1) {
      res = _py_i64_mod(res + a, mod);
    }
    a = _py_i64_mod(a + a, mod);
    b >>= 1;
  }
  return res;
}

inline PyInt64 modmul(PyInt64 a, PyInt64 b, PyInt64 mod) {
  return __modmul__(a, b, mod);
}

inline PyInt64 __mod__(PyInt64 a, PyInt64 b) {
  return _py_i64_mod(a, b);
}

inline PyInt64 __mod__(PyInt a, PyInt64 b) {
  return _py_i64_mod((PyInt64)a, b);
}

inline PyInt64 __mod__(PyInt64 a, PyInt b) {
  return _py_i64_mod(a, (PyInt64)b);
}

inline PyFloat64 __mod__(PyFloat64 a, PyFloat64 b) {
  double q = floor(a / b);
  return (PyFloat64)(a - q * b);
}

inline PyFloat64 __truediv__(PyInt64 a, PyInt64 b) {
  return (PyFloat64)a / (PyFloat64)b;
}

inline PyFloat64 __truediv__(PyFloat64 a, PyFloat64 b) {
  return a / b;
}

inline PyFloat64 __truediv__(PyInt64 a, PyFloat64 b) {
  return (PyFloat64)a / b;
}

inline PyFloat64 __truediv__(PyFloat64 a, PyInt64 b) {
  return a / (PyFloat64)b;
}

inline PyFloat64 __truediv__(PyInt a, PyInt64 b) {
  return (PyFloat64)a / (PyFloat64)b;
}

inline PyFloat64 __truediv__(PyInt64 a, PyInt b) {
  return (PyFloat64)a / (PyFloat64)b;
}

inline PyFloat64 __truediv__(PyFloat a, PyFloat64 b) {
  return (PyFloat64)a / b;
}

inline PyFloat64 __truediv__(PyFloat64 a, PyFloat b) {
  return a / (PyFloat64)b;
}

inline PyInt64 __floordiv__(PyInt64 a, PyInt64 b) {
  return _py_i64_floordiv(a, b);
}

inline PyInt64 __floordiv__(PyInt a, PyInt64 b) {
  return _py_i64_floordiv((PyInt64)a, b);
}

inline PyInt64 __floordiv__(PyInt64 a, PyInt b) {
  return _py_i64_floordiv(a, (PyInt64)b);
}

inline PyFloat64 __floordiv__(PyFloat64 a, PyFloat64 b) {
  return (PyFloat64)floor(a / b);
}

inline PyFloat64 __floordiv__(PyFloat a, PyFloat64 b) {
  return (PyFloat64)floor((PyFloat64)a / b);
}

inline PyFloat64 __floordiv__(PyFloat64 a, PyFloat b) {
  return (PyFloat64)floor(a / (PyFloat64)b);
}

inline PyInt64 __pow__(PyInt64 base, PyInt64 exp) {
  if (exp < 0) {
    return 0;
  }
  PyInt64 out = 1;
  for (PyInt64 i = 0; i < exp; ++i) {
    out *= base;
  }
  return out;
}

inline PyFloat64 __pow__(PyFloat64 base, PyFloat64 exp) {
  return (PyFloat64)pow(base, exp);
}

inline PyFloat64 __pow__(PyInt64 base, PyFloat64 exp) {
  return (PyFloat64)pow((double)base, exp);
}

inline PyFloat64 __pow__(PyFloat64 base, PyInt64 exp) {
  return (PyFloat64)pow(base, (double)exp);
}

inline PyInt64 hash(PyInt64 v) {
  return v;
}

inline PY2CPP_TYPE(PyStr) repr(PyInt64 v) {
  char buf[32];
  snprintf(buf, sizeof(buf), "%lld", (long long)v);
  return PY2CPP_TYPE(PyStr)(buf);
}

inline PY2CPP_TYPE(PyStr) repr(PyFloat64 v) {
  char buf[64];
  snprintf(buf, sizeof(buf), "%g", v);
  return PY2CPP_TYPE(PyStr)(buf);
}

inline PY2CPP_TYPE(PyStr) format(PyInt64 v, c_str format_spec) {
  if (str_format_spec_empty(format_spec)) {
    return repr(v);
  }
  char fmt[64];
  str_format_printf_spec(format_spec, fmt, sizeof(fmt));
  return PY2CPP_TYPE(PyStr)::percent_format(fmt, (long long)v);
}

inline PY2CPP_TYPE(PyStr) format(PyFloat64 v, c_str format_spec) {
  if (str_format_spec_empty(format_spec)) {
    return repr(v);
  }
  char fmt[64];
  str_format_printf_spec(format_spec, fmt, sizeof(fmt));
  return PY2CPP_TYPE(PyStr)::percent_format(fmt, v);
}

inline PY2CPP_TYPE(PyStr) chr(PyInt i) {
  return PY2CPP_TYPE(PyStr)((PyChar)i);
}
