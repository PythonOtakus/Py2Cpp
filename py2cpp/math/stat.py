"""``statistics``：描述统计（对齐 Python 3.13 ``statistics`` 核心子集）。

路径：``py2cpp.math.stat``（``import statistics`` 的 CPython 同名模块在 Py2Cpp 中请显式导入本模块）。

参考 https://docs.python.org/3.13/library/statistics.html 与 ``Lib/statistics.py``。
容器形参使用 ``IterableType[T]``；组合逻辑为纯 Python，复用 ``py2cpp.math`` 与 ``util.misc.Counter``。

**暂未实现**：``kde`` / ``kde_random``、``correlation(..., method='ranked')``、``NormalDist.samples``、``Fraction``/``Decimal`` 精确算术路径。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import StatisticsError, ValueError
from ..util.protocols import DictKeyType, IterableType
from ..util.list import list
from ..util.misc import Counter
from . import erfc, exp, fabs, hypot, log, sqrt, tau

_Sqrt2: float64 @const = 1.4142135623730951


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


@immutable
def _materialize[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> list[Scalar]:
  out: list[Scalar] = []
  for x in data:
    out.append(x)
  return out


@immutable
def _sum[Scalar: oneof[float, float64] = float](xs: list[Scalar]) -> Scalar:
  total: Scalar = 0.0
  comp: Scalar = 0.0
  for i in range(len(xs)):
    x: Scalar = xs[i]
    y: Scalar = x - comp
    t: Scalar = total + y
    comp = (t - total) - y
    total = t
  return total


@immutable
def _bisectLeft[Scalar: oneof[float, float64] = float](a: list[Scalar], x: Scalar, lo: int) -> int:
  hi: int = len(a)
  while lo < hi:
    mid: int = (lo + hi) // 2
    if a[mid] < x:
      lo = mid + 1
    else:
      hi = mid
  return lo


@immutable
def _bisectRight[Scalar: oneof[float, float64] = float](a: list[Scalar], x: Scalar, lo: int) -> int:
  hi: int = len(a)
  while lo < hi:
    mid: int = (lo + hi) // 2
    if a[mid] <= x:
      lo = mid + 1
    else:
      hi = mid
  return lo


@immutable
def _sqrtprod[Scalar: oneof[float, float64] = float](x: Scalar, y: Scalar) -> Scalar:
  return sqrt[Scalar](x * y)


@immutable
def _normalDistInvCdf[Scalar: oneof[float, float64] = float](p: Scalar, mu: Scalar, sigma: Scalar) -> Scalar:
  q: Scalar = p - 0.5
  if fabs[Scalar](q) <= 0.425:
    r: Scalar = 0.180625 - q * q
    num: Scalar = (
      (
        (
          (
            (
              (
                (
                  2509.0809273012266727e3 * r + 33430.575835881281105e4
                )
                * r
                + 67265.770927008700853e4
              )
              * r
              + 45921.953931549871457e4
            )
            * r
            + 13731.693765094611125e4
          )
          * r
          + 1971.5909503065514427e3
        )
        * r
        + 133.14166789178437745e2
      )
      * r
      + 3.3871328727963666080e0
    ) * q
    den: Scalar = (
      (
        (
          (
            (
              (
                (5226.4952788528545610e3 * r + 28729.085735721942674e4) * r + 39307.895800092710610e4
              )
              * r
              + 21213.794301586595867e4
            )
            * r
            + 5394.1960214247511077e3
          )
          * r
          + 687.18700749205790830e2
        )
        * r
        + 42.31333701600911252e1
      )
      * r
      + 1.0
    )
    x: Scalar = num / den
    return mu + x * sigma

  tailR: Scalar = p if q <= 0.0 else 1.0 - p
  tailR = sqrt[Scalar](-log[Scalar](tailR))
  num: Scalar = 0.0
  den: Scalar = 1.0
  if tailR <= 5.0:
    tailR -= 1.6
    num = (
      (
        (
          (
            (
              (
                (7.74545014278341407640e-4 * tailR + 2.27238449892691845833e-2) * tailR + 2.41780725177450611770e-1
              )
              * tailR
              + 1.27045825245236838258e0
            )
            * tailR
            + 3.64784832476320460504e0
          )
          * tailR
          + 5.76949722146069140550e0
        )
        * tailR
        + 4.6301778488618984109e0
      )
      * tailR
      + 1.42343711074968357734e0
    )
    den = (
      (
        (
          (
            (
              (
                (1.05075007164641684324e-9 * tailR + 5.47593808449534452082e-8) * tailR + 1.98682901311009748190e-6
              )
              * tailR
              + 5.39034819765571181726e-5
            )
            * tailR
            + 1.08635003577702313740e-3
          )
          * tailR
          + 1.70221530808101306731e-2
        )
        * tailR
        + 1.39135141456819893247e-1
      )
      * tailR
      + 1.0
    )
  else:
    tailR -= 5.0
    num = (
      (
        (
          (
            (
              (
                (2.01033439929228813265e-7 * tailR + 2.71155556874348757815e-5) * tailR + 1.24201408437628920243e-3
              )
              * tailR
              + 1.94505165435132943082e-2
            )
            * tailR
            + 1.70245072591715627637e-1
          )
          * tailR
          + 1.32853770818818539260e0
        )
        * tailR
        + 8.4505470897995433549e-1
      )
      * tailR
      + 3.2246712907003980707e-1
    )
    den = (
      (
        (
          (
            (
              (
                (2.01033439929228813265e-7 * tailR + 2.76108934939072005662e-5) * tailR + 1.29859299146765180637e-3
              )
              * tailR
              + 1.70276605252253405072e-2
            )
            * tailR
            + 1.3903883181237951452e-1
          )
          * tailR
          + 9.1601147851470048629e-1
        )
        * tailR
        + 2.89693918961538066690e0
      )
      * tailR
      + 6.78765410500808900110e0
    )
  x: Scalar = num / den
  if q < 0.0:
    x = -x
  return mu + x * sigma


@immutable
def _normalCdf[Scalar: oneof[float, float64] = float](mu: Scalar, sigma: Scalar, x: Scalar) -> Scalar:
  return 0.5 * erfc[Scalar]((mu - x) / (sigma * _Sqrt2))


# ---------------------------------------------------------------------------
# 集中趋势
# ---------------------------------------------------------------------------


@immutable
def mean[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  lst: list[Scalar] = _materialize[Scalar](data)
  n: int = len(lst)
  if n < 1:
    raise StatisticsError("mean requires at least one data point")
  return _sum[Scalar](lst) / (n * 1.0)


@immutable
def _fmeanPlain[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  lst: list[Scalar] = _materialize[Scalar](data)
  n: int = len(lst)
  if not n:
    raise StatisticsError("fmean requires at least one data point")
  return _sum[Scalar](lst) / (n * 1.0)


@immutable
def _fmeanWeighted[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], weights: list[Scalar]) -> Scalar:
  xs: list[Scalar] = _materialize[Scalar](data)
  ws: list[Scalar] = []
  for i in range(len(weights)):
    ws.append(weights[i])
  if len(xs) != len(ws):
    raise StatisticsError("data and weights must be the same length")
  num: Scalar = 0.0
  for i in range(len(xs)):
    num += xs[i] * ws[i]
  den: Scalar = _sum[Scalar](ws)
  if not den:
    raise StatisticsError("sum of weights must be non-zero")
  return num / den


@overload
@immutable
def fmean[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  return _fmeanPlain(data)


@overload
@immutable
def fmean[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], weights: list[Scalar]) -> Scalar:
  return _fmeanWeighted(data, weights)


@immutable
def geometricMean[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  n: int = 0
  foundZero: bool = False
  logs: list[Scalar] = []
  for x in data:
    n += 1
    if x > 0.0 or float64.isNaN(x):
      logs.append(log[Scalar](x))
    elif x == 0.0:
      foundZero = True
    else:
      raise StatisticsError("No negative inputs allowed")
  if not n:
    raise StatisticsError("Must have a non-empty dataset")
  total: Scalar = _sum[Scalar](logs)
  if float64.isNaN(total):
    return float64.NaN
  if foundZero:
    if total == float64.Inf:
      return float64.NaN
    return 0.0
  return exp[Scalar](total / (n * 1.0))


@immutable
def _harmonicMeanPlain[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  errmsg: str = "harmonic mean does not support negative values"
  xs: list[Scalar] = _materialize[Scalar](data)
  n: int = len(xs)
  if n < 1:
    raise StatisticsError("harmonicMean requires at least one data point")
  if n == 1:
    if xs[0] < 0.0:
      raise StatisticsError(errmsg)
    return xs[0]
  total: Scalar = 0.0
  for i in range(n):
    if xs[i] < 0.0:
      raise StatisticsError(errmsg)
    if xs[i] == 0.0:
      return 0.0
    total += 1.0 / xs[i]
  if total <= 0.0:
    raise StatisticsError("Weighted sum must be positive")
  return (n * 1.0) / total


@immutable
def _harmonicMeanWeighted[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], weights: list[Scalar]) -> Scalar:
  errmsg: str = "harmonic mean does not support negative values"
  xs: list[Scalar] = _materialize[Scalar](data)
  ws: list[Scalar] = []
  for i in range(len(weights)):
    ws.append(weights[i])
  n: int = len(xs)
  if len(ws) != n:
    raise StatisticsError("NumberType of weights does not match data size")
  if n < 1:
    raise StatisticsError("harmonicMean requires at least one data point")
  sumWeights: Scalar = _sum[Scalar](ws)
  for i in range(n):
    if ws[i] < 0.0:
      raise StatisticsError(errmsg)
  total: Scalar = 0.0
  for i in range(n):
    if xs[i] < 0.0:
      raise StatisticsError(errmsg)
    if xs[i] == 0.0:
      return 0.0
    w: Scalar = ws[i]
    if w:
      total += w / xs[i]
  if total <= 0.0:
    raise StatisticsError("Weighted sum must be positive")
  return sumWeights / total


@overload
@immutable
def harmonicMean[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  return _harmonicMeanPlain(data)


@overload
@immutable
def harmonicMean[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], weights: list[Scalar]) -> Scalar:
  return _harmonicMeanWeighted(data, weights)


@immutable
def median[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  xs: list[Scalar] = _materialize[Scalar](data)
  xs.sort()
  n: int = len(xs)
  if not n:
    raise StatisticsError("no median for empty data")
  if n % 2 == 1:
    return xs[n // 2]
  i: int = n // 2
  return (xs[i - 1] + xs[i]) / 2.0


@immutable
def medianLow[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  xs: list[Scalar] = _materialize[Scalar](data)
  xs.sort()
  n: int = len(xs)
  if not n:
    raise StatisticsError("no median for empty data")
  if n % 2 == 1:
    return xs[n // 2]
  return xs[n // 2 - 1]


@immutable
def medianHigh[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  xs: list[Scalar] = _materialize[Scalar](data)
  xs.sort()
  n: int = len(xs)
  if not n:
    raise StatisticsError("no median for empty data")
  return xs[n // 2]


@immutable
def medianGrouped[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], interval: Scalar = 1.0) -> Scalar:
  xs: list[Scalar] = _materialize[Scalar](data)
  xs.sort()
  n: int = len(xs)
  if not n:
    raise StatisticsError("no median for empty data")
  x: Scalar = xs[n // 2]
  i: int = _bisectLeft[Scalar](xs, x, 0)
  j: int = _bisectRight[Scalar](xs, x, i)
  L: Scalar = x - interval / 2.0
  cf: Scalar = i
  f: Scalar = j - i
  return L + interval * (n / 2.0 - cf) / f


@immutable
def mode[T: DictKeyType](data: list[T]) -> T:
  if not data:
    raise StatisticsError("no mode for empty data")
  counts: Counter[T, int] = new(data)
  best: T = counts.keyAt(0)
  bestN: int = 0
  for i in range(len(counts)):
    c: int = counts.valueAt(i)
    if c > bestN:
      bestN = c
      best = counts.keyAt(i)
  return best


@immutable
def multiMode[T: DictKeyType](data: list[T]) -> list[T]:
  counts: Counter[T, int] = new(data)
  if len(counts) < 1:
    empty: list[T] = []
    return empty
  maxcount: int = 0
  for i in range(len(counts)):
    c: int = counts.valueAt(i)
    if c > maxcount:
      maxcount = c
  out: list[T] = []
  for i in range(len(counts)):
    if counts.valueAt(i) == maxcount:
      out.append(counts.keyAt(i))
  return out


# ---------------------------------------------------------------------------
# 离散程度
# ---------------------------------------------------------------------------


@immutable
def _varianceAt[Scalar: oneof[float, float64] = float](xs: list[Scalar], xbar: Scalar) -> Scalar:
  n: int = len(xs)
  if n < 2:
    raise StatisticsError("variance requires at least two data points")
  ss: Scalar = 0.0
  for i in range(n):
    d: Scalar = xs[i] - xbar
    ss += d * d
  return ss / ((n - 1) * 1.0)


@immutable
def _varianceList[Scalar: oneof[float, float64] = float](xs: list[Scalar]) -> Scalar:
  n: int = len(xs)
  if n < 2:
    raise StatisticsError("variance requires at least two data points")
  xbar: Scalar = _sum[Scalar](xs) / (n * 1.0)
  return _varianceAt[Scalar](xs, xbar)


@overload
@immutable
def variance[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  return _varianceList[Scalar](_materialize[Scalar](data))


@overload
@immutable
def variance[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], xbar: Scalar) -> Scalar:
  return _varianceAt[Scalar](_materialize[Scalar](data), xbar)


@immutable
def _pvarianceAt[Scalar: oneof[float, float64] = float](xs: list[Scalar], mu: Scalar) -> Scalar:
  n: int = len(xs)
  if n < 1:
    raise StatisticsError("pvariance requires at least one data point")
  ss: Scalar = 0.0
  for i in range(n):
    d: Scalar = xs[i] - mu
    ss += d * d
  return ss / (n * 1.0)


@immutable
def _pvarianceList[Scalar: oneof[float, float64] = float](xs: list[Scalar]) -> Scalar:
  n: int = len(xs)
  if n < 1:
    raise StatisticsError("pvariance requires at least one data point")
  mu: Scalar = _sum[Scalar](xs) / (n * 1.0)
  return _pvarianceAt[Scalar](xs, mu)


@overload
@immutable
def pvariance[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  return _pvarianceList[Scalar](_materialize[Scalar](data))


@overload
@immutable
def pvariance[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], mu: Scalar) -> Scalar:
  return _pvarianceAt[Scalar](_materialize[Scalar](data), mu)


@overload
@immutable
def stdev[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  return sqrt[Scalar](variance[Scalar](data))


@overload
@immutable
def stdev[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], xbar: Scalar) -> Scalar:
  return sqrt[Scalar](variance[Scalar](data, xbar))


@overload
@immutable
def pstdev[Scalar: oneof[float, float64] = float](data: IterableType[Scalar]) -> Scalar:
  return sqrt[Scalar](pvariance[Scalar](data))


@overload
@immutable
def pstdev[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], mu: Scalar) -> Scalar:
  return sqrt[Scalar](pvariance[Scalar](data, mu))


# ---------------------------------------------------------------------------
# 分位数
# ---------------------------------------------------------------------------


@immutable
def quantiles[Scalar: oneof[float, float64] = float](data: IterableType[Scalar], n: int = 4, method: str = "exclusive") -> list[Scalar]:
  if n < 1:
    raise StatisticsError("n must be at least 1")
  xs: list[Scalar] = _materialize[Scalar](data)
  xs.sort()
  ld: int = len(xs)
  if ld < 2:
    if ld == 1:
      single: list[Scalar] = []
      v: Scalar = xs[0]
      for i in range(n - 1):
        single.append(v)
      return single
    raise StatisticsError("must have at least one data point")
  if method == "inclusive":
    m: int = ld - 1
    result: list[Scalar] = []
    for i in range(1, n):
      prod: int = i * m
      j: int = prod // n
      delta: int = prod - j * n
      interpolated: Scalar = (xs[j] * (n - delta) + xs[j + 1] * delta) / (n * 1.0)
      result.append(interpolated)
    return result
  if method == "exclusive":
    m = ld + 1
    result: list[Scalar] = []
    for i in range(1, n):
      j = i * m // n
      if j < 1:
        j = 1
      elif j > ld - 1:
        j = ld - 1
      delta = i * m - j * n
      interpolated = (xs[j - 1] * (n - delta) + xs[j] * delta) / (n * 1.0)
      result.append(interpolated)
    return result
  raise ValueError(f"Unknown method: {method!r}")


# ---------------------------------------------------------------------------
# 双变量关系
# ---------------------------------------------------------------------------


@immutable
def _covarianceLists[Scalar: oneof[float, float64] = float](xs: list[Scalar], ys: list[Scalar]) -> Scalar:
  n: int = len(xs)
  if len(ys) != n:
    raise StatisticsError("covariance requires that both inputs have same number of data points")
  if n < 2:
    raise StatisticsError("covariance requires at least two data points")
  xbar: Scalar = _sum[Scalar](xs) / (n * 1.0)
  ybar: Scalar = _sum[Scalar](ys) / (n * 1.0)
  sxy: Scalar = 0.0
  for i in range(n):
    sxy += (xs[i] - xbar) * (ys[i] - ybar)
  return sxy / ((n - 1) * 1.0)


@immutable
def covariance[Scalar: oneof[float, float64] = float](x: IterableType[Scalar], y: IterableType[Scalar]) -> Scalar:
  return _covarianceLists[Scalar](_materialize[Scalar](x), _materialize[Scalar](y))


@immutable
def _correlationLists[Scalar: oneof[float, float64] = float](xs: list[Scalar], ys: list[Scalar], method: str) -> Scalar:
  n: int = len(xs)
  if len(ys) != n:
    raise StatisticsError("correlation requires that both inputs have same number of data points")
  if n < 2:
    raise StatisticsError("correlation requires at least two data points")
  if method != "linear":
    raise ValueError(f"Unknown method: {method!r}")
  xbar: Scalar = _sum[Scalar](xs) / (n * 1.0)
  ybar: Scalar = _sum[Scalar](ys) / (n * 1.0)
  sxy: Scalar = 0.0
  sxx: Scalar = 0.0
  syy: Scalar = 0.0
  for i in range(n):
    dx: Scalar = xs[i] - xbar
    dy: Scalar = ys[i] - ybar
    sxy += dx * dy
    sxx += dx * dx
    syy += dy * dy
  denom: Scalar = _sqrtprod[Scalar](sxx, syy)
  if not denom:
    raise StatisticsError("at least one of the inputs is constant")
  return sxy / denom


@immutable
def correlation[Scalar: oneof[float, float64] = float](x: IterableType[Scalar], y: IterableType[Scalar], method: str = "linear") -> Scalar:
  return _correlationLists[Scalar](_materialize[Scalar](x), _materialize[Scalar](y), method)


@dataclass
class LinearRegression[Scalar: oneof[float, float64] = float]:
  slope: Scalar
  intercept: Scalar


@immutable
def _linearRegressionLists[Scalar: oneof[float, float64] = float](
  xs: list[Scalar],
  ys: list[Scalar],
  proportional: bool,
) -> LinearRegression[Scalar]:
  n: int = len(xs)
  if len(ys) != n:
    raise StatisticsError("linear regression requires that both inputs have same number of data points")
  if n < 2:
    raise StatisticsError("linear regression requires at least two data points")
  xbar: Scalar = 0.0
  ybar: Scalar = 0.0
  if not proportional:
    xbar = _sum[Scalar](xs) / (n * 1.0)
    ybar = _sum[Scalar](ys) / (n * 1.0)
  sxy: Scalar = 0.0
  sxx: Scalar = 0.0
  for i in range(n):
    dx: Scalar = xs[i] - xbar
    dy: Scalar = ys[i] - ybar
    sxy += dx * dy
    sxx += dx * dx
  if not sxx:
    raise StatisticsError("x is constant")
  slope: Scalar = sxy / sxx
  intercept: Scalar = 0.0
  if not proportional:
    intercept = ybar - slope * xbar
  return new(slope, intercept)


@immutable
def linearRegression[Scalar: oneof[float, float64] = float](
  x: IterableType[Scalar],
  y: IterableType[Scalar],
  proportional: bool = False,
) -> LinearRegression[Scalar]:
  return _linearRegressionLists[Scalar](_materialize[Scalar](x), _materialize[Scalar](y), proportional)


# ---------------------------------------------------------------------------
# 正态分布
# ---------------------------------------------------------------------------


@copyable
class NormalDist[Scalar: oneof[float, float64] = float]:
  """正态分布（对齐 ``statistics.NormalDist`` 核心 API）。"""

  def __init__(self, mu: Scalar = 0.0, sigma: Scalar = 1.0):
    if sigma < 0.0:
      raise StatisticsError("sigma must be non-negative")
    self._mu: Scalar = mu
    self._sigma: Scalar = sigma

  @staticmethod
  def fromSamples(data: IterableType[Scalar]) -> Self:
    lst: list[Scalar] = _materialize[Scalar](data)
    n: int = len(lst)
    if n < 2:
      raise StatisticsError("stdev requires at least two data points")
    mu: Scalar = _sum[Scalar](lst) / (n * 1.0)
    ss: Scalar = 0.0
    for i in range(n):
      d: Scalar = lst[i] - mu
      ss += d * d
    sigma: Scalar = sqrt[Scalar](ss / ((n - 1) * 1.0))
    return new(mu, sigma)

  @immutable
  def pdf(self, x: Scalar) -> Scalar:
    variance: Scalar = self._sigma * self._sigma
    if not variance:
      raise StatisticsError("pdf() not defined when sigma is zero")
    diff: Scalar = x - self._mu
    return exp[Scalar](diff * diff / (-2.0 * variance)) / sqrt[Scalar](tau * variance)

  @immutable
  def cdf(self, x: Scalar) -> Scalar:
    if not self._sigma:
      raise StatisticsError("cdf() not defined when sigma is zero")
    return 0.5 * erfc[Scalar]((self._mu - x) / (self._sigma * _Sqrt2))

  @immutable
  def invCdf(self, p: Scalar) -> Scalar:
    if p <= 0.0 or p >= 1.0:
      raise StatisticsError("p must be in the range 0.0 < p < 1.0")
    return _normalDistInvCdf[Scalar](p, self._mu, self._sigma)

  @immutable
  def quantiles(self, n: int = 4) -> list[Scalar]:
    out: list[Scalar] = []
    for i in range(1, n):
      out.append(self.invCdf(i / (n * 1.0)))
    return out

  @immutable
  def zscore(self, x: Scalar) -> Scalar:
    if not self._sigma:
      raise StatisticsError("zscore() not defined when sigma is zero")
    return (x - self._mu) / self._sigma

  @immutable
  def overlap(self, other: Self) -> Scalar:
    XMu: Scalar = self._mu
    XSigma: Scalar = self._sigma
    YMu: Scalar = other._mu
    YSigma: Scalar = other._sigma
    if YSigma < XSigma or (YSigma == XSigma and YMu < XMu):
      swapMu: Scalar = XMu
      XMu = YMu
      YMu = swapMu
      swapSigma: Scalar = XSigma
      XSigma = YSigma
      YSigma = swapSigma
    XVar: Scalar = XSigma * XSigma
    YVar: Scalar = YSigma * YSigma
    if not XVar or not YVar:
      raise StatisticsError("overlap() not defined when sigma is zero")
    dv: Scalar = YVar - XVar
    dm: Scalar = fabs[Scalar](YMu - XMu)
    if not dv:
      return erfc[Scalar](dm / (2.0 * XSigma * _Sqrt2))
    a: Scalar = XMu * YVar - YMu * XVar
    sigProd: Scalar = XSigma * YSigma
    radic: Scalar = sqrt[Scalar](dm * dm + dv * log[Scalar](YVar / XVar))
    b: Scalar = sigProd * radic
    x1: Scalar = (a + b) / dv
    x2: Scalar = (a - b) / dv
    return 1.0 - (
      fabs[Scalar](_normalCdf[Scalar](YMu, YSigma, x1) - _normalCdf[Scalar](XMu, XSigma, x1))
      + fabs[Scalar](_normalCdf[Scalar](YMu, YSigma, x2) - _normalCdf[Scalar](XMu, XSigma, x2))
    )

  @property
  def mean(self) -> Scalar:
    return self._mu

  @property
  def median(self) -> Scalar:
    return self._mu

  @property
  def mode(self) -> Scalar:
    return self._mu

  @property
  def stdev(self) -> Scalar:
    return self._sigma

  @property
  def variance(self) -> Scalar:
    return self._sigma * self._sigma

  @overload
  def __add__(self, other: Self) -> Self:
    return new(self._mu + other._mu, hypot[Scalar](self._sigma, other._sigma))

  @overload
  def __add__(self, other: Scalar) -> Self:
    return new(self._mu + other, self._sigma)

  @overload
  def __sub__(self, other: Self) -> Self:
    return new(self._mu - other._mu, hypot[Scalar](self._sigma, other._sigma))

  @overload
  def __sub__(self, other: Scalar) -> Self:
    return new(self._mu - other, self._sigma)

  @overload
  def __mul__(self, other: Scalar) -> Self:
    return new(self._mu * other, self._sigma * fabs[Scalar](other))

  @immutable
  def __eq__(self, other: Self) -> bool:
    return self._mu == other._mu and self._sigma == other._sigma
