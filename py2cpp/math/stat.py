"""``statistics``：描述统计（对齐 Python 3.13 ``statistics`` 核心子集）。

路径：``py2cpp.math.stat``（``import statistics`` 的 CPython 同名模块在 Py2Cpp 中请显式导入本模块）。

参考 https://docs.python.org/3.13/library/statistics.html 与 ``Lib/statistics.py``。
容器形参使用 ``Iterable[T]``；组合逻辑为纯 Python，复用 ``py2cpp.math`` 与 ``util.misc.Counter``。

**暂未实现**：``kde`` / ``kde_random``、``correlation(..., method='ranked')``、``NormalDist.samples``、``Fraction``/``Decimal`` 精确算术路径。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import StatisticsError, ValueError
from ..util.protocols import DictKey, Iterable
from ..util.list import list
from ..util.misc import Counter
from . import erfc, exp, fabs, hypot, log, sqrt, tau

_SQRT2: float64 @const = 1.4142135623730951


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


@immutable
def _materialize_f64(data: Iterable[float64]) -> list[float64]:
  out: list[float64] = []
  for x in data:
    out.append(x)
  return out


@immutable
def _sum_f64(xs: list[float64]) -> float64:
  total: float64 = 0.0
  comp: float64 = 0.0
  for i in range(len(xs)):
    x: float64 = xs[i]
    y: float64 = x - comp
    t: float64 = total + y
    comp = (t - total) - y
    total = t
  return total


@immutable
def _bisect_left(a: list[float64], x: float64, lo: int) -> int:
  hi: int = len(a)
  while lo < hi:
    mid: int = (lo + hi) // 2
    if a[mid] < x:
      lo = mid + 1
    else:
      hi = mid
  return lo


@immutable
def _bisect_right(a: list[float64], x: float64, lo: int) -> int:
  hi: int = len(a)
  while lo < hi:
    mid: int = (lo + hi) // 2
    if a[mid] <= x:
      lo = mid + 1
    else:
      hi = mid
  return lo


@immutable
def _sqrtprod(x: float64, y: float64) -> float64:
  return sqrt(x * y)


@immutable
def _normal_dist_inv_cdf(p: float64, mu: float64, sigma: float64) -> float64:
  q: float64 = p - 0.5
  if fabs(q) <= 0.425:
    r: float64 = 0.180625 - q * q
    num: float64 = (
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
    den: float64 = (
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
    x: float64 = num / den
    return mu + x * sigma

  tail_r: float64 = p if q <= 0.0 else 1.0 - p
  tail_r = sqrt(-log(tail_r))
  num: float64 = 0.0
  den: float64 = 1.0
  if tail_r <= 5.0:
    tail_r -= 1.6
    num = (
      (
        (
          (
            (
              (
                (7.74545014278341407640e-4 * tail_r + 2.27238449892691845833e-2) * tail_r + 2.41780725177450611770e-1
              )
              * tail_r
              + 1.27045825245236838258e0
            )
            * tail_r
            + 3.64784832476320460504e0
          )
          * tail_r
          + 5.76949722146069140550e0
        )
        * tail_r
        + 4.6301778488618984109e0
      )
      * tail_r
      + 1.42343711074968357734e0
    )
    den = (
      (
        (
          (
            (
              (
                (1.05075007164641684324e-9 * tail_r + 5.47593808449534452082e-8) * tail_r + 1.98682901311009748190e-6
              )
              * tail_r
              + 5.39034819765571181726e-5
            )
            * tail_r
            + 1.08635003577702313740e-3
          )
          * tail_r
          + 1.70221530808101306731e-2
        )
        * tail_r
        + 1.39135141456819893247e-1
      )
      * tail_r
      + 1.0
    )
  else:
    tail_r -= 5.0
    num = (
      (
        (
          (
            (
              (
                (2.01033439929228813265e-7 * tail_r + 2.71155556874348757815e-5) * tail_r + 1.24201408437628920243e-3
              )
              * tail_r
              + 1.94505165435132943082e-2
            )
            * tail_r
            + 1.70245072591715627637e-1
          )
          * tail_r
          + 1.32853770818818539260e0
        )
        * tail_r
        + 8.4505470897995433549e-1
      )
      * tail_r
      + 3.2246712907003980707e-1
    )
    den = (
      (
        (
          (
            (
              (
                (2.01033439929228813265e-7 * tail_r + 2.76108934939072005662e-5) * tail_r + 1.29859299146765180637e-3
              )
              * tail_r
              + 1.70276605252253405072e-2
            )
            * tail_r
            + 1.3903883181237951452e-1
          )
          * tail_r
          + 9.1601147851470048629e-1
        )
        * tail_r
        + 2.89693918961538066690e0
      )
      * tail_r
      + 6.78765410500808900110e0
    )
  x: float64 = num / den
  if q < 0.0:
    x = -x
  return mu + x * sigma


@immutable
def _normal_cdf(mu: float64, sigma: float64, x: float64) -> float64:
  return 0.5 * erfc((mu - x) / (sigma * _SQRT2))


# ---------------------------------------------------------------------------
# 集中趋势
# ---------------------------------------------------------------------------


@immutable
def mean(data: Iterable[float64]) -> float64:
  lst: list[float64] = _materialize_f64(data)
  n: int = len(lst)
  if n < 1:
    raise StatisticsError("mean requires at least one data point")
  return _sum_f64(lst) / (n * 1.0)


@immutable
def _fmean_plain(data: Iterable[float64]) -> float64:
  lst: list[float64] = _materialize_f64(data)
  n: int = len(lst)
  if not n:
    raise StatisticsError("fmean requires at least one data point")
  return _sum_f64(lst) / (n * 1.0)


@immutable
def _fmean_weighted(data: Iterable[float64], weights: list[float64]) -> float64:
  xs: list[float64] = _materialize_f64(data)
  ws: list[float64] = []
  for i in range(len(weights)):
    ws.append(weights[i])
  if len(xs) != len(ws):
    raise StatisticsError("data and weights must be the same length")
  num: float64 = 0.0
  for i in range(len(xs)):
    num += xs[i] * ws[i]
  den: float64 = _sum_f64(ws)
  if not den:
    raise StatisticsError("sum of weights must be non-zero")
  return num / den


@overload
@immutable
def fmean(data: Iterable[float64]) -> float64:
  return _fmean_plain(data)


@overload
@immutable
def fmean(data: Iterable[float64], weights: list[float64]) -> float64:
  return _fmean_weighted(data, weights)


@immutable
def geometric_mean(data: Iterable[float64]) -> float64:
  n: int = 0
  found_zero: bool = False
  logs: list[float64] = []
  for x in data:
    n += 1
    if x > 0.0 or float64.isNaN(x):
      logs.append(log(x))
    elif x == 0.0:
      found_zero = True
    else:
      raise StatisticsError("No negative inputs allowed")
  if not n:
    raise StatisticsError("Must have a non-empty dataset")
  total: float64 = _sum_f64(logs)
  if float64.isNaN(total):
    return float64.NaN
  if found_zero:
    if total == float64.Inf:
      return float64.NaN
    return 0.0
  return exp(total / (n * 1.0))


@immutable
def _harmonic_mean_plain(data: Iterable[float64]) -> float64:
  errmsg: str = "harmonic mean does not support negative values"
  xs: list[float64] = _materialize_f64(data)
  n: int = len(xs)
  if n < 1:
    raise StatisticsError("harmonic_mean requires at least one data point")
  if n == 1:
    if xs[0] < 0.0:
      raise StatisticsError(errmsg)
    return xs[0]
  total: float64 = 0.0
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
def _harmonic_mean_weighted(data: Iterable[float64], weights: list[float64]) -> float64:
  errmsg: str = "harmonic mean does not support negative values"
  xs: list[float64] = _materialize_f64(data)
  ws: list[float64] = []
  for i in range(len(weights)):
    ws.append(weights[i])
  n: int = len(xs)
  if len(ws) != n:
    raise StatisticsError("Number of weights does not match data size")
  if n < 1:
    raise StatisticsError("harmonic_mean requires at least one data point")
  sum_weights: float64 = _sum_f64(ws)
  for i in range(n):
    if ws[i] < 0.0:
      raise StatisticsError(errmsg)
  total: float64 = 0.0
  for i in range(n):
    if xs[i] < 0.0:
      raise StatisticsError(errmsg)
    if xs[i] == 0.0:
      return 0.0
    w: float64 = ws[i]
    if w:
      total += w / xs[i]
  if total <= 0.0:
    raise StatisticsError("Weighted sum must be positive")
  return sum_weights / total


@overload
@immutable
def harmonic_mean(data: Iterable[float64]) -> float64:
  return _harmonic_mean_plain(data)


@overload
@immutable
def harmonic_mean(data: Iterable[float64], weights: list[float64]) -> float64:
  return _harmonic_mean_weighted(data, weights)


@immutable
def median(data: Iterable[float64]) -> float64:
  xs: list[float64] = _materialize_f64(data)
  xs.sort()
  n: int = len(xs)
  if not n:
    raise StatisticsError("no median for empty data")
  if n % 2 == 1:
    return xs[n // 2]
  i: int = n // 2
  return (xs[i - 1] + xs[i]) / 2.0


@immutable
def median_low(data: Iterable[float64]) -> float64:
  xs: list[float64] = _materialize_f64(data)
  xs.sort()
  n: int = len(xs)
  if not n:
    raise StatisticsError("no median for empty data")
  if n % 2 == 1:
    return xs[n // 2]
  return xs[n // 2 - 1]


@immutable
def median_high(data: Iterable[float64]) -> float64:
  xs: list[float64] = _materialize_f64(data)
  xs.sort()
  n: int = len(xs)
  if not n:
    raise StatisticsError("no median for empty data")
  return xs[n // 2]


@immutable
def median_grouped(data: Iterable[float64], interval: float64 = 1.0) -> float64:
  xs: list[float64] = _materialize_f64(data)
  xs.sort()
  n: int = len(xs)
  if not n:
    raise StatisticsError("no median for empty data")
  x: float64 = xs[n // 2]
  i: int = _bisect_left(xs, x, 0)
  j: int = _bisect_right(xs, x, i)
  L: float64 = x - interval / 2.0
  cf: float64 = i
  f: float64 = j - i
  return L + interval * (n / 2.0 - cf) / f


@immutable
def mode[T: DictKey](data: list[T]) -> T:
  if not data:
    raise StatisticsError("no mode for empty data")
  counts: Counter[T, int] = new(data)
  best: T = counts.key_at(0)
  best_n: int = 0
  for i in range(len(counts)):
    c: int = counts.value_at(i)
    if c > best_n:
      best_n = c
      best = counts.key_at(i)
  return best


@immutable
def multimode[T: DictKey](data: list[T]) -> list[T]:
  counts: Counter[T, int] = new(data)
  if len(counts) < 1:
    empty: list[T] = []
    return empty
  maxcount: int = 0
  for i in range(len(counts)):
    c: int = counts.value_at(i)
    if c > maxcount:
      maxcount = c
  out: list[T] = []
  for i in range(len(counts)):
    if counts.value_at(i) == maxcount:
      out.append(counts.key_at(i))
  return out


# ---------------------------------------------------------------------------
# 离散程度
# ---------------------------------------------------------------------------


@immutable
def _variance_at(xs: list[float64], xbar: float64) -> float64:
  n: int = len(xs)
  if n < 2:
    raise StatisticsError("variance requires at least two data points")
  ss: float64 = 0.0
  for i in range(n):
    d: float64 = xs[i] - xbar
    ss += d * d
  return ss / ((n - 1) * 1.0)


@immutable
def _variance_list(xs: list[float64]) -> float64:
  n: int = len(xs)
  if n < 2:
    raise StatisticsError("variance requires at least two data points")
  xbar: float64 = _sum_f64(xs) / (n * 1.0)
  return _variance_at(xs, xbar)


@overload
@immutable
def variance(data: Iterable[float64]) -> float64:
  return _variance_list(_materialize_f64(data))


@overload
@immutable
def variance(data: Iterable[float64], xbar: float64) -> float64:
  return _variance_at(_materialize_f64(data), xbar)


@immutable
def _pvariance_at(xs: list[float64], mu: float64) -> float64:
  n: int = len(xs)
  if n < 1:
    raise StatisticsError("pvariance requires at least one data point")
  ss: float64 = 0.0
  for i in range(n):
    d: float64 = xs[i] - mu
    ss += d * d
  return ss / (n * 1.0)


@immutable
def _pvariance_list(xs: list[float64]) -> float64:
  n: int = len(xs)
  if n < 1:
    raise StatisticsError("pvariance requires at least one data point")
  mu: float64 = _sum_f64(xs) / (n * 1.0)
  return _pvariance_at(xs, mu)


@overload
@immutable
def pvariance(data: Iterable[float64]) -> float64:
  return _pvariance_list(_materialize_f64(data))


@overload
@immutable
def pvariance(data: Iterable[float64], mu: float64) -> float64:
  return _pvariance_at(_materialize_f64(data), mu)


@overload
@immutable
def stdev(data: Iterable[float64]) -> float64:
  return sqrt(variance(data))


@overload
@immutable
def stdev(data: Iterable[float64], xbar: float64) -> float64:
  return sqrt(variance(data, xbar))


@overload
@immutable
def pstdev(data: Iterable[float64]) -> float64:
  return sqrt(pvariance(data))


@overload
@immutable
def pstdev(data: Iterable[float64], mu: float64) -> float64:
  return sqrt(pvariance(data, mu))


# ---------------------------------------------------------------------------
# 分位数
# ---------------------------------------------------------------------------


@immutable
def quantiles(data: Iterable[float64], n: int = 4, method: str = "exclusive") -> list[float64]:
  if n < 1:
    raise StatisticsError("n must be at least 1")
  xs: list[float64] = _materialize_f64(data)
  xs.sort()
  ld: int = len(xs)
  if ld < 2:
    if ld == 1:
      single: list[float64] = []
      v: float64 = xs[0]
      for i in range(n - 1):
        single.append(v)
      return single
    raise StatisticsError("must have at least one data point")
  if method == "inclusive":
    m: int = ld - 1
    result: list[float64] = []
    for i in range(1, n):
      prod: int = i * m
      j: int = prod // n
      delta: int = prod - j * n
      interpolated: float64 = (xs[j] * (n - delta) + xs[j + 1] * delta) / (n * 1.0)
      result.append(interpolated)
    return result
  if method == "exclusive":
    m = ld + 1
    result: list[float64] = []
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
def _covariance_lists(xs: list[float64], ys: list[float64]) -> float64:
  n: int = len(xs)
  if len(ys) != n:
    raise StatisticsError("covariance requires that both inputs have same number of data points")
  if n < 2:
    raise StatisticsError("covariance requires at least two data points")
  xbar: float64 = _sum_f64(xs) / (n * 1.0)
  ybar: float64 = _sum_f64(ys) / (n * 1.0)
  sxy: float64 = 0.0
  for i in range(n):
    sxy += (xs[i] - xbar) * (ys[i] - ybar)
  return sxy / ((n - 1) * 1.0)


@immutable
def covariance(x: Iterable[float64], y: Iterable[float64]) -> float64:
  return _covariance_lists(_materialize_f64(x), _materialize_f64(y))


@immutable
def _correlation_lists(xs: list[float64], ys: list[float64], method: str) -> float64:
  n: int = len(xs)
  if len(ys) != n:
    raise StatisticsError("correlation requires that both inputs have same number of data points")
  if n < 2:
    raise StatisticsError("correlation requires at least two data points")
  if method != "linear":
    raise ValueError(f"Unknown method: {method!r}")
  xbar: float64 = _sum_f64(xs) / (n * 1.0)
  ybar: float64 = _sum_f64(ys) / (n * 1.0)
  sxy: float64 = 0.0
  sxx: float64 = 0.0
  syy: float64 = 0.0
  for i in range(n):
    dx: float64 = xs[i] - xbar
    dy: float64 = ys[i] - ybar
    sxy += dx * dy
    sxx += dx * dx
    syy += dy * dy
  denom: float64 = _sqrtprod(sxx, syy)
  if not denom:
    raise StatisticsError("at least one of the inputs is constant")
  return sxy / denom


@immutable
def correlation(x: Iterable[float64], y: Iterable[float64], method: str = "linear") -> float64:
  return _correlation_lists(_materialize_f64(x), _materialize_f64(y), method)


@dataclass
class LinearRegression:
  slope: float64
  intercept: float64


@immutable
def _linear_regression_lists(
  xs: list[float64],
  ys: list[float64],
  proportional: bool,
) -> LinearRegression:
  n: int = len(xs)
  if len(ys) != n:
    raise StatisticsError("linear regression requires that both inputs have same number of data points")
  if n < 2:
    raise StatisticsError("linear regression requires at least two data points")
  xbar: float64 = 0.0
  ybar: float64 = 0.0
  if not proportional:
    xbar = _sum_f64(xs) / (n * 1.0)
    ybar = _sum_f64(ys) / (n * 1.0)
  sxy: float64 = 0.0
  sxx: float64 = 0.0
  for i in range(n):
    dx: float64 = xs[i] - xbar
    dy: float64 = ys[i] - ybar
    sxy += dx * dy
    sxx += dx * dx
  if not sxx:
    raise StatisticsError("x is constant")
  slope: float64 = sxy / sxx
  intercept: float64 = 0.0
  if not proportional:
    intercept = ybar - slope * xbar
  return new(slope, intercept)


@immutable
def linear_regression(
  x: Iterable[float64],
  y: Iterable[float64],
  proportional: bool = False,
) -> LinearRegression:
  return _linear_regression_lists(_materialize_f64(x), _materialize_f64(y), proportional)


# ---------------------------------------------------------------------------
# 正态分布
# ---------------------------------------------------------------------------


@copyable
class NormalDist:
  """正态分布（对齐 ``statistics.NormalDist`` 核心 API）。"""

  def __init__(self, mu: float64 = 0.0, sigma: float64 = 1.0):
    if sigma < 0.0:
      raise StatisticsError("sigma must be non-negative")
    self._mu: float64 = mu
    self._sigma: float64 = sigma

  @staticmethod
  def from_samples(data: Iterable[float64]) -> Self:
    lst: list[float64] = _materialize_f64(data)
    n: int = len(lst)
    if n < 2:
      raise StatisticsError("stdev requires at least two data points")
    mu: float64 = _sum_f64(lst) / (n * 1.0)
    ss: float64 = 0.0
    for i in range(n):
      d: float64 = lst[i] - mu
      ss += d * d
    sigma: float64 = sqrt(ss / ((n - 1) * 1.0))
    return new(mu, sigma)

  @immutable
  def pdf(self, x: float64) -> float64:
    variance: float64 = self._sigma * self._sigma
    if not variance:
      raise StatisticsError("pdf() not defined when sigma is zero")
    diff: float64 = x - self._mu
    return exp(diff * diff / (-2.0 * variance)) / sqrt(tau * variance)

  @immutable
  def cdf(self, x: float64) -> float64:
    if not self._sigma:
      raise StatisticsError("cdf() not defined when sigma is zero")
    return 0.5 * erfc((self._mu - x) / (self._sigma * _SQRT2))

  @immutable
  def inv_cdf(self, p: float64) -> float64:
    if p <= 0.0 or p >= 1.0:
      raise StatisticsError("p must be in the range 0.0 < p < 1.0")
    return _normal_dist_inv_cdf(p, self._mu, self._sigma)

  @immutable
  def quantiles(self, n: int = 4) -> list[float64]:
    out: list[float64] = []
    for i in range(1, n):
      out.append(self.inv_cdf(i / (n * 1.0)))
    return out

  @immutable
  def zscore(self, x: float64) -> float64:
    if not self._sigma:
      raise StatisticsError("zscore() not defined when sigma is zero")
    return (x - self._mu) / self._sigma

  @immutable
  def overlap(self, other: Self) -> float64:
    X_mu: float64 = self._mu
    X_sigma: float64 = self._sigma
    Y_mu: float64 = other._mu
    Y_sigma: float64 = other._sigma
    if Y_sigma < X_sigma or (Y_sigma == X_sigma and Y_mu < X_mu):
      swap_mu: float64 = X_mu
      X_mu = Y_mu
      Y_mu = swap_mu
      swap_sigma: float64 = X_sigma
      X_sigma = Y_sigma
      Y_sigma = swap_sigma
    X_var: float64 = X_sigma * X_sigma
    Y_var: float64 = Y_sigma * Y_sigma
    if not X_var or not Y_var:
      raise StatisticsError("overlap() not defined when sigma is zero")
    dv: float64 = Y_var - X_var
    dm: float64 = fabs(Y_mu - X_mu)
    if not dv:
      return erfc(dm / (2.0 * X_sigma * _SQRT2))
    a: float64 = X_mu * Y_var - Y_mu * X_var
    sig_prod: float64 = X_sigma * Y_sigma
    radic: float64 = sqrt(dm * dm + dv * log(Y_var / X_var))
    b: float64 = sig_prod * radic
    x1: float64 = (a + b) / dv
    x2: float64 = (a - b) / dv
    return 1.0 - (
      fabs(_normal_cdf(Y_mu, Y_sigma, x1) - _normal_cdf(X_mu, X_sigma, x1))
      + fabs(_normal_cdf(Y_mu, Y_sigma, x2) - _normal_cdf(X_mu, X_sigma, x2))
    )

  @property
  def mean(self) -> float64:
    return self._mu

  @property
  def median(self) -> float64:
    return self._mu

  @property
  def mode(self) -> float64:
    return self._mu

  @property
  def stdev(self) -> float64:
    return self._sigma

  @property
  def variance(self) -> float64:
    return self._sigma * self._sigma

  @overload
  def __add__(self, other: Self) -> Self:
    return new(self._mu + other._mu, hypot(self._sigma, other._sigma))

  @overload
  def __add__(self, other: float64) -> Self:
    return new(self._mu + other, self._sigma)

  @overload
  def __sub__(self, other: Self) -> Self:
    return new(self._mu - other._mu, hypot(self._sigma, other._sigma))

  @overload
  def __sub__(self, other: float64) -> Self:
    return new(self._mu - other, self._sigma)

  @overload
  def __mul__(self, other: float64) -> Self:
    return new(self._mu * other, self._sigma * fabs(other))

  @immutable
  def __eq__(self, other: Self) -> bool:
    return self._mu == other._mu and self._sigma == other._sigma
