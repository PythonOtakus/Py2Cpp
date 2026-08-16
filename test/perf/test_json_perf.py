"""``dumps`` / ``loads`` 大数据量性能（wall-clock，stdout 打印耗时与输出规模）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.serde.json import Json, JsonEncoder
from py2cpp.system.time import formatDuration, perfCounter


@serializable
@copyable
@dataclass
class User:
  id: int
  name: str
  active: bool = True
  tags: list[str] @optional = []


def _printRow(label: str, n: int, elapsed: float64, outLen: int) -> None:
  mb: float64 = 0.0
  if elapsed > 0.0:
    mb = (outLen / 1048576.0) / elapsed
  print(
    f"  {label} n={n}  time={formatDuration(elapsed)}  out={outLen} chars  ~{mb:.2f} MB/s"
  )


class JsonPerfListInt10kTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    n: int = 10000
    xs: list[int] = []
    i: int = 0
    while i < n:
      xs.append(i)
      i += 1
    t0: float64 = perfCounter()
    js: str = Json.dumps(xs)
    elapsed: float64 = perfCounter() - t0
    outLen: int = len(js)
    _printRow("dumps list[int]", n, elapsed, outLen)
    self.assertTrue(outLen > n)
    self.assertEqual(xs[0] + xs[n - 1], n - 1)


class JsonPerfListInt5kTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    n: int = 5000
    xs: list[int] = []
    i: int = 0
    while i < n:
      xs.append(i)
      i += 1
    t0: float64 = perfCounter()
    jsDump: str = Json.dumps(xs)
    tDump: float64 = perfCounter() - t0
    enc: JsonEncoder = JsonEncoder()
    t1: float64 = perfCounter()
    enc.dumpListInt(xs)
    jsEnc: str = enc.finish()
    tEnc: float64 = perfCounter() - t1
    t2: float64 = perfCounter()
    ys: list[int] = Json.loads(jsDump)
    tLoad: float64 = perfCounter() - t2
    _printRow("dumps list[int]", n, tDump, len(jsDump))
    _printRow("encoder dumpListInt", n, tEnc, len(jsEnc))
    _printRow("loads list[int]", n, tLoad, len(jsDump))
    self.assertEqual(len(jsDump), len(jsEnc))
    self.assertEqual(ys[0] + ys[n - 1], n - 1)


class JsonPerfListStr50kTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    n: int = 50000
    xs: list[str] = []
    i: int = 0
    while i < n:
      xs.append("item")
      i += 1
    t0: float64 = perfCounter()
    js: str = Json.dumps(xs)
    elapsed: float64 = perfCounter() - t0
    outLen: int = len(js)
    _printRow("dumps list[str]", n, elapsed, outLen)
    self.assertTrue(outLen > n * 4)


class JsonPerfUserTags10kTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    n: int = 10000
    tags: list[str] = []
    i: int = 0
    while i < n:
      tags.append("tag")
      i += 1
    u: User = new(id=1, name="bench", tags=tags)
    t0: float64 = perfCounter()
    js: str = Json.dumps(u)
    elapsed: float64 = perfCounter() - t0
    _printRow("dumps User (tags)", n, elapsed, len(js))
    self.assertEqual(len(u.tags), n)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
