"""``math``：浮点数学函数（对齐 Python 3.13 ``math`` 核心 API）。

路径：``py2cpp.math``（``import math`` 的 CPython 同名模块在 Py2Cpp 中请显式导入本包）。

``Inf`` / ``NaN`` 请用标量静态属性 ``float.Inf``、``float64.NaN`` 等（见 ``py_types.h``）；``isfinite`` / ``isInf`` / ``isNaN`` 为 ``float`` / ``float64`` 静态方法。**无** ``math.inf`` / ``math.nan`` / ``math.isinf`` 等。

参考 https://docs.python.org/3.13/library/math.html 与 ``Modules/mathmodule.c`` / ``Lib/math.py``。
超越函数与分类谓词为 ``@native``（``templates/-math.inl`` paste_before → ``math.inl``）；组合逻辑为纯 Python。

**暂未实现**：``frexp`` / ``modf`` / ``ldexp``、``nextafter`` / ``ulp``、``sumprod`` 等。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import ValueError
from ..util.list import list

# ---------------------------------------------------------------------------
# 常量（与 CPython / libm 一致）
# ---------------------------------------------------------------------------

pi: float64 @const = 3.14159265358979323846

e: float64 @const = 2.71828182845904523536

tau: float64 @const = 6.28318530717958647692


# ---------------------------------------------------------------------------
# libm 一元 / 二元（``@native``）
# ---------------------------------------------------------------------------


@native
@native_name("math_*")
@immutable
def sqrt(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def fabs(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def floor(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def ceil(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def trunc(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def sin(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def cos(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def tan(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def asin(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def acos(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def atan(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def sinh(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def cosh(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def tanh(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def asinh(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def acosh(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def atanh(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def exp(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def exp2(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def expm1(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def log(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def log2(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def log10(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def log1p(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def erf(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def erfc(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def gamma(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def lgamma(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def cbrt(x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def atan2(y: float64, x: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def hypot(x: float64, y: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def pow(x: float64, y: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def fmod(x: float64, y: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def copysign(x: float64, y: float64) -> float64:
  ...


@native
@native_name("math_*")
@immutable
def remainder(x: float64, y: float64) -> float64:
  ...


# ---------------------------------------------------------------------------
# 纯 Python 组合
# ---------------------------------------------------------------------------


@immutable
def degrees(x: float64) -> float64:
  return x * (180.0 / pi)


@immutable
def radians(x: float64) -> float64:
  return x * (pi / 180.0)


@immutable
def almost(x: float64, y: float64) -> bool:
  """游戏数学常用绝对容差（``1e-5``）。"""
  return abs(x - y) <= 1e-5


@immutable
def safe_sqrt(x: float64) -> float64:
  """``sqrt`` 的非负实域版本（``x<=0`` 时返回 ``0``）。"""
  if x <= 0.0:
    return 0.0
  return sqrt(x)


@immutable
def sign(x: float64) -> float64:
  if x < 0.0:
    return -1.0
  if x > 0.0:
    return 1.0
  return 0.0


@immutable
def clamp(x: float64, min_value: float64, max_value: float64) -> float64:
  if x < min_value:
    return min_value
  if x > max_value:
    return max_value
  return x


@immutable
def clamp01(x: float64) -> float64:
  return clamp(x, 0.0, 1.0)


@immutable
def reflect(x: float64) -> float64:
  v: float64 = x - floor(x * 0.5) * 2.0
  if v > 1.0:
    return 2.0 - v
  return v


@immutable
def repeat(x: float64) -> float64:
  return x - floor(x)


@immutable
def move_towards(a: float64, b: float64, delta: float64) -> float64:
  if a < b:
    return a + delta
  if a > b:
    return a - delta
  return a


@immutable
def lerp(a: float64, b: float64, t: float64) -> float64:
  return a + (b - a) * t


@immutable
def ease(x: float64) -> float64:
  if x < 0.0:
    return 0.0
  if x > 1.0:
    return 1.0
  return x * x * (3.0 - 2.0 * x)


@immutable
def smooth_step(edge0: float64, edge1: float64, x: float64) -> float64:
  if x < edge0:
    return 0.0
  if x > edge1:
    return 1.0
  t: float64 = (x - edge0) / (edge1 - edge0)
  return t * t * (3.0 - 2.0 * t)


@immutable
def isclose(
  a: float64,
  b: float64,
  rel_tol: float64 = 1e-09,
  abs_tol: float64 = 0.0,
) -> bool:
  """对齐 ``math.isclose``（``rel_tol`` / ``abs_tol`` 关键字在调用处传入）。"""
  if a == b:
    return True
  if float64.isInf(a) or float64.isInf(b):
    return a == b
  if float64.isNaN(a) or float64.isNaN(b):
    return False
  diff: float64 = fabs(a - b)
  scale_a: float64 = fabs(a)
  scale_b: float64 = fabs(b)
  scale: float64 = scale_a
  if scale_b > scale:
    scale = scale_b
  tol: float64 = rel_tol * scale
  if abs_tol > tol:
    tol = abs_tol
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
def _perm_nk(n: int, k: int) -> int:
  if k < 0 or k > n:
    raise ValueError("k out of range")
  return factorial(n) // factorial(n - k)


@overload
@immutable
def perm(n: int) -> int:
  return _perm_nk(n, n)


@overload
@immutable
def perm(n: int, k: int) -> int:
  return _perm_nk(n, k)


@immutable
def prod(iterable: list[float64]) -> float64:
  r: float64 = 1.0
  for i in range(len(iterable)):
    r *= iterable[i]
  return r


@immutable
def dist(p: list[float64], q: list[float64]) -> float64:
  if len(p) != len(q):
    raise ValueError("both points must have the same number of dimensions")
  s: float64 = 0.0
  for i in range(len(p)):
    d: float64 = p[i] - q[i]
    s += d * d
  return sqrt(s)


@immutable
def fsum(iterable: list[float64]) -> float64:
  """Kahan 补偿求和（对齐 ``Lib/math.py`` ``fsum`` 核心路径）。"""
  total: float64 = 0.0
  comp: float64 = 0.0
  for i in range(len(iterable)):
    x: float64 = iterable[i]
    y: float64 = x - comp
    t: float64 = total + y
    comp = (t - total) - y
    total = t
  return total
