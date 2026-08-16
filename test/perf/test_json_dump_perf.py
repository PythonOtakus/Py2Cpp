"""``Json.dumps`` vs ``Json.dump``（``StringIO`` sink）性能对照。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io import StringIO
from py2cpp.serde.json import Json
from py2cpp.system.time import formatDuration, perfCounter

_SizeInt: int = 50000
_SizeStr: int = 20000
_SizeDict: int = 5000
_SizeTags: int = 10000
_SizeListUser: int = 2000


@serializable
@copyable
@dataclass
class User:
  id: int
  name: str
  active: bool = True
  tags: list[str] @optional = []


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


def _benchDumpsListInt(xs: list[int]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpListInt(xs: list[int]) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perfCounter()
  Json.dump(xs, fp)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(fp.take()))


def _benchDumpsListStr(xs: list[str]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpListStr(xs: list[str]) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perfCounter()
  Json.dump(xs, fp)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(fp.take()))


def _benchDumpsDictStrInt(d: dict[str, int]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(d)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpDictStrInt(d: dict[str, int]) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perfCounter()
  Json.dump(d, fp)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(fp.take()))


def _benchDumpsUser(u: User) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(u)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpUser(u: User) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perfCounter()
  Json.dump(u, fp)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(fp.take()))


def _benchDumpsListUser(xs: list[User]) -> (float64, int):
  t0: float64 = perfCounter()
  js: str = Json.dumps(xs)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(js))


def _benchDumpListUser(xs: list[User]) -> (float64, int):
  fp: StringIO = new()
  t0: float64 = perfCounter()
  Json.dump(xs, fp)
  elapsed: float64 = perfCounter() - t0
  return (elapsed, len(fp.take()))


def _printRow(label: str, n: int, elapsed: float64, outLen: int) -> None:
  mb: float64 = 0.0
  if elapsed > 0.0:
    mb = (outLen / 1048576.0) / elapsed
  print(
    f"    {label} n={n}  time={formatDuration(elapsed)}  "
    f"out={outLen} chars  ~{mb:.2f} MB/s"
  )


def _printCompare(kind: str, n: int, tDumps: float64, tDump: float64, outLen: int) -> None:
  ratio: float64 = 0.0
  if tDump > 0.0:
    ratio = tDumps / tDump
  saved: float64 = 0.0
  if tDumps > 0.0:
    saved = (tDumps - tDump) / tDumps * 100.0
  print(f"  [{kind}]")
  _printRow("dumps", n, tDumps, outLen)
  _printRow("dump(StringIO)", n, tDump, outLen)
  print(f"    dumps/dump={ratio:.2f}x  dump saves {saved:.1f}% vs dumps")


class JsonDumpPerfListIntTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    n: int = _SizeInt
    xs: list[int] = _makeListInt(n)
    rd: (float64, int) = _benchDumpsListInt(xs)
    rp: (float64, int) = _benchDumpListInt(xs)
    _printCompare("list[int]", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n)


class JsonDumpPerfListStrTests(TestCaseMixin):
  _testTag = 11

  @override
  def test(self):
    n: int = _SizeStr
    xs: list[str] = _makeListStr(n)
    rd: (float64, int) = _benchDumpsListStr(xs)
    rp: (float64, int) = _benchDumpListStr(xs)
    _printCompare("list[str]", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n * 4)


class JsonDumpPerfDictStrIntTests(TestCaseMixin):
  _testTag = 12

  @override
  def test(self):
    n: int = _SizeDict
    d: dict[str, int] = _makeDictStrInt(n)
    rd: (float64, int) = _benchDumpsDictStrInt(d)
    rp: (float64, int) = _benchDumpDictStrInt(d)
    _printCompare("dict[str,int]", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n * 4)


class JsonDumpPerfUserTagsTests(TestCaseMixin):
  _testTag = 13

  @override
  def test(self):
    n: int = _SizeTags
    u: User = _makeUserTags(n)
    rd: (float64, int) = _benchDumpsUser(u)
    rp: (float64, int) = _benchDumpUser(u)
    _printCompare("User(tags)", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n * 4)


class JsonDumpPerfListUserTests(TestCaseMixin):
  _testTag = 14

  @override
  def test(self):
    n: int = _SizeListUser
    xs: list[User] = _makeListUser(n)
    rd: (float64, int) = _benchDumpsListUser(xs)
    rp: (float64, int) = _benchDumpListUser(xs)
    _printCompare("list[User]", n, rd[0], rp[0], rd[1])
    self.assertEqual(rd[1], rp[1])
    self.assertTrue(rd[1] > n * 20)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
