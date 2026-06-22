"""``JsonDocument`` 局部 patch + ``commit`` 与全量 ``loads``/``dumps`` 写回性能对比（stdout 打印耗时）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io.path import Path
from py2cpp.io.file.path import join
from py2cpp.serde.json import Json, JsonDocument
from py2cpp.system.time import format_duration, perf_counter
from py2cpp.test.test_temp import _TEST_TEMP, ensure_test_temp

# 与 ``scripts/compare_json_perf.py`` 规模同一量级：嵌套 ``Org``，单次深路径读写/写回
_N_TEAMS: int = 100
_N_MEMBERS: int = 20
_TEAM_IDX: int = 50
_MEMBER_IDX: int = 10
_PATCH_NAME: str = "patched"


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
class Team:
  name: str
  members: list[User] @optional = []


@serializable
@copyable
@dataclass
class Org:
  title: str
  teams: list[Team] @optional = []


def _make_org(n_teams: int, n_members: int) -> Org:
  teams: list[Team] = []
  t: int = 0
  while t < n_teams:
    members: list[User] = []
    m: int = 0
    while m < n_members:
      u: User = new(id=m, name="user")
      members.append(u)
      m += 1
    team: Team = new(name="team", members=members)
    teams.append(team)
    t += 1
  return new(title="bench", teams=teams)


def _print_row(label: str, elapsed: float64, nbytes: int) -> None:
  mb: float64 = 0.0
  if elapsed > 0.0:
    mb = (nbytes / 1048576.0) / elapsed
  print(
    f"  {label}  time={format_duration(elapsed)}  "
    f"bytes={nbytes}  ~{mb:.2f} MB/s"
  )


def _print_ratio(label: str, t_full: float64, t_doc: float64) -> None:
  ratio: float64 = 0.0
  if t_doc > 0.0:
    ratio = t_full / t_doc
  print(f"  {label}  full/document = {ratio:.2f}x")


def _bench_full_rmw(path: Path, team_i: int, member_i: int, new_name: str) -> float64:
  t0: float64 = perf_counter()
  text: str = path.read_text()
  org: Org = Json.loads[Org](text)
  org.teams[team_i].members[member_i].name = new_name
  out: str = Json.dumps(org)
  path.write_text(out)
  return perf_counter() - t0


def _bench_document_patch(path: Path, team_i: int, member_i: int, new_name: str) -> float64:
  t0: float64 = perf_counter()
  doc: JsonDocument[Org] = new.open(path.__str__(), "r+")
  t_open: float64 = perf_counter() - t0
  t1: float64 = perf_counter()
  doc.teams[team_i].members[member_i].name = new_name
  t_patch: float64 = perf_counter() - t1
  t2: float64 = perf_counter()
  doc.commit()
  t_commit: float64 = perf_counter() - t2
  print(
    f"    document phases  open={format_duration(t_open)}  "
    f"patch={format_duration(t_patch)}  commit={format_duration(t_commit)}"
  )
  return t_open + t_patch + t_commit


def _bench_full_read(path: Path, team_i: int, member_i: int) -> float64:
  t0: float64 = perf_counter()
  text: str = path.read_text()
  org: Org = Json.loads[Org](text)
  _name: str = org.teams[team_i].members[member_i].name
  return perf_counter() - t0


def _read_name_full(path: Path, team_i: int, member_i: int) -> str:
  org: Org = Json.loads[Org](path.read_text())
  return org.teams[team_i].members[member_i].name


def _bench_document_read(path: Path, team_i: int, member_i: int) -> float64:
  t0: float64 = perf_counter()
  doc: JsonDocument[Org] = new.open(path.__str__(), "r")
  t_open: float64 = perf_counter() - t0
  t1: float64 = perf_counter()
  _name: str = doc.teams[team_i].members[member_i].name
  t_read: float64 = perf_counter() - t1
  print(
    f"    document phases  open={format_duration(t_open)}  "
    f"read={format_duration(t_read)}"
  )
  return t_open + t_read


def _read_name_document(path: Path, team_i: int, member_i: int) -> str:
  doc: JsonDocument[Org] = new.open(path.__str__(), "r")
  return doc.teams[team_i].members[member_i].name


class JsonDocumentPerfPatchTests(TestCaseMixin):
  """深路径字段写回：全量 RMW vs ``JsonDocument`` patch + ``commit``。"""

  _test_tag = 1

  @override
  def test(self):
    ensure_test_temp()
    org: Org = _make_org(_N_TEAMS, _N_MEMBERS)
    js: str = Json.dumps(org)
    nbytes: int = len(js)
    path_full: Path = Path(join(_TEST_TEMP, "_json_doc_perf_full.json"))
    path_doc: Path = Path(join(_TEST_TEMP, "_json_doc_perf_doc.json"))
    path_full.write_text(js)
    path_doc.write_text(js)

    t_full: float64 = _bench_full_rmw(path_full, _TEAM_IDX, _MEMBER_IDX, _PATCH_NAME)
    t_doc: float64 = _bench_document_patch(path_doc, _TEAM_IDX, _MEMBER_IDX, _PATCH_NAME)

    print(
      f"patch teams[{_TEAM_IDX}].members[{_MEMBER_IDX}].name "
      f"teams={_N_TEAMS} members={_N_MEMBERS} bytes={nbytes}"
    )
    _print_row("full loads+dumps+write", t_full, nbytes)
    _print_row("document patch+commit", t_doc, nbytes)
    _print_ratio("writeback", t_full, t_doc)

    org_full: Org = Json.loads[Org](path_full.read_text())
    doc_check: JsonDocument[Org] = new.open(path_doc.__str__(), "r")
    name_doc: str = doc_check.teams[_TEAM_IDX].members[_MEMBER_IDX].name
    self.assertEqual(org_full.teams[_TEAM_IDX].members[_MEMBER_IDX].name, _PATCH_NAME)
    self.assertEqual(name_doc, _PATCH_NAME)


class JsonDocumentPerfReadTests(TestCaseMixin):
  """深路径只读：全量 ``loads`` vs ``JsonDocument`` 懒读（无写回）。"""

  _test_tag = 2

  @override
  def test(self):
    ensure_test_temp()
    org: Org = _make_org(_N_TEAMS, _N_MEMBERS)
    js: str = Json.dumps(org)
    nbytes: int = len(js)
    path: Path = Path(join(_TEST_TEMP, "_json_doc_perf_read.json"))
    path.write_text(js)

    t_full: float64 = _bench_full_read(path, _TEAM_IDX, _MEMBER_IDX)
    t_doc: float64 = _bench_document_read(path, _TEAM_IDX, _MEMBER_IDX)

    print(
      f"read teams[{_TEAM_IDX}].members[{_MEMBER_IDX}].name "
      f"teams={_N_TEAMS} members={_N_MEMBERS} bytes={nbytes}"
    )
    _print_row("full read+loads", t_full, nbytes)
    _print_row("document lazy read", t_doc, nbytes)
    _print_ratio("read", t_full, t_doc)

    self.assertEqual(_read_name_full(path, _TEAM_IDX, _MEMBER_IDX), "user")
    self.assertEqual(_read_name_document(path, _TEAM_IDX, _MEMBER_IDX), "user")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
