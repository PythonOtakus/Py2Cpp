"""``math``：浮点数学函数（对齐 Python 3.13 ``math`` 核心 API）。

路径：``py2cpp.math``（``import math`` 的 CPython 同名模块在 Py2Cpp 中请显式导入本包）。

``Inf`` / ``NaN`` 请用标量静态属性 ``float.Inf``、``float64.NaN`` 等（见 ``py_types.h``）；``isFinite`` / ``isInf`` / ``isNaN`` 为 ``float`` / ``float64`` 静态方法。**无** ``math.inf`` / ``math.nan`` / ``math.isinf`` 等。

参考 https://docs.python.org/3.13/library/math.html 与 ``Modules/mathmodule.c`` / ``Lib/math.py``。
超越函数直接分派到 ``ffi.crt.math`` 的 CRT 绑定；组合逻辑为纯 Python。

**暂未实现**：``frexp`` / ``modf`` / ``ldexp``、``nextafter`` / ``ulp``、``sumprod`` 等。
"""
from __future__ import annotations

from ..builtins import *
from ffi.crt.math import (
  pyiAcos, pyiAcosf, pyiAcosh, pyiAcoshf, pyiAsin, pyiAsinf, pyiAsinh, pyiAsinhf,
  pyiAtan, pyiAtanf, pyiAtan2, pyiAtan2F, pyiAtanh, pyiAtanhf, pyiCbrt, pyiCbrtf,
  pyiCeil, pyiCeilf, pyiCopysign, pyiCopysignf, pyiCos, pyiCosf, pyiCosh, pyiCoshf,
  pyiErf, pyiErff, pyiErfc, pyiErfcf, pyiExp, pyiExpf, pyiExp2, pyiExp2F,
  pyiExpm1, pyiExpm1F, pyiFabs, pyiFabsf, pyiFloor, pyiFloorf, pyiFmod, pyiFmodf,
  pyiHypot, pyiHypotf, pyiLgamma, pyiLgammaf, pyiLog, pyiLogf, pyiLog1P, pyiLog1Pf,
  pyiLog2, pyiLog2F, pyiLog10, pyiLog10F, pyiPow, pyiPowf, pyiRemainder,
  pyiRemainderf, pyiSin, pyiSinf, pyiSinh, pyiSinhf, pyiSqrt, pyiSqrtf, pyiTan,
  pyiTanf, pyiTanh, pyiTanhf, pyiTgamma, pyiTgammaf, pyiTrunc, pyiTruncf,
)
from ..core.exceptions import ValueError
from ..util.list import list

# ---------------------------------------------------------------------------
# 常量（与 CPython / libm 一致）
# ---------------------------------------------------------------------------

pi: float64 @const = 3.14159265358979323846

e: float64 @const = 2.71828182845904523536

tau: float64 @const = 6.28318530717958647692


# ---------------------------------------------------------------------------
# CRT `math.h` FFI
# ---------------------------------------------------------------------------

