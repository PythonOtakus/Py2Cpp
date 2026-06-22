"""``dumps`` / ``loads`` 大数据量性能（wall-clock，stdout 打印耗时与输出规模）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.serde.json import Json, JsonEncoder
from py2cpp.system.time import format_duration, perf_counter


@serializable
@copyable
@dataclass
class User:
  id: int
  name: str
  active: bool = True
  tags: list[str] @optional = []


def _print_row(label: str, n: int, elapsed: float64, out_len: int) -> None:
  mb: float64 = 0.0
  if elapsed > 0.0:
    mb = (out_len / 1048576.0) / elapsed
  print(
    f"  {label} n={n}  time={format_duration(elapsed)}  out={out_len} chars  ~{mb:.2f} MB/s"
  )


class JsonPerfListInt10kTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    n: int = 10000
    xs: list[int] = []
    i: int = 0
    while i < n:
      xs.append(i)
      i += 1
    t0: float64 = perf_counter()
    js: str = Json.dumps(xs)
    elapsed: float64 = perf_counter() - t0
    out_len: int = len(js)
    _print_row("dumps list[int]", n, elapsed, out_len)
    self.assertTrue(out_len > n)
    self.assertEqual(xs[0] + xs[n - 1], n - 1)


class JsonPerfListInt5kTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    n: int = 5000
    xs: list[int] = []
    i: int = 0
    while i < n:
      xs.append(i)
      i += 1
    t0: float64 = perf_counter()
    js_dump: str = Json.dumps(xs)
    t_dump: float64 = perf_counter() - t0
    enc: JsonEncoder = JsonEncoder()
    t1: float64 = perf_counter()
    enc.dump_list_int(xs)
    js_enc: str = enc.finish()
    t_enc: float64 = perf_counter() - t1
    t2: float64 = perf_counter()
    ys: list[int] = Json.loads(js_dump)
    t_load: float64 = perf_counter() - t2
    _print_row("dumps list[int]", n, t_dump, len(js_dump))
    _print_row("encoder dump_list_int", n, t_enc, len(js_enc))
    _print_row("loads list[int]", n, t_load, len(js_dump))
    self.assertEqual(len(js_dump), len(js_enc))
    self.assertEqual(ys[0] + ys[n - 1], n - 1)


class JsonPerfListStr50kTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    n: int = 50000
    xs: list[str] = []
    i: int = 0
    while i < n:
      xs.append("item")
      i += 1
    t0: float64 = perf_counter()
    js: str = Json.dumps(xs)
    elapsed: float64 = perf_counter() - t0
    out_len: int = len(js)
    _print_row("dumps list[str]", n, elapsed, out_len)
    self.assertTrue(out_len > n * 4)


class JsonPerfUserTags10kTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    n: int = 10000
    tags: list[str] = []
    i: int = 0
    while i < n:
      tags.append("tag")
      i += 1
    u: User = new(id=1, name="bench", tags=tags)
    t0: float64 = perf_counter()
    js: str = Json.dumps(u)
    elapsed: float64 = perf_counter() - t0
    _print_row("dumps User (tags)", n, elapsed, len(js))
    self.assertEqual(len(u.tags), n)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
