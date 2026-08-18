"""``cmath``：复数数学函数（对齐 Python 3.13 ``cmath`` 核心 API）。

路径：``py2cpp.math.complex``（``import cmath`` 的 CPython 同名模块在 Py2Cpp 中请显式导入本模块）。

参考 https://docs.python.org/3.13/library/cmath.html 与 ``Modules/cmathmodule.c``。
组合逻辑为纯 Python，实部/虚部经标量类型与 ``py2cpp.math`` libm；返回值均为 ``complex[Scalar]``。
``Inf``/``NaN``/``Infj``/``NaNj`` 与 ``isFinite``/``isInf``/``isNaN`` 见 ``complex`` 类型静态成员（同 ``float`` 标量策略）。
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


# ---------------------------------------------------------------------------
# 坐标变换
# ---------------------------------------------------------------------------


@immutable
def phase[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> Scalar:
  return atan2(z.imag, z.real)


@immutable
def polar[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> (Scalar, Scalar):
  r: Scalar = hypot(z.real, z.imag)
  p: Scalar = phase(z)
  return (r, p)


@immutable
def rect[Scalar: oneof[float, float64] = float](r: Scalar, phi: Scalar) -> complex[Scalar]:
  unit: complex[Scalar] = new(_rm.cos(phi), _rm.sin(phi))
  return unit * r


# ---------------------------------------------------------------------------
# 幂与对数
# ---------------------------------------------------------------------------


@immutable
def _logCore[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  xr: Scalar = z.real
  xi: Scalar = z.imag
  mod: Scalar = hypot(xr, xi)
  if mod == 0.0:
    raise ValueError("math domain error")
  re: Scalar = _rm.log(mod)
  im: Scalar = atan2(xi, xr)
  return new(re, im)


@immutable
def exp[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  xr: Scalar = z.real
  xi: Scalar = z.imag
  er: Scalar = _rm.exp(xr)
  unit: complex[Scalar] = new(_rm.cos(xi), _rm.sin(xi))
  return unit * er


@overload
@immutable
def log[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  return _logCore(z)


@overload
@immutable
def log[Scalar: oneof[float, float64] = float](z: complex[Scalar], base: Scalar) -> complex[Scalar]:
  core: complex[Scalar] = _logCore(z)
  denom: complex[Scalar] = _logCore(complex[Scalar](base, 0.0))
  return core / denom


@immutable
def log10[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  ln10: complex[Scalar] = new(_rm.log(10.0), 0.0)
  return _logCore(z) / ln10


@immutable
def sqrt[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  half: complex[Scalar] = new(0.5, 0)
  return exp(half * _logCore(z))


# ---------------------------------------------------------------------------
# 三角 / 反三角
# ---------------------------------------------------------------------------


@immutable
def sin[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  x: Scalar = z.real
  y: Scalar = z.imag
  sh: Scalar = _rm.sinh(y)
  ch: Scalar = _rm.cosh(y)
  sx: Scalar = _rm.sin(x)
  cx: Scalar = _rm.cos(x)
  re: Scalar = sx * ch
  im: Scalar = cx * sh
  return new(re, im)


@immutable
def cos[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  x: Scalar = z.real
  y: Scalar = z.imag
  sh: Scalar = _rm.sinh(y)
  ch: Scalar = _rm.cosh(y)
  sx: Scalar = _rm.sin(x)
  cx: Scalar = _rm.cos(x)
  re: Scalar = cx * ch
  im: Scalar = -sx * sh
  return new(re, im)


@immutable
def tan[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  s: complex[Scalar] = sin(z)
  c: complex[Scalar] = cos(z)
  return s / c


@immutable
def asin[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  i: complex[Scalar] = new(0, 1)
  one: complex[Scalar] = new(1, 0)
  zz: complex[Scalar] = z * z
  inner: complex[Scalar] = i * z + sqrt(one - zz)
  w: complex[Scalar] = log(inner)
  negI: complex[Scalar] = -i
  return negI * w


@immutable
def acos[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  half: Scalar = 0.5 * pi
  halfPi: complex[Scalar] = new(half, 0.0)
  return halfPi - asin(z)


@immutable
def atan[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  i: complex[Scalar] = new(0, 1)
  one: complex[Scalar] = new(1, 0)
  halfI: complex[Scalar] = new(0, 0.5)
  num: complex[Scalar] = one - i * z
  denom: complex[Scalar] = one + i * z
  ratio: complex[Scalar] = num / denom
  return halfI * log(ratio)


# ---------------------------------------------------------------------------
# 双曲 / 反双曲
# ---------------------------------------------------------------------------


@immutable
def sinh[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  ez: complex[Scalar] = exp(z)
  en: complex[Scalar] = exp(-z)
  diff: complex[Scalar] = ez - en
  half: complex[Scalar] = new(0.5, 0.0)
  return diff * half


@immutable
def cosh[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  ez: complex[Scalar] = exp(z)
  en: complex[Scalar] = exp(-z)
  total: complex[Scalar] = ez + en
  half: complex[Scalar] = new(0.5, 0.0)
  return total * half


@immutable
def tanh[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  sh: complex[Scalar] = sinh(z)
  ch: complex[Scalar] = cosh(z)
  return sh / ch


@immutable
def asinh[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  one: complex[Scalar] = new(1, 0)
  return log(z + sqrt(z * z + one))


@immutable
def acosh[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  one: complex[Scalar] = new(1, 0)
  return log(z + sqrt(z * z - one))


@immutable
def atanh[Scalar: oneof[float, float64] = float](z: complex[Scalar]) -> complex[Scalar]:
  one: complex[Scalar] = new(1, 0)
  half: complex[Scalar] = new(0.5, 0)
  return half * log((one + z) / (one - z))


@immutable
def isClose[Scalar: oneof[float, float64] = float](
  a: complex[Scalar],
  b: complex[Scalar],
  relTol: Scalar = 1e-09,
  absTol: Scalar = 0.0,
) -> bool:
  if a == b:
    return True
  if complex[Scalar].isInf(a) or complex[Scalar].isInf(b):
    return a == b
  if complex[Scalar].isNaN(a) or complex[Scalar].isNaN(b):
    return False
  diff: Scalar = abs(a - b)
  scaleA: Scalar = abs(a)
  scaleB: Scalar = abs(b)
  scale: Scalar = scaleA
  if scaleB > scale:
    scale = scaleB
  tol: Scalar = relTol * scale
  if absTol > tol:
    tol = absTol
  return diff <= tol
