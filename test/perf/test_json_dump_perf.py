"""``Json.dumps`` vs ``Json.dump``（``StringIO`` sink）性能对照。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io import StringIO
from py2cpp.serde.json import Json
from py2cpp.system.time import format_duration, perf_counter

_SIZE_INT: int = 50000
_SIZE_STR: int = 20000
_SIZE_DICT: int = 5000
_SIZE_TAGS: int = 10000
_SIZE_LIST_USER: int = 2000


@serializable
@copyable
@dataclass
class User:
  id: int
  name: str
  active: bool = True
  tags: list[str] @optional = []


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


def _bench_dumps_list_int(xs: list[int]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dump_list_int(xs: list[int]) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perf_counter()
  Json.dump(xs, fp)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(fp.take()))


def _bench_dumps_list_str(xs: list[str]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dump_list_str(xs: list[str]) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perf_counter()
  Json.dump(xs, fp)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(fp.take()))


def _bench_dumps_dict_str_int(d: dict[str, int]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(d)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dump_dict_str_int(d: dict[str, int]) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perf_counter()
  Json.dump(d, fp)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(fp.take()))


def _bench_dumps_user(u: User) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(u)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dump_user(u: User) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perf_counter()
  Json.dump(u, fp)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(fp.take()))


def _bench_dumps_list_user(xs: list[User]) -> (float64, int):
  t0: float64 = perf_counter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(js))


def _bench_dump_list_user(xs: list[User]) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perf_counter()
  Json.dump(xs, fp)
  elapsed: float64 = perf_counter() - t0
  return (elapsed, len(fp.take()))


def _print_row(label: str, n: int, elapsed: float64, out_len: int) -> None:
  mb: float64 = 0.0
  if elapsed > 0.0:
    mb = (out_len / 1048576.0) / elapsed
  print(
    f"    {label} n={n}  time={format_duration(elapsed)}  "
    f"out={out_len} chars  ~{mb:.2f} MB/s"
  )


def _print_compare(kind: str, n: int, t_dumps: float64, t_dump: float64, out_len: int) -> None:
  ratio: float64 = 0.0
  if t_dump > 0.0:
    ratio = t_dumps / t_dump
  saved: float64 = 0.0
  if t_dumps > 0.0:
    saved = (t_dumps - t_dump) / t_dumps * 100.0
  print(f"  [{kind}]")
  _print_row("dumps", n, t_dumps, out_len)
  _print_row("dump(StringIO)", n, t_dump, out_len)
  print(f"    dumps/dump={ratio:.2f}x  dump saves {saved:.1f}% vs dumps")


class JsonDumpPerfListIntTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    n: int = _SIZE_INT
    xs: list[int] = _make_list_int(n)
    rd: (float64, int) = _bench_dumps_list_int(xs)
    rp: (float64, int) = _bench_dump_list_int(xs)
    _print_compare("list[int]", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n)


class JsonDumpPerfListStrTests(TestCaseMixin):
  _test_tag = 11

  @override
  def test(self):
    n: int = _SIZE_STR
    xs: list[str] = _make_list_str(n)
    rd: (float64, int) = _bench_dumps_list_str(xs)
    rp: (float64, int) = _bench_dump_list_str(xs)
    _print_compare("list[str]", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n * 4)


class JsonDumpPerfDictStrIntTests(TestCaseMixin):
  _test_tag = 12

  @override
  def test(self):
    n: int = _SIZE_DICT
    d: dict[str, int] = _make_dict_str_int(n)
    rd: (float64, int) = _bench_dumps_dict_str_int(d)
    rp: (float64, int) = _bench_dump_dict_str_int(d)
    _print_compare("dict[str,int]", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n * 4)


class JsonDumpPerfUserTagsTests(TestCaseMixin):
  _test_tag = 13

  @override
  def test(self):
    n: int = _SIZE_TAGS
    u: User = _make_user_tags(n)
    rd: (float64, int) = _bench_dumps_user(u)
    rp: (float64, int) = _bench_dump_user(u)
    _print_compare("User(tags)", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n * 4)


class JsonDumpPerfListUserTests(TestCaseMixin):
  _test_tag = 14

  @override
  def test(self):
    n: int = _SIZE_LIST_USER
    xs: list[User] = _make_list_user(n)
    rd: (float64, int) = _bench_dumps_list_user(xs)
    rp: (float64, int) = _bench_dump_list_user(xs)
    _print_compare("list[User]", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n * 20)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
