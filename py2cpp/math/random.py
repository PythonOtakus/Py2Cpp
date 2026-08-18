"""``random``：Mersenne Twister PRNG（对齐 Python 3.13 ``random`` 核心 API）。

路径：``py2cpp.math.random``（``import random`` 的 CPython 同名模块在 Py2Cpp 中请显式导入本子模块）。

参考 https://docs.python.org/3.13/library/random.html 与 ``Lib/random.py``。
算法与 CPython 3.13 ``Random``（MT19937、Version=3）一致。

**暂未实现**：``betavariate``、``expovariate``、``gammavariate``、``gauss`` / ``normalvariate``、
``lognormvariate``、``vonmisesvariate``、``paretovariate``、``weibullvariate``、``triangular``、
``SystemRandom``（依赖 ``os.urandom``）等。
"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from ..system.time import time
from ..text.bytes import bytes
from ..util.list import list


_N: int @const = 624
_M: int @const = 397
_MatrixA: int @const = 0x9908B0DF
_UpperMask: int @const = 0x80000000
_LowerMask: int @const = 0x7FFFFFFF


@copyable
class Random[Scalar: oneof[float, float64] = float]:
  """可播种的伪随机数生成器（MT19937）。"""

  Version: int @const = 3

  @immutable
  @staticmethod
  def _mask32(x: int) -> int:
    return x & 0xFFFFFFFF

  def __init__(self):
    self._index: int = _N
    self._mt: uint[:624] = new()
    for i in range(_N):
      self._mt[i] = 0
    self.seed()

  @overload
  def seed(self) -> None:
    t: Scalar = time()
    keys: list[int] = []
    keys.append(int(t * 256.0) & 0xFFFFFFFF)
    self._initByArray(keys)

  @overload
  def seed(self, a: int, version: int = 2) -> None:
    if version == 1:
      self._initGenrand(a)
      return
    if version != 2:
      raise ValueError("unsupported seed version")
    keys: list[int] = []
    keys.append(a)
    self._initByArray(keys)

  def _initGenrand(self, seed: int) -> None:
    self._mt[0] = Self._mask32(seed)
    for i in range(1, _N):
      prev: int = self._mt[i - 1]
      self._mt[i] = Self._mask32(1812433253 * (prev ^ (prev >> 30)) + i)
    self._index = _N

  def _initByArray(self, key: list[int]) -> None:
    """``version=2`` 整数种子路径（对齐 ``_randommodule`` ``init_by_array``）。"""
    self._initGenrand(19650218)
    i: int = 1
    j: int = 0
    k: int = _N
    if len(key) > k:
      k = len(key)
    for _ in range(k):
      prev: int = self._mt[i - 1]
      mix: int = Self._mask32(Self._mask32(prev ^ (prev >> 30)) * 1664525)
      self._mt[i] = Self._mask32((self._mt[i] ^ mix) + key[j] + j)
      i += 1
      j += 1
      if i >= _N:
        self._mt[0] = self._mt[_N - 1]
        i = 1
      if j >= len(key):
        j = 0
    for _ in range(_N - 1):
      prev = self._mt[i - 1]
      mix2: int = Self._mask32(Self._mask32(prev ^ (prev >> 30)) * 1566083941)
      self._mt[i] = Self._mask32((self._mt[i] ^ mix2) - i)
      i += 1
      if i >= _N:
        self._mt[0] = self._mt[_N - 1]
        i = 1
    self._mt[0] = 0x80000000
    self._index = _N

  def _twist(self) -> None:
    for i in range(_N - _M):
      y: int = (self._mt[i] & _UpperMask) | (self._mt[i + 1] & _LowerMask)
      self._mt[i] = Self._mask32(self._mt[i + _M] ^ (y >> 1))
      if y & 1:
        self._mt[i] = Self._mask32(self._mt[i] ^ _MatrixA)
    for i in range(_N - _M, _N - 1):
      y = (self._mt[i] & _UpperMask) | (self._mt[i + 1] & _LowerMask)
      self._mt[i] = Self._mask32(self._mt[i + _M - _N] ^ (y >> 1))
      if y & 1:
        self._mt[i] = Self._mask32(self._mt[i] ^ _MatrixA)
    y = (self._mt[_N - 1] & _UpperMask) | (self._mt[0] & _LowerMask)
    self._mt[_N - 1] = Self._mask32(self._mt[_M - 1] ^ (y >> 1))
    if y & 1:
      self._mt[_N - 1] = Self._mask32(self._mt[_N - 1] ^ _MatrixA)
    self._index = 0

  def _genrandInt32(self) -> int:
    if self._index >= _N:
      self._twist()
    raw: int = self._mt[self._index]
    self._index += 1
    y: int = Self._mask32(raw ^ (raw >> 11))
    y = Self._mask32(y ^ ((y << 7) & 0x9D2C5680))
    y = Self._mask32(y ^ ((y << 15) & 0xEFC60000))
    y = Self._mask32(y ^ (y >> 18))
    return y

  def getRandBits(self, k: int) -> uint:
    if k < 0:
      raise ValueError("number of bits must be non-negative")
    if k == 0:
      return 0
    if k <= 32:
      r: int = self._genrandInt32()
      return r >> (32 - k)
    numBytes: int = (k + 7) // 8
    acc: int = 0
    for i in range(numBytes):
      acc = (acc << 8) | (self._genrandInt32() & 0xFF)
    shift: int = numBytes * 8 - k
    return acc >> shift

  def _randbelow(self, n: int) -> int:
    if n <= 0:
      raise ValueError("n must be positive")
    k: int = 0
    t: int = n - 1
    while t > 0:
      t >>= 1
      k += 1
    r: int = self.getRandBits(k)
    while r >= n:
      r = self.getRandBits(k)
    return r

  def random(self) -> Scalar:
    a: int = self._genrandInt32() >> 5
    b: int = self._genrandInt32() >> 6
    num: Scalar = a
    num = num * 67108864.0 + b
    den: Scalar = 9007199254740992.0
    return num / den

  def uniform(self, a: Scalar, b: Scalar) -> Scalar:
    return a + (b - a) * self.random()

  @overload
  def randRange(self, stop: int) -> int:
    return self.randRange(0, stop, 1)

  @overload
  def randRange(self, start: int, stop: int, step: int = 1) -> int:
    if step == 0:
      raise ValueError("zero step for randRange()")
    width: int = stop - start
    n: int = 0
    if step > 0:
      if width <= 0:
        raise ValueError("empty range for randRange()")
      n = (width + step - 1) // step
    else:
      if width >= 0:
        raise ValueError("empty range for randRange()")
      n = (width + step + 1) // step
    return start + self._randbelow(n) * step

  def randInt(self, a: int, b: int) -> int:
    return self.randRange(a, b + 1)

  def randBytes(self, n: int) -> bytes:
    if n < 0:
      raise ValueError("negative argument not allowed")
    out: byte[:] = new(n)
    for i in range(n):
      out[i] = byte(self._genrandInt32() & 0xFF)
    return bytes(out)

  def choice[T](self, seq: list[T]) -> T:
    if not seq:
      raise IndexError("cannot choose from an empty sequence")
    return seq[self._randbelow(len(seq))]

  def shuffle[T](self, x: list[T] @ref) -> None:
    n: int = len(x)
    if n < 2:
      return
    for i in range(n - 1, 0, -1):
      j: int = self._randbelow(i + 1)
      x[i], x[j] = x[j], x[i]

  def shuffleWith[T](self, x: list[T] @ref, randomFn: Function[[], Scalar]) -> None:
    n: int = len(x)
    if n < 2:
      return
    for i in range(n - 1, 0, -1):
      j = int(randomFn() * (i + 1))
      if j > i:
        j = i
      x[i], x[j] = x[j], x[i]

  def sample[T](self, population: list[T], k: int) -> list[T]:
    n: int = len(population)
    if k < 0 or k > n:
      raise ValueError("sample larger than population or negative")
    result: list[T] = []
    pool: list[T] = []
    for i in range(n):
      pool.append(population[i])
    for i in range(k):
      j: int = self._randbelow(n - i)
      result.append(pool[j])
      pool[j] = pool[n - i - 1]
    return result

  def choices[T](self, population: list[T], k: int = 1) -> list[T]:
    out: list[T] = []
    for _ in range(k):
      out.append(self.choice(population))
    return out

  def choicesWeighted[T](self, population: list[T], weights: list[Scalar], k: int = 1) -> list[T]:
    n: int = len(population)
    if n == 0:
      raise IndexError("cannot choose from an empty population")
    if len(weights) != n:
      raise ValueError("the number of weights does not match the population")
    total: Scalar = 0.0
    for i in range(n):
      w: Scalar = weights[i]
      if w < 0.0:
        raise ValueError("negative weight")
      total += w
    if total <= 0.0:
      raise ValueError("total of weights must be positive")
    out2: list[T] = []
    for _ in range(k):
      pick: Scalar = self.random() * total
      acc: Scalar = 0.0
      for i in range(n):
        acc += weights[i]
        if pick < acc:
          out2.append(population[i])
          break
    return out2

  def getState(self) -> (int, list[int]):
    internal: list[int] = []
    for i in range(_N):
      internal.append(self._mt[i])
    internal.append(self._index)
    return (Self.Version, internal)

  def setState(self, state: (int, list[int])) -> None:
    version: int = state[0]
    internal: list[int] = state[1]
    if version != Self.Version:
      raise ValueError("state version mismatch")
    if len(internal) != _N + 1:
      raise ValueError("state is invalid")
    for i in range(_N):
      self._mt[i] = Self._mask32(internal[i])
    self._index = internal[_N]


_rng: Random = new()


@overload
def seed() -> None:
  _rng.seed()


@overload
def seed(a: int, version: int = 2) -> None:
  _rng.seed(a, version)


def getState() -> (int, list[int]):
  return _rng.getState()


def setState(state: (int, list[int])) -> None:
  _rng.setState(state)


def random() -> float64:
  return _rng.random()


def uniform(a: float64, b: float64) -> float64:
  return _rng.uniform(a, b)


@overload
def randRange(stop: int) -> int:
  return _rng.randRange(stop)


@overload
def randRange(start: int, stop: int, step: int = 1) -> int:
  return _rng.randRange(start, stop, step)


def randInt(a: int, b: int) -> int:
  return _rng.randInt(a, b)


def getRandBits(k: int) -> uint:
  return _rng.getRandBits(k)


def randBytes(n: int) -> bytes:
  return _rng.randBytes(n)


def choice[T](seq: list[T]) -> T:
  return _rng.choice(seq)


def shuffle[T](x: list[T] @ref) -> None:
  _rng.shuffle(x)


def sample[T](population: list[T], k: int) -> list[T]:
  return _rng.sample(population, k)


def choices[T](population: list[T], k: int = 1) -> list[T]:
  return _rng.choices(population, k)


def choicesWeighted[T](population: list[T], weights: list[float64], k: int = 1) -> list[T]:
  return _rng.choicesWeighted(population, weights, k)
