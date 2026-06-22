"""``cmath``：复数数学函数（对齐 Python 3.13 ``cmath`` 核心 API）。

路径：``py2cpp.math.complex``（``import cmath`` 的 CPython 同名模块在 Py2Cpp 中请显式导入本模块）。

参考 https://docs.python.org/3.13/library/cmath.html 与 ``Modules/cmathmodule.c``。
组合逻辑为纯 Python，实部/虚部经 ``float64`` 与 ``py2cpp.math`` libm；返回值均为 ``complex``。
``Inf``/``NaN``/``Infj``/``NaNj`` 与 ``isfinite``/``isInf``/``isNaN`` 见 ``complex`` 类型静态成员（同 ``float`` 标量策略）。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import ValueError
from ..numeric.complex import complex
from .. import math as _rm
from . import (
  atan2,
  e,
  hypot,
  pi,
  tau,
)

_i: complex @const = 1j


# ---------------------------------------------------------------------------
# 坐标变换
# ---------------------------------------------------------------------------


@immutable
def phase(z: complex) -> float64:
  return atan2(z.imag, z.real)


@immutable
def polar(z: complex) -> (float64, float64):
  r: float64 = hypot(z.real, z.imag)
  p: float64 = phase(z)
  return (r, p)


@immutable
def rect(r: float64, phi: float64) -> complex:
  unit: complex = new(_rm.cos(phi), _rm.sin(phi))
  return unit * r


# ---------------------------------------------------------------------------
# 幂与对数
# ---------------------------------------------------------------------------


@immutable
def _log_core(z: complex) -> complex:
  xr: float64 = z.real
  xi: float64 = z.imag
  mod: float64 = hypot(xr, xi)
  if mod == 0.0:
    raise ValueError("math domain error")
  re: float64 = _rm.log(mod)
  im: float64 = atan2(xi, xr)
  return new(re, im)


@native_name("cmath_*")
@immutable
def exp(z: complex) -> complex:
  xr: float64 = z.real
  xi: float64 = z.imag
  er: float64 = _rm.exp(xr)
  unit: complex = new(_rm.cos(xi), _rm.sin(xi))
  return unit * er


@overload
@native_name("cmath_*")
@immutable
def log(z: complex) -> complex:
  return _log_core(z)


@overload
@native_name("cmath_*")
@immutable
def log(z: complex, base: float64) -> complex:
  core: complex = _log_core(z)
  b: complex = new(base, 0.0)
  denom: complex = _log_core(b)
  return core / denom


@native_name("cmath_*")
@immutable
def log10(z: complex) -> complex:
  ln10: complex = new(_rm.log(10.0), 0.0)
  return _log_core(z) / ln10


@native_name("cmath_*")
@immutable
def sqrt(z: complex) -> complex:
  half: complex = new(0.5, 0)
  return exp(half * _log_core(z))


# ---------------------------------------------------------------------------
# 三角 / 反三角
# ---------------------------------------------------------------------------


@native_name("cmath_*")
@immutable
def sin(z: complex) -> complex:
  x: float64 = z.real
  y: float64 = z.imag
  sh: float64 = _rm.sinh(y)
  ch: float64 = _rm.cosh(y)
  sx: float64 = _rm.sin(x)
  cx: float64 = _rm.cos(x)
  re: float64 = sx * ch
  im: float64 = cx * sh
  return new(re, im)


@native_name("cmath_*")
@immutable
def cos(z: complex) -> complex:
  x: float64 = z.real
  y: float64 = z.imag
  sh: float64 = _rm.sinh(y)
  ch: float64 = _rm.cosh(y)
  sx: float64 = _rm.sin(x)
  cx: float64 = _rm.cos(x)
  re: float64 = cx * ch
  im: float64 = -sx * sh
  return new(re, im)


@native_name("cmath_*")
@immutable
def tan(z: complex) -> complex:
  s: complex = sin(z)
  c: complex = cos(z)
  return s / c


@native_name("cmath_*")
@immutable
def asin(z: complex) -> complex:
  one: complex = new(1, 0)
  zz: complex = z * z
  inner: complex = _i * z + sqrt(one - zz)
  w: complex = log(inner)
  neg_i: complex = -_i
  return neg_i * w


@native_name("cmath_*")
@immutable
def acos(z: complex) -> complex:
  half: float64 = 0.5 * pi
  half_pi: complex = new(half, 0.0)
  return half_pi - asin(z)


@native_name("cmath_*")
@immutable
def atan(z: complex) -> complex:
  one: complex = new(1, 0)
  half_i: complex = new(0, 0.5)
  num: complex = one - _i * z
  denom: complex = one + _i * z
  ratio: complex = num / denom
  return half_i * log(ratio)


# ---------------------------------------------------------------------------
# 双曲 / 反双曲
# ---------------------------------------------------------------------------


@native_name("cmath_*")
@immutable
def sinh(z: complex) -> complex:
  ez: complex = exp(z)
  en: complex = exp(-z)
  diff: complex = ez - en
  half: complex = new(0.5, 0.0)
  return diff * half


@native_name("cmath_*")
@immutable
def cosh(z: complex) -> complex:
  ez: complex = exp(z)
  en: complex = exp(-z)
  total: complex = ez + en
  half: complex = new(0.5, 0.0)
  return total * half


@native_name("cmath_*")
@immutable
def tanh(z: complex) -> complex:
  sh: complex = sinh(z)
  ch: complex = cosh(z)
  return sh / ch


@native_name("cmath_*")
@immutable
def asinh(z: complex) -> complex:
  one: complex = new(1, 0)
  return log(z + sqrt(z * z + one))


@native_name("cmath_*")
@immutable
def acosh(z: complex) -> complex:
  one: complex = new(1, 0)
  return log(z + sqrt(z * z - one))


@native_name("cmath_*")
@immutable
def atanh(z: complex) -> complex:
  one: complex = new(1, 0)
  half: complex = new(0.5, 0)
  return half * log((one + z) / (one - z))


@immutable
def isclose(
  a: complex,
  b: complex,
  rel_tol: float64 = 1e-09,
  abs_tol: float64 = 0.0,
) -> bool:
  if a == b:
    return True
  if complex.isInf(a) or complex.isInf(b):
    return a == b
  if complex.isNaN(a) or complex.isNaN(b):
    return False
  diff: float64 = abs(a - b)
  scale_a: float64 = abs(a)
  scale_b: float64 = abs(b)
  scale: float64 = scale_a
  if scale_b > scale:
    scale = scale_b
  tol: float64 = rel_tol * scale
  if abs_tol > tol:
    tol = abs_tol
  return diff <= tol