@immutable
def sqrt[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiSqrtf(x)
  elif Scalar is float64:
    return pyiSqrt(x)

@immutable
def fabs[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiFabsf(x)
  elif Scalar is float64:
    return pyiFabs(x)

@immutable
def floor[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiFloorf(x)
  elif Scalar is float64:
    return pyiFloor(x)

@immutable
def ceil[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiCeilf(x)
  elif Scalar is float64:
    return pyiCeil(x)

@immutable
def trunc[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiTruncf(x)
  elif Scalar is float64:
    return pyiTrunc(x)

@immutable
def sin[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiSinf(x)
  elif Scalar is float64:
    return pyiSin(x)

@immutable
def cos[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiCosf(x)
  elif Scalar is float64:
    return pyiCos(x)

@immutable
def tan[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiTanf(x)
  elif Scalar is float64:
    return pyiTan(x)

@immutable
def asin[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiAsinf(x)
  elif Scalar is float64:
    return pyiAsin(x)

@immutable
def acos[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiAcosf(x)
  elif Scalar is float64:
    return pyiAcos(x)

@immutable
def atan[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiAtanf(x)
  elif Scalar is float64:
    return pyiAtan(x)

@immutable
def sinh[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiSinhf(x)
  elif Scalar is float64:
    return pyiSinh(x)

@immutable
def cosh[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiCoshf(x)
  elif Scalar is float64:
    return pyiCosh(x)

@immutable
def tanh[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiTanhf(x)
  elif Scalar is float64:
    return pyiTanh(x)

@immutable
def asinh[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiAsinhf(x)
  elif Scalar is float64:
    return pyiAsinh(x)

@immutable
def acosh[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiAcoshf(x)
  elif Scalar is float64:
    return pyiAcosh(x)

@immutable
def atanh[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiAtanhf(x)
  elif Scalar is float64:
    return pyiAtanh(x)

@immutable
def exp[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiExpf(x)
  elif Scalar is float64:
    return pyiExp(x)

@immutable
def exp2[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiExp2F(x)
  elif Scalar is float64:
    return pyiExp2(x)

@immutable
def expm1[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiExpm1F(x)
  elif Scalar is float64:
    return pyiExpm1(x)

@immutable
def log[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiLogf(x)
  elif Scalar is float64:
    return pyiLog(x)

@immutable
def log2[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiLog2F(x)
  elif Scalar is float64:
    return pyiLog2(x)

@immutable
def log10[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiLog10F(x)
  elif Scalar is float64:
    return pyiLog10(x)

@immutable
def log1p[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiLog1Pf(x)
  elif Scalar is float64:
    return pyiLog1P(x)

@immutable
def erf[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiErff(x)
  elif Scalar is float64:
    return pyiErf(x)

@immutable
def erfc[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiErfcf(x)
  elif Scalar is float64:
    return pyiErfc(x)

@immutable
def gamma[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiTgammaf(x)
  elif Scalar is float64:
    return pyiTgamma(x)

@immutable
def lgamma[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiLgammaf(x)
  elif Scalar is float64:
    return pyiLgamma(x)

@immutable
def cbrt[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiCbrtf(x)
  elif Scalar is float64:
    return pyiCbrt(x)

@immutable
def atan2[Scalar: oneof[float, float64] = float](y: Scalar, x: Scalar) -> Scalar:
  if Scalar is float:
    return pyiAtan2F(y, x)
  elif Scalar is float64:
    return pyiAtan2(y, x)

@immutable
def hypot[Scalar: oneof[float, float64] = float](x: Scalar, y: Scalar) -> Scalar:
  if Scalar is float:
    return pyiHypotf(x, y)
  elif Scalar is float64:
    return pyiHypot(x, y)

@immutable
def pow[Scalar: oneof[float, float64] = float](x: Scalar, y: Scalar) -> Scalar:
  if Scalar is float:
    return pyiPowf(x, y)
  elif Scalar is float64:
    return pyiPow(x, y)

@immutable
def fmod[Scalar: oneof[float, float64] = float](x: Scalar, y: Scalar) -> Scalar:
  if Scalar is float:
    return pyiFmodf(x, y)
  elif Scalar is float64:
    return pyiFmod(x, y)

@immutable
def copySign[Scalar: oneof[float, float64] = float](x: Scalar, y: Scalar) -> Scalar:
  if Scalar is float:
    return pyiCopysignf(x, y)
  elif Scalar is float64:
    return pyiCopysign(x, y)

@immutable
def remainder[Scalar: oneof[float, float64] = float](x: Scalar, y: Scalar) -> Scalar:
  if Scalar is float:
    return pyiRemainderf(x, y)
  elif Scalar is float64:
    return pyiRemainder(x, y)

# ---------------------------------------------------------------------------
# 纯 Python 组合
# ---------------------------------------------------------------------------


@immutable
def degrees[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  return x * (180.0 / pi)


@immutable
def radians[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  return x * (pi / 180.0)


@immutable
def almost[Scalar: oneof[float, float64] = float](x: Scalar, y: Scalar) -> bool:
  """游戏数学常用绝对容差（``1e-5``）。"""
  return abs(x - y) <= 1e-5


@immutable
def safeSqrt[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  """``sqrt`` 的非负实域版本（``x<=0`` 时返回 ``0``）。"""
  if x <= 0.0:
    return 0.0
  return sqrt[Scalar](x)


@immutable
def sign[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if x < 0.0:
    return -1.0
  if x > 0.0:
    return 1.0
  return 0.0


@immutable
def clamp[Scalar: oneof[float, float64] = float](x: Scalar, minValue: Scalar, maxValue: Scalar) -> Scalar:
  if x < minValue:
    return minValue
  if x > maxValue:
    return maxValue
  return x


@immutable
def clamp01[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  return clamp(x, 0.0, 1.0)


@immutable
def reflect[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  v: Scalar = x - floor[Scalar](x * 0.5) * 2.0
  if v > 1.0:
    return 2.0 - v
  return v


@immutable
def repeat[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  return x - floor[Scalar](x)


@immutable
def moveTowards[Scalar: oneof[float, float64] = float](a: Scalar, b: Scalar, delta: Scalar) -> Scalar:
  if a < b:
    return a + delta
  if a > b:
    return a - delta
  return a


@immutable
def lerp[Scalar: oneof[float, float64] = float](a: Scalar, b: Scalar, t: Scalar) -> Scalar:
  return a + (b - a) * t


@immutable
def ease[Scalar: oneof[float, float64] = float](x: Scalar) -> Scalar:
  if x < 0.0:
    return 0.0
  if x > 1.0:
    return 1.0
  return x * x * (3.0 - 2.0 * x)


@immutable
def smoothStep[Scalar: oneof[float, float64] = float](edge0: Scalar, edge1: Scalar, x: Scalar) -> Scalar:
  if x < edge0:
    return 0.0
  if x > edge1:
    return 1.0
  t: Scalar = (x - edge0) / (edge1 - edge0)
  return t * t * (3.0 - 2.0 * t)


@immutable
def isClose[Scalar: oneof[float, float64] = float](
  a: Scalar,
  b: Scalar,
  relTol: Scalar = 1e-09,
  absTol: Scalar = 0.0,
) -> bool:
  """对齐 ``math.isClose``（``relTol`` / ``absTol`` 关键字在调用处传入）。"""
  if a == b:
    return True
  if float64.isInf(a) or float64.isInf(b):
    return a == b
  if float64.isNaN(a) or float64.isNaN(b):
    return False
  diff: Scalar = fabs[Scalar](a - b)
  scaleA: Scalar = fabs[Scalar](a)
  scaleB: Scalar = fabs[Scalar](b)
  scale: Scalar = scaleA
  if scaleB > scale:
    scale = scaleB
  tol: Scalar = relTol * scale
  if absTol > tol:
    tol = absTol
  return diff <= tol


@immutable
def factorial(n: int) -> int:
  if n < 0:
    raise ValueError("factorial() not defined for negative values")
  r: int = 1
  for i in range(2, n + 1):
    r *= i
  return r


@immutable
def gcd(a: int, b: int) -> int:
  x: int = a if a >= 0 else -a
  y: int = b if b >= 0 else -b
  while y != 0:
    t: int = y
    y = x % y
    x = t
  return x


@immutable
def lcm(a: int, b: int) -> int:
  if a == 0 or b == 0:
    return 0
  g: int = gcd(a, b)
  return (a // g) * b


@immutable
def isqrt(n: int) -> int:
  if n < 0:
    raise ValueError("isqrt() argument must be nonnegative")
  if n < 2:
    return n
  lo: int = 1
  hi: int = n
  while lo < hi:
    mid: int = (lo + hi + 1) // 2
    sq: int = mid * mid
    if sq <= n:
      lo = mid
    else:
      hi = mid - 1
  return lo


@immutable
def comb(n: int, k: int) -> int:
  if k < 0 or k > n:
    raise ValueError("k out of range")
  return factorial(n) // (factorial(k) * factorial(n - k))


@immutable
def _permNk(n: int, k: int) -> int:
  if k < 0 or k > n:
    raise ValueError("k out of range")
  return factorial(n) // factorial(n - k)


@overload
@immutable
def perm(n: int) -> int:
  return _permNk(n, n)


@overload
@immutable
def perm(n: int, k: int) -> int:
  return _permNk(n, k)


@immutable
def prod[Scalar: oneof[float, float64] = float](iterable: list[Scalar]) -> Scalar:
  r: Scalar = 1.0
  for i in range(len(iterable)):
    r *= iterable[i]
  return r


@immutable
def dist[Scalar: oneof[float, float64] = float](p: list[Scalar], q: list[Scalar]) -> Scalar:
  if len(p) != len(q):
    raise ValueError("both points must have the same number of dimensions")
  s: Scalar = 0.0
  for i in range(len(p)):
    d: Scalar = p[i] - q[i]
    s += d * d
  return sqrt[Scalar](s)


@immutable
def fsum[Scalar: oneof[float, float64] = float](iterable: list[Scalar]) -> Scalar:
  """Kahan 补偿求和（对齐 ``Lib/math.py`` ``fsum`` 核心路径）。"""
  total: Scalar = 0.0
  comp: Scalar = 0.0
  for i in range(len(iterable)):
    x: Scalar = iterable[i]
    y: Scalar = x - comp
    t: Scalar = total + y
    comp = (t - total) - y
    total = t
  return total
