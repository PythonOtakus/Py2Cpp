"""``Pool[T]`` 功能与 ``alloc``/``free`` 微基准（``py2cpp/util/pool.py``）。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.system.time import perfCounter


class PoolIntBox:
  def __init__(self, value: int = 0):
    self.value: int = value


class PoolBasicTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    p: Pool[PoolIntBox] = new(2)
    self.assertEqual(len(p), 0)
    self.assertEqual(p.capacity, 0)
    p.capacity = 4
    self.assertEqual(p.capacity, 4)
    self.assertEqual(len(p), 0)
    a: Pointer[PoolIntBox] = p.acquire()
    b: Pointer[PoolIntBox] = p.acquire()
    self.assertEqual(len(p), 2)
    init(a, PoolIntBox(10))
    init(b, PoolIntBox(20))
    self.assertEqual(a.value, 10)
    self.assertEqual(b.value, 20)
    p.release(a)
    self.assertEqual(len(p), 1)
    c: Pointer[PoolIntBox] = p.acquire()
    init(c, PoolIntBox(30))
    self.assertEqual(c.value, 30)
    p.clear()
    self.assertEqual(len(p), 0)
    self.assertEqual(p.capacity, 0)


class PoolReuseTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    p: Pool[PoolIntBox] = new(4)
    for i in range(8):
      q: Pointer[PoolIntBox] = p.acquire()
      init(q, PoolIntBox(i))
      p.release(q)
    self.assertEqual(len(p), 0)
    self.assertEqual(p.capacity, 4)
    p.capacity = 8
    self.assertEqual(p.capacity, 8)


class PoolGrowLiveTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    p: Pool[PoolIntBox] = new(2)
    p.capacity = 2
    a: Pointer[PoolIntBox] = p.acquire()
    b: Pointer[PoolIntBox] = p.acquire()
    init(a, PoolIntBox(1))
    init(b, PoolIntBox(2))
    c: Pointer[PoolIntBox] = p.acquire()
    init(c, PoolIntBox(3))
    self.assertEqual(len(p), 3)
    self.assertEqual(p.capacity, 4)
    self.assertEqual(a.value, 1)
    p.release(b)
    p.release(c)
    p.release(a)
    self.assertEqual(len(p), 0)


class PoolNestedListLiteralTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    rows: list[list[int]] = [[0, 1], []]
    self.assertEqual(len(rows), 2)
    self.assertEqual(len(rows[0]), 2)
    self.assertEqual(len(rows[1]), 0)
    rows[1] = [2, 3, 4]
    self.assertEqual(len(rows[1]), 3)



def _benchAllocFreeWall(n: int) -> (float64, int):
  """整段 wall-clock：先 n 次 alloc+init，再 n 次 destroy+free。"""
  slots: list[Pointer[PoolIntBox]] = []
  acc: int = 0
  t0: float64 = perfCounter()
  for i in range(n):
    p: Pointer[PoolIntBox] = alloc[PoolIntBox]()
    init(p, PoolIntBox(i))
    acc += p.value
    slots.append(p)
  for j in range(len(slots)):
    q: Pointer[PoolIntBox] = slots[j]
    destroy(q)
    free(q)
  total: float64 = perfCounter() - t0
  return (total, acc)


def _benchPoolPingPongWall(n: int) -> (float64, int):
  """整段 wall-clock：单槽 ping-pong acquire/release（旧累加计时口径）。"""
  pl: Pool[PoolIntBox] = new()
  acc: int = 0
  t0: float64 = perfCounter()
  cur: Pointer[PoolIntBox] = pl.acquire()
  init(cur, PoolIntBox(0))
  for i in range(n):
    nxt: Pointer[PoolIntBox] = pl.acquire()
    init(nxt, PoolIntBox(i))
    acc += nxt.value + cur.value
    pl.release(cur)
    cur = nxt
  acc += cur.value
  pl.release(cur)
  pl.clear()
  total: float64 = perfCounter() - t0
  return (total, acc)


def _benchPoolBatchWall(n: int) -> (float64, int):
  """整段 wall-clock：n 次 acquire+init，再 n 次 release（与 alloc 两阶段对称）。

  同时存活槽数受 ``Pool._SlotCap`` 限制，按块分批以免撑爆栈式空闲表。
  """
  pl: Pool[PoolIntBox] = new()
  acc: int = 0
  t0: float64 = perfCounter()
  for base in range(0, n, Pool._SlotCap):
    chunk: int = n - base
    if chunk > Pool._SlotCap:
      chunk = Pool._SlotCap
    slots: list[Pointer[PoolIntBox]] = []
    for i in range(chunk):
      p: Pointer[PoolIntBox] = pl.acquire()
      gi: int = base + i
      init(p, PoolIntBox(gi))
      acc += p.value
      slots.append(p)
    for j in range(len(slots)):
      pl.release(slots[j])
  pl.clear()
  total: float64 = perfCounter() - t0
  return (total, acc)


def _expectedSum(n: int) -> int:
  if n <= 0:
    return 0
  return (n - 1) * n // 2


def _printAllocVsPool(
  n: int,
  tAlloc: float64,
  tPoolBatch: float64,
  tPoolPing: float64,
) -> None:
  ratioBatch: float64 = 0.0
  ratioPing: float64 = 0.0
  if tPoolBatch > 0.0:
    ratioBatch = tAlloc / tPoolBatch
  if tPoolPing > 0.0:
    ratioPing = tAlloc / tPoolPing
  print(
    f"  n={n}  alloc/free={tAlloc:.6f}s  "
    f"pool_batch={tPoolBatch:.6f}s (alloc/batch={ratioBatch:.2f}x)  "
    f"pool_ping={tPoolPing:.6f}s (alloc/ping={ratioPing:.2f}x)  "
    f"block_cap={Pool._BlockCap}"
  )


class PoolPerf1kTests(TestCaseMixin):
  _testTag = 100

  @override
  def test(self):
    n: int = 1000
    exp: int = _expectedSum(n)
    rAlloc: (float64, int) = _benchAllocFreeWall(n)
    rBatch: (float64, int) = _benchPoolBatchWall(n)
    rPing: (float64, int) = _benchPoolPingPongWall(n)
    _printAllocVsPool(n, rAlloc[0], rBatch[0], rPing[0])
    self.assertEqual(rAlloc[1], exp)
    self.assertEqual(rBatch[1], exp)
    self.assertTrue(rPing[1] >= exp)
    self.assertTrue(rAlloc[0] >= 0.0)
    self.assertTrue(rBatch[0] >= 0.0)
    self.assertTrue(rPing[0] >= 0.0)


class PoolPerf10kTests(TestCaseMixin):
  _testTag = 101

  @override
  def test(self):
    n: int = 10000
    exp: int = _expectedSum(n)
    rAlloc: (float64, int) = _benchAllocFreeWall(n)
    rBatch: (float64, int) = _benchPoolBatchWall(n)
    rPing: (float64, int) = _benchPoolPingPongWall(n)
    _printAllocVsPool(n, rAlloc[0], rBatch[0], rPing[0])
    self.assertEqual(rAlloc[1], exp)
    self.assertEqual(rBatch[1], exp)
    self.assertTrue(rPing[1] >= exp)
    self.assertTrue(rAlloc[0] >= 0.0)
    self.assertTrue(rBatch[0] >= 0.0)
    self.assertTrue(rPing[0] >= 0.0)


class PoolPerf100kTests(TestCaseMixin):
  _testTag = 102

  @override
  def test(self):
    n: int = 100000
    exp: int = _expectedSum(n)
    rAlloc: (float64, int) = _benchAllocFreeWall(n)
    rBatch: (float64, int) = _benchPoolBatchWall(n)
    rPing: (float64, int) = _benchPoolPingPongWall(n)
    _printAllocVsPool(n, rAlloc[0], rBatch[0], rPing[0])
    self.assertEqual(rAlloc[1], exp)
    self.assertEqual(rBatch[1], exp)
    self.assertTrue(rPing[1] >= exp)
    self.assertTrue(rAlloc[0] >= 0.0)
    self.assertTrue(rBatch[0] >= 0.0)
    self.assertTrue(rPing[0] >= 0.0)


class PoolPerfAllocWall100kTests(TestCaseMixin):
  _testTag = 103

  @override
  def test(self):
    n: int = 100000
    r: (float64, int) = _benchAllocFreeWall(n)
    print(f"  [wall] alloc/free n={n}  {r[0]:.6f}s")
    self.assertEqual(r[1], _expectedSum(n))


class PoolPerfPoolBatchWall100kTests(TestCaseMixin):
  _testTag = 104

  @override
  def test(self):
    n: int = 100000
    r: (float64, int) = _benchPoolBatchWall(n)
    print(f"  [wall] pool batch n={n}  {r[0]:.6f}s")
    self.assertEqual(r[1], _expectedSum(n))


class PoolPerfPoolPingWall100kTests(TestCaseMixin):
  _testTag = 105

  @override
  def test(self):
    n: int = 100000
    r: (float64, int) = _benchPoolPingPongWall(n)
    print(f"  [wall] pool ping-pong n={n}  {r[0]:.6f}s")
    self.assertTrue(r[1] >= _expectedSum(n))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
