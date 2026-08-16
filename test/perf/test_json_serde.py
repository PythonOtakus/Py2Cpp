"""JSON 序列化性能：多类型/嵌套 ``@serializable`` 结构，对照 CPython 基线（见 ``scripts/compare_json_perf.py``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.serde.json import Json
from py2cpp.system.time import formatDuration, perfCounter

# 与 scripts/compare_json_perf.py 中 _SIZES 对齐
_SizeInt: int = 50000
_SizeStr: int = 20000
_SizeNested: int = 5000
_SizeTags: int = 10000
_SizeListUser: int = 2000
_SizeTicker: int = 20000

# PR-1：``loads list[int|str]`` ASCII 叶子快路径
_MaxLoadsListInt50k: float64 = 0.038
_MaxLoadsListStr20k: float64 = 0.035
# PR-2：``@serializable`` ``loads[list[Cls]]`` 有序 mega-loop 特化
_MaxLoadsListUser2k: float64 = 0.012
# PR-P1/P2：``dict[str,int|str]`` ASCII 叶子快路径（``dict._index`` 用 ``hash(key)``）
_MaxLoadsDictStrInt5k: float64 = 0.120
_MaxLoadsDictStrStr5k: float64 = 0.180
# 10k list[int]：Py2Cpp 约 5–8ms；CPython ~0.36ms（见 scripts/compare_json_perf.py）
_MaxDumpsListInt10k: float64 = 0.012


@serializable
@copyable
@dataclass
class User:
  id: int
  name: str
  active: bool = True
  tags: list[str] @optional = []


@serializable
@copyable
@dataclass
class MiniUser:
  """无 ``name``/``tags``：对比 ``User`` 的字符串与空列表分支开销。"""

  id: int
  active: bool = True


@serializable
@copyable
@dataclass
class Ticker:
  """纯 ``int`` 标量行：最能体现 SwAR + 有序 mega-loop（无 ``PyStr`` 解析）。"""

  id: int
  seq: int
  qty: int


@serializable
@copyable
@dataclass
class NestedDoc:
  """嵌套：``list[int]`` + ``dict[str, str]`` + 标量字段。"""

  id: int = 0
  counts: list[int] @optional = []
  labels: dict[str, str] @optional = {}


@serializable
@union
class EventUnion:
  @variant
  class Tick:
    seq: int
    values: list[int]

  @variant
  class Ping:
    msg: str


def _makeListInt(n: int) -> list[int]:
  xs: list[int] = []
  i: int = 0
  while i < n:
    xs.append(i)
    i += 1
  return xs


def _makeListStr(n: int) -> list[str]:
  xs: list[str] = []
  i: int = 0
  while i < n:
    xs.append("item")
    i += 1
  return xs


def _makeDictStrInt(n: int) -> dict[str, int]:
  d: dict[str, int] = {}
  i: int = 0
  while i < n:
    k: str = "k"
    k += str(i)
    d[k] = i
    i += 1
  return d


def _makeDictStrStr(n: int) -> dict[str, str]:
  d: dict[str, str] = {}
  i: int = 0
  while i < n:
    k: str = "k"
    k += str(i)
    d[k] = "v"
    i += 1
  return d


def _makeNestedDoc(n: int) -> NestedDoc:
  counts: list[int] = _makeListInt(n)
  labels: dict[str, str] = {}
  i: int = 0
  while i < n:
    key: str = "f"
    key += str(i)
    labels[key] = "v"
    i += 1
  doc: NestedDoc = new()
  doc.id = 42
  doc.counts = counts
  doc.labels = labels
  return doc


def _makeUserTags(n: int) -> User:
  tags: list[str] = []
  i: int = 0
  while i < n:
    tags.append("tag")
    i += 1
  return new(id=1, name="bench", tags=tags)


def _makeListUser(n: int) -> list[User]:
  xs: list[User] = new()
  i: int = 0
  while i < n:
    u: User = new(id=i, name="u")
    xs.append(u)
    i += 1
  return xs


def _makeListMiniUser(n: int) -> list[MiniUser]:
  xs: list[MiniUser] = new()
  i: int = 0
  while i < n:
    u: MiniUser = new(id=i, active=True)
    xs.append(u)
    i += 1
  return xs


def _makeListTicker(n: int) -> list[Ticker]:
  xs: list[Ticker] = new()
  i: int = 0
  while i < n:
    t: Ticker = new(id=i, seq=i, qty=1)
    xs.append(t)
    i += 1
  return xs


def _benchDumpsListInt(xs: list[int]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpsListStr(xs: list[str]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpsDictStrInt(d: dict[str, int]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(d)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchLoadsDictStrInt(js: str) -> float64:
  t0: float64 = perfCounter()
  d: dict[str, int] = Json.loads(js)
  elapsed: float64 = perfCounter() - t0
  return elapsed


def _benchDumpsDictStrStr(d: dict[str, str]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(d)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchLoadsDictStrStr(js: str) -> float64:
  t0: float64 = perfCounter()
  d: dict[str, str] = Json.loads(js)
  elapsed: float64 = perfCounter() - t0
  return elapsed


def _benchDumpsNested(doc: NestedDoc) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(doc)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpsUser(u: User) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(u)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpsListUser(xs: list[User]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchLoadsListUser(js: str) -> float64:
  t0: float64 = perfCounter()
  ys: list[User] = Json.loads(js)
  elapsed: float64 = perfCounter() - t0
  return elapsed


def _benchLoadsListInt(js: str) -> float64:
  t0: float64 = perfCounter()
  ys: list[int] = Json.loads(js)
  elapsed: float64 = perfCounter() - t0
  return elapsed


def _benchLoadsListStr(js: str) -> float64:
  t0: float64 = perfCounter()
  ys: list[str] = Json.loads(js)
  elapsed: float64 = perfCounter() - t0
  return elapsed


def _benchLoadsListTicker(js: str) -> float64:
  t0: float64 = perfCounter()
  ys: list[Ticker] = Json.loads(js)
  elapsed: float64 = perfCounter() - t0
  return elapsed


def _benchLoadsListMiniUser(js: str) -> float64:
  t0: float64 = perfCounter()
  ys: list[MiniUser] = Json.loads(js)
  elapsed: float64 = perfCounter() - t0
  return elapsed


def _benchDumpsEvent(ev: EventUnion) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(ev)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _printRow(label: str, n: int, elapsed: float64, outLen: int) -> None:
  mb: float64 = 0.0
  if elapsed > 0.0:
    mb = (outLen / 1048576.0) / elapsed
  print(
    f"  {label} n={n}  time={formatDuration(elapsed)}  "
    f"out={outLen} chars  ~{mb:.2f} MB/s"
  )


class JsonSerdePerfListUserTests(TestCaseMixin):
  _testTag = 295

  @override
  def test(self):
    n: int = _SizeListUser
    xs: list[User] = _makeListUser(n)
    r: (float64, int) = _benchDumpsListUser(xs)
    _printRow("dumps list[User]", n, r[0], r[1])
    js: str = Json.dumps(xs)
    tLoad: float64 = _benchLoadsListUser(js)
    _printRow("loads list[User]", n, tLoad, r[1])
    self.assertTrue(tLoad < _MaxLoadsListUser2k)
    mu: list[MiniUser] = _makeListMiniUser(n)
    jsMu: str = Json.dumps(mu)
    tMu: float64 = _benchLoadsListMiniUser(jsMu)
    _printRow("loads list[MiniUser]", n, tMu, len(jsMu))
    self.assertTrue(r[1] > n * 20)
    ys: list[User] = Json.loads(js)
    self.assertEqual(len(ys), n)
    self.assertEqual(ys[0].id, 0)
    self.assertEqual(ys[n - 1].name, "u")
    ysMu: list[MiniUser] = Json.loads(jsMu)
    self.assertEqual(len(ysMu), n)


class JsonSerdePerfListInt10kTests(TestCaseMixin):
  _testTag = 300

  @override
  def test(self):
    n: int = 10000
    xs: list[int] = _makeListInt(n)
    r: (float64, int) = _benchDumpsListInt(xs)
    _printRow("dumps list[int]", n, r[0], r[1])
    self.assertTrue(r[0] < _MaxDumpsListInt10k)
    self.assertTrue(r[1] > n)


class JsonSerdePerfListInt50kTests(TestCaseMixin):
  _testTag = 301

  @override
  def test(self):
    n: int = _SizeInt
    xs: list[int] = _makeListInt(n)
    r: (float64, int) = _benchDumpsListInt(xs)
    _printRow("dumps list[int]", n, r[0], r[1])
    js: str = Json.dumps(xs)
    tLoad: float64 = _benchLoadsListInt(js)
    _printRow("loads list[int]", n, tLoad, len(js))
    self.assertTrue(tLoad < _MaxLoadsListInt50k)
    ys: list[int] = Json.loads(js)
    self.assertEqual(len(ys), n)
    self.assertEqual(ys[0], 0)
    self.assertEqual(ys[n - 1], n - 1)


class JsonSerdePerfListStr20kTests(TestCaseMixin):
  _testTag = 302

  @override
  def test(self):
    n: int = _SizeStr
    xs: list[str] = _makeListStr(n)
    r: (float64, int) = _benchDumpsListStr(xs)
    _printRow("dumps list[str]", n, r[0], r[1])
    js: str = Json.dumps(xs)
    tLoad: float64 = _benchLoadsListStr(js)
    _printRow("loads list[str]", n, tLoad, len(js))
    self.assertTrue(tLoad < _MaxLoadsListStr20k)
    ys: list[str] = Json.loads(js)
    self.assertEqual(len(ys), n)
    self.assertEqual(ys[0], "item")
    self.assertTrue(r[1] > n * 5)


class JsonSerdePerfDictStrInt5kTests(TestCaseMixin):
  _testTag = 303

  @override
  def test(self):
    n: int = _SizeNested
    d: dict[str, int] = _makeDictStrInt(n)
    r: (float64, int) = _benchDumpsDictStrInt(d)
    _printRow("dumps dict[str,int]", n, r[0], r[1])
    js: str = Json.dumps(d)
    tLoad: float64 = _benchLoadsDictStrInt(js)
    _printRow("loads dict[str,int]", n, tLoad, len(js))
    self.assertTrue(tLoad < _MaxLoadsDictStrInt5k)
    d2: dict[str, int] = Json.loads(js)
    self.assertEqual(len(d2), n)
    self.assertEqual(d2["k0"], 0)
    self.assertTrue(r[1] > n * 4)


class JsonSerdePerfDictStrStr5kTests(TestCaseMixin):
  _testTag = 308

  @override
  def test(self):
    n: int = _SizeNested
    d: dict[str, str] = _makeDictStrStr(n)
    r: (float64, int) = _benchDumpsDictStrStr(d)
    _printRow("dumps dict[str,str]", n, r[0], r[1])
    js: str = Json.dumps(d)
    tLoad: float64 = _benchLoadsDictStrStr(js)
    _printRow("loads dict[str,str]", n, tLoad, len(js))
    self.assertTrue(tLoad < _MaxLoadsDictStrStr5k)
    d2: dict[str, str] = Json.loads(js)
    self.assertEqual(len(d2), n)
    self.assertEqual(d2["k0"], "v")
    self.assertTrue(r[1] > n * 6)


class JsonSerdePerfNestedDoc5kTests(TestCaseMixin):
  _testTag = 304

  @override
  def test(self):
    n: int = _SizeNested
    doc: NestedDoc = _makeNestedDoc(n)
    r: (float64, int) = _benchDumpsNested(doc)
    _printRow("dumps NestedDoc", n, r[0], r[1])
    doc2: NestedDoc = Json.loads(Json.dumps(doc))
    self.assertEqual(doc2.id, 42)
    self.assertEqual(len(doc2.counts), n)
    self.assertEqual(len(doc2.labels), n)


class JsonSerdePerfUserTags10kTests(TestCaseMixin):
  _testTag = 305

  @override
  def test(self):
    n: int = _SizeTags
    u: User = _makeUserTags(n)
    r: (float64, int) = _benchDumpsUser(u)
    _printRow("dumps User(tags)", n, r[0], r[1])
    u2: User = Json.loads(Json.dumps(u))
    self.assertEqual(len(u2.tags), n)


class JsonSerdePerfUnionListTests(TestCaseMixin):
  _testTag = 306

  @override
  def test(self):
    n: int = 2000
    ev: EventUnion = EventUnion.Tick(seq=9, values=_makeListInt(n))
    r: (float64, int) = _benchDumpsEvent(ev)
    _printRow("dumps EventUnion.Tick", n, r[0], r[1])
    self.assertTrue(r[1] > n)


class JsonSerdePerfListTicker20kTests(TestCaseMixin):
  """纯 ``int`` 行对象：对比 ``list[User]`` 的 ``PyStr`` 解析与物化。"""

  _testTag = 307

  @override
  def test(self):
    n: int = _SizeTicker
    xs: list[Ticker] = _makeListTicker(n)
    t0: float64 = perfCounter()
    js: str = Json.dumps(xs)
    tDump: float64 = perfCounter() - t0
    _printRow("dumps list[Ticker]", n, tDump, len(js))
    tLoad: float64 = _benchLoadsListTicker(js)
    _printRow("loads list[Ticker]", n, tLoad, len(js))
    ys: list[Ticker] = Json.loads(js)
    self.assertEqual(len(ys), n)
    self.assertEqual(ys[0].id, 0)
    self.assertEqual(ys[n - 1].qty, 1)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
