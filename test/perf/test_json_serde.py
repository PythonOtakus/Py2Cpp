"""JSON 序列化性能：多类型/嵌套 ``@serializable`` 结构，对照 CPython 基线（见 ``scripts/compare_json_perf.py``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.serde.json import Json
from py2cpp.system.time import format_duration, perf_counter

# 与 scripts/compare_json_perf.py 中 _SIZES 对齐
_SIZE_INT: int = 50000
_SIZE_STR: int = 20000
_SIZE_NESTED: int = 5000
_SIZE_TAGS: int = 10000
_SIZE_LIST_USER: int = 2000
_SIZE_TICKER: int = 20000

# PR-1：``loads list[int|str]`` ASCII 叶子快路径
_MAX_LOADS_LIST_INT_50K: float64 = 0.038
_MAX_LOADS_LIST_STR_20K: float64 = 0.035
# PR-2：``@serializable`` ``loads[list[Cls]]`` 有序 mega-loop 特化
_MAX_LOADS_LIST_USER_2K: float64 = 0.012
# PR-P1/P2：``dict[str,int|str]`` ASCII 叶子快路径（``dict._index`` 用 ``hash(key)``）
_MAX_LOADS_DICT_STR_INT_5K: float64 = 0.120
_MAX_LOADS_DICT_STR_STR_5K: float64 = 0.180
# 10k list[int]：Py2Cpp 约 5–8ms；CPython ~0.36ms（见 scripts/compare_json_perf.py）
_MAX_DUMPS_LIST_INT_10K: float64 = 0.012


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
class Event:
  @variant
  class Tick:
    seq: int
    values: list[int]

  @variant
  class Ping:
    msg: str


def _make_list_int(n: int) -> list[int]:
  xs: list[int] = []
  i: int = 0
  while i < n:
    xs.append(i)
    i += 1
  return xs


def _make_list_str(n: int) -> list[str]:
  xs: list[str] = []
  i: int = 0
  while i < n:
    xs.append("item")
    i += 1
  return xs


def _make_dict_str_int(n: int) -> dict[str, int]:
  d: dict[str, int] = {}
  i: int = 0
  while i < n:
    k: str = "k"
    k += str(i)
    d[k] = i
    i += 1
  return d


def _make_dict_str_str(n: int) -> dict[str, str]:
  d: dict[str, str] = {}
  i: int = 0
  while i < n:
    k: str = "k"
    k += str(i)
    d[k] = "v"
    i += 1
  return d


def _make_nested_doc(n: int) -> NestedDoc:
  counts: list[int] = _make_list_int(n)
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


def _make_user_tags(n: int) -> User:
  tags: list[str] = []
  i: int = 0
  while i < n:
    tags.append("tag")
    i += 1
  return new(id=1, name="bench", tags=tags)


def _make_list_user(n: int) -> list[User]:
  xs: list[User] = new()
  i: int = 0
  while i < n:
    u: User = new(id=i, name="u")
    xs.append(u)
    i += 1
  return xs


def _make_list_mini_user(n: int) -> list[MiniUser]:
  xs: list[MiniUser] = new()
  i: int = 0
  while i < n:
    u: MiniUser = new(id=i, active=True)
    xs.append(u)
    i += 1
  return xs


def _make_list_ticker(n: int) -> list[Ticker]:
  xs: list[Ticker] = new()
  i: int = 0
  while i < n:
    t: Ticker = new(id=i, seq=i, qty=1)
    xs.append(t)
    i += 1
  return xs


def _bench_dumps_list_int(xs: list[int]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dumps_list_str(xs: list[str]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dumps_dict_str_int(d: dict[str, int]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(d)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_loads_dict_str_int(js: str) -> float64:
  t0: float64 = perf_counter()
  d: dict[str, int] = Json.loads(js)
  elapsed: float64 = perf_counter() - t0
  return elapsed


def _bench_dumps_dict_str_str(d: dict[str, str]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(d)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_loads_dict_str_str(js: str) -> float64:
  t0: float64 = perf_counter()
  d: dict[str, str] = Json.loads(js)
  elapsed: float64 = perf_counter() - t0
  return elapsed


def _bench_dumps_nested(doc: NestedDoc) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(doc)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dumps_user(u: User) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(u)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dumps_list_user(xs: list[User]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_loads_list_user(js: str) -> float64:
  t0: float64 = perf_counter()
  ys: list[User] = Json.loads(js)
  elapsed: float64 = perf_counter() - t0
  return elapsed


def _bench_loads_list_int(js: str) -> float64:
  t0: float64 = perf_counter()
  ys: list[int] = Json.loads(js)
  elapsed: float64 = perf_counter() - t0
  return elapsed


def _bench_loads_list_str(js: str) -> float64:
  t0: float64 = perf_counter()
  ys: list[str] = Json.loads(js)
  elapsed: float64 = perf_counter() - t0
  return elapsed


def _bench_loads_list_ticker(js: str) -> float64:
  t0: float64 = perf_counter()
  ys: list[Ticker] = Json.loads(js)
  elapsed: float64 = perf_counter() - t0
  return elapsed


def _bench_loads_list_mini_user(js: str) -> float64:
  t0: float64 = perf_counter()
  ys: list[MiniUser] = Json.loads(js)
  elapsed: float64 = perf_counter() - t0
  return elapsed


def _bench_dumps_event(ev: Event) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(ev)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _print_row(label: str, n: int, elapsed: float64, out_len: int) -> None:
  mb: float64 = 0.0
  if elapsed > 0.0:
    mb = (out_len / 1048576.0) / elapsed
  print(
    f"  {label} n={n}  time={format_duration(elapsed)}  "
    f"out={out_len} chars  ~{mb:.2f} MB/s"
  )


class JsonSerdePerfListUserTests(TestCaseMixin):
  _test_tag = 295

  @override
  def test(self):
    n: int = _SIZE_LIST_USER
    xs: list[User] = _make_list_user(n)
    r: (float64, int) = _bench_dumps_list_user(xs)
    _print_row("dumps list[User]", n, r[0], r[1])
    js: str = Json.dumps(xs)
    t_load: float64 = _bench_loads_list_user(js)
    _print_row("loads list[User]", n, t_load, r[1])
    self.assertTrue(t_load < _MAX_LOADS_LIST_USER_2K)
    mu: list[MiniUser] = _make_list_mini_user(n)
    js_mu: str = Json.dumps(mu)
    t_mu: float64 = _bench_loads_list_mini_user(js_mu)
    _print_row("loads list[MiniUser]", n, t_mu, len(js_mu))
    self.assertTrue(r[1] > n * 20)
    ys: list[User] = Json.loads(js)
    self.assertEqual(len(ys), n)
    self.assertEqual(ys[0].id, 0)
    self.assertEqual(ys[n - 1].name, "u")
    ys_mu: list[MiniUser] = Json.loads(js_mu)
    self.assertEqual(len(ys_mu), n)


class JsonSerdePerfListInt10kTests(TestCaseMixin):
  _test_tag = 300

  @override
  def test(self):
    n: int = 10000
    xs: list[int] = _make_list_int(n)
    r: (float64, int) = _bench_dumps_list_int(xs)
    _print_row("dumps list[int]", n, r[0], r[1])
    self.assertTrue(r[0] < _MAX_DUMPS_LIST_INT_10K)
    self.assertTrue(r[1] > n)


class JsonSerdePerfListInt50kTests(TestCaseMixin):
  _test_tag = 301

  @override
  def test(self):
    n: int = _SIZE_INT
    xs: list[int] = _make_list_int(n)
    r: (float64, int) = _bench_dumps_list_int(xs)
    _print_row("dumps list[int]", n, r[0], r[1])
    js: str = Json.dumps(xs)
    t_load: float64 = _bench_loads_list_int(js)
    _print_row("loads list[int]", n, t_load, len(js))
    self.assertTrue(t_load < _MAX_LOADS_LIST_INT_50K)
    ys: list[int] = Json.loads(js)
    self.assertEqual(len(ys), n)
    self.assertEqual(ys[0], 0)
    self.assertEqual(ys[n - 1], n - 1)


class JsonSerdePerfListStr20kTests(TestCaseMixin):
  _test_tag = 302

  @override
  def test(self):
    n: int = _SIZE_STR
    xs: list[str] = _make_list_str(n)
    r: (float64, int) = _bench_dumps_list_str(xs)
    _print_row("dumps list[str]", n, r[0], r[1])
    js: str = Json.dumps(xs)
    t_load: float64 = _bench_loads_list_str(js)
    _print_row("loads list[str]", n, t_load, len(js))
    self.assertTrue(t_load < _MAX_LOADS_LIST_STR_20K)
    ys: list[str] = Json.loads(js)
    self.assertEqual(len(ys), n)
    self.assertEqual(ys[0], "item")
    self.assertTrue(r[1] > n * 5)


class JsonSerdePerfDictStrInt5kTests(TestCaseMixin):
  _test_tag = 303

  @override
  def test(self):
    n: int = _SIZE_NESTED
    d: dict[str, int] = _make_dict_str_int(n)
    r: (float64, int) = _bench_dumps_dict_str_int(d)
    _print_row("dumps dict[str,int]", n, r[0], r[1])
    js: str = Json.dumps(d)
    t_load: float64 = _bench_loads_dict_str_int(js)
    _print_row("loads dict[str,int]", n, t_load, len(js))
    self.assertTrue(t_load < _MAX_LOADS_DICT_STR_INT_5K)
    d2: dict[str, int] = Json.loads(js)
    self.assertEqual(len(d2), n)
    self.assertEqual(d2["k0"], 0)
    self.assertTrue(r[1] > n * 4)


class JsonSerdePerfDictStrStr5kTests(TestCaseMixin):
  _test_tag = 308

  @override
  def test(self):
    n: int = _SIZE_NESTED
    d: dict[str, str] = _make_dict_str_str(n)
    r: (float64, int) = _bench_dumps_dict_str_str(d)
    _print_row("dumps dict[str,str]", n, r[0], r[1])
    js: str = Json.dumps(d)
    t_load: float64 = _bench_loads_dict_str_str(js)
    _print_row("loads dict[str,str]", n, t_load, len(js))
    self.assertTrue(t_load < _MAX_LOADS_DICT_STR_STR_5K)
    d2: dict[str, str] = Json.loads(js)
    self.assertEqual(len(d2), n)
    self.assertEqual(d2["k0"], "v")
    self.assertTrue(r[1] > n * 6)


class JsonSerdePerfNestedDoc5kTests(TestCaseMixin):
  _test_tag = 304

  @override
  def test(self):
    n: int = _SIZE_NESTED
    doc: NestedDoc = _make_nested_doc(n)
    r: (float64, int) = _bench_dumps_nested(doc)
    _print_row("dumps NestedDoc", n, r[0], r[1])
    doc2: NestedDoc = Json.loads(Json.dumps(doc))
    self.assertEqual(doc2.id, 42)
    self.assertEqual(len(doc2.counts), n)
    self.assertEqual(len(doc2.labels), n)


class JsonSerdePerfUserTags10kTests(TestCaseMixin):
  _test_tag = 305

  @override
  def test(self):
    n: int = _SIZE_TAGS
    u: User = _make_user_tags(n)
    r: (float64, int) = _bench_dumps_user(u)
    _print_row("dumps User(tags)", n, r[0], r[1])
    u2: User = Json.loads(Json.dumps(u))
    self.assertEqual(len(u2.tags), n)


class JsonSerdePerfUnionListTests(TestCaseMixin):
  _test_tag = 306

  @override
  def test(self):
    n: int = 2000
    ev: Event = Event.Tick(seq=9, values=_make_list_int(n))
    r: (float64, int) = _bench_dumps_event(ev)
    _print_row("dumps Event.Tick", n, r[0], r[1])
    self.assertTrue(r[1] > n)


class JsonSerdePerfListTicker20kTests(TestCaseMixin):
  """纯 ``int`` 行对象：对比 ``list[User]`` 的 ``PyStr`` 解析与物化。"""

  _test_tag = 307

  @override
  def test(self):
    n: int = _SIZE_TICKER
    xs: list[Ticker] = _make_list_ticker(n)
    t0: float64 = perf_counter()
    js: str = Json.dumps(xs)
    t_dump: float64 = perf_counter() - t0
    _print_row("dumps list[Ticker]", n, t_dump, len(js))
    t_load: float64 = _bench_loads_list_ticker(js)
    _print_row("loads list[Ticker]", n, t_load, len(js))
    ys: list[Ticker] = Json.loads(js)
    self.assertEqual(len(ys), n)
    self.assertEqual(ys[0].id, 0)
    self.assertEqual(ys[n - 1].qty, 1)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
