PY2CPP_IGNORE
#include "py2cpp/math.h"
#include "py2cpp/py_types.h"
PY2CPP_END

#include <math.h>

PY2CPP_BEGIN_SCOPE

PyFloat64 math_sqrt(PyFloat64 x)
{
  return (PyFloat64)::sqrt((double)x);
}


PyFloat64 math_fabs(PyFloat64 x)
{
  return (PyFloat64)::fabs((double)x);
}


PyFloat64 math_floor(PyFloat64 x)
{
  return (PyFloat64)::floor((double)x);
}


PyFloat64 math_ceil(PyFloat64 x)
{
  return (PyFloat64)::ceil((double)x);
}


PyFloat64 math_trunc(PyFloat64 x)
{
  return (PyFloat64)::trunc((double)x);
}


PyFloat64 math_sin(PyFloat64 x)
{
  return (PyFloat64)::sin((double)x);
}


PyFloat64 math_cos(PyFloat64 x)
{
  return (PyFloat64)::cos((double)x);
}


PyFloat64 math_tan(PyFloat64 x)
{
  return (PyFloat64)::tan((double)x);
}


PyFloat64 math_asin(PyFloat64 x)
{
  return (PyFloat64)::asin((double)x);
}


PyFloat64 math_acos(PyFloat64 x)
{
  return (PyFloat64)::acos((double)x);
}


PyFloat64 math_atan(PyFloat64 x)
{
  return (PyFloat64)::atan((double)x);
}


PyFloat64 math_sinh(PyFloat64 x)
{
  return (PyFloat64)::sinh((double)x);
}


PyFloat64 math_cosh(PyFloat64 x)
{
  return (PyFloat64)::cosh((double)x);
}


PyFloat64 math_tanh(PyFloat64 x)
{
  return (PyFloat64)::tanh((double)x);
}


PyFloat64 math_asinh(PyFloat64 x)
{
  return (PyFloat64)::asinh((double)x);
}


PyFloat64 math_acosh(PyFloat64 x)
{
  return (PyFloat64)::acosh((double)x);
}


PyFloat64 math_atanh(PyFloat64 x)
{
  return (PyFloat64)::atanh((double)x);
}


PyFloat64 math_exp(PyFloat64 x)
{
  return (PyFloat64)::exp((double)x);
}


PyFloat64 math_exp2(PyFloat64 x)
{
  return (PyFloat64)::exp2((double)x);
}


PyFloat64 math_expm1(PyFloat64 x)
{
  return (PyFloat64)::expm1((double)x);
}


PyFloat64 math_log(PyFloat64 x)
{
  return (PyFloat64)::log((double)x);
}


PyFloat64 math_log2(PyFloat64 x)
{
  return (PyFloat64)::log2((double)x);
}


PyFloat64 math_log10(PyFloat64 x)
{
  return (PyFloat64)::log10((double)x);
}


PyFloat64 math_log1p(PyFloat64 x)
{
  return (PyFloat64)::log1p((double)x);
}


PyFloat64 math_erf(PyFloat64 x)
{
  return (PyFloat64)::erf((double)x);
}


PyFloat64 math_erfc(PyFloat64 x)
{
  return (PyFloat64)::erfc((double)x);
}


PyFloat64 math_gamma(PyFloat64 x)
{
  return (PyFloat64)::tgamma((double)x);
}


PyFloat64 math_lgamma(PyFloat64 x)
{
  return (PyFloat64)::lgamma((double)x);
}


PyFloat64 math_cbrt(PyFloat64 x)
{
  return (PyFloat64)::cbrt((double)x);
}


PyFloat64 math_atan2(PyFloat64 x, PyFloat64 y)
{
  return (PyFloat64)::atan2((double)x, (double)y);
}


PyFloat64 math_hypot(PyFloat64 x, PyFloat64 y)
{
  return (PyFloat64)::hypot((double)x, (double)y);
}


PyFloat64 math_pow(PyFloat64 x, PyFloat64 y)
{
  return (PyFloat64)::pow((double)x, (double)y);
}


PyFloat64 math_fmod(PyFloat64 x, PyFloat64 y)
{
  return (PyFloat64)::fmod((double)x, (double)y);
}


PyFloat64 math_copysign(PyFloat64 x, PyFloat64 y)
{
  return (PyFloat64)::copysign((double)x, (double)y);
}


PyFloat64 math_remainder(PyFloat64 x, PyFloat64 y)
{
  return (PyFloat64)::remainder((double)x, (double)y);
}

PY2CPP_END_SCOPE
