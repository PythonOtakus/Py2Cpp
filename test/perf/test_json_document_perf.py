"""``JsonDocument`` 局部 patch + ``commit`` 与全量 ``loads``/``dumps`` 写回性能对比（stdout 打印耗时）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io.path import Path
from py2cpp.io.file.path import join
from py2cpp.serde.json import Json, JsonDocument
from py2cpp.system.time import formatDuration, perfCounter
from py2cpp.test.test_temp import _TestTemp, ensureTestTemp

# 与 ``scripts/compare_json_perf.py`` 规模同一量级：嵌套 ``Org``，单次深路径读写/写回
_NTeams: int = 100
_NMembers: int = 20
_TeamIdx: int = 50
_MemberIdx: int = 10
_PatchName: str = "patched"


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


def _makeOrg(nTeams: int, nMembers: int) -> Org:
  teams: list[Team] = []
  t: int = 0
  while t < nTeams:
    members: list[User] = []
    m: int = 0
    while m < nMembers:
      u: User = new(id=m, name="user")
      members.append(u)
      m += 1
    team: Team = new(name="team", members=members)
    teams.append(team)
    t += 1
  return new(title="bench", teams=teams)


def _printRow(label: str, elapsed: float64, nbytes: int) -> None:
  mb: float64 = 0.0
  if elapsed > 0.0:
    mb = (nbytes / 1048576.0) / elapsed
  print(
    f"  {label}  time={formatDuration(elapsed)}  "
    f"bytes={nbytes}  ~{mb:.2f} MB/s"
  )


def _printRatio(label: str, tFull: float64, tDoc: float64) -> None:
  ratio: float64 = 0.0
  if tDoc > 0.0:
    ratio = tFull / tDoc
  print(f"  {label}  full/document = {ratio:.2f}x")


def _benchFullRmw(path: Path, teamI: int, memberI: int, newName: str) -> float64:
  t0: float64 = perfCounter()
  text: str = path.readText()
  org: Org = Json.loads[Org](text)
  org.teams[teamI].members[memberI].name = newName
  out: str = Json.dumps(org)
  path.writeText(out)
  return perfCounter() - t0


def _benchDocumentPatch(path: Path, teamI: int, memberI: int, newName: str) -> float64:
  t0: float64 = perfCounter()
  doc: JsonDocument[Org] = new.open(path.__str__(), "r+")
  tOpen: float64 = perfCounter() - t0
  t1: float64 = perfCounter()
  doc.teams[teamI].members[memberI].name = newName
  tPatch: float64 = perfCounter() - t1
  t2: float64 = perfCounter()
  doc.commit()
  tCommit: float64 = perfCounter() - t2
  print(
    f"    document phases  open={formatDuration(tOpen)}  "
    f"patch={formatDuration(tPatch)}  commit={formatDuration(tCommit)}"
  )
  return tOpen + tPatch + tCommit


def _benchFullRead(path: Path, teamI: int, memberI: int) -> float64:
  t0: float64 = perfCounter()
  text: str = path.readText()
  org: Org = Json.loads[Org](text)
  _name: str = org.teams[teamI].members[memberI].name
  return perfCounter() - t0


def _readNameFull(path: Path, teamI: int, memberI: int) -> str:
  org: Org = Json.loads[Org](path.readText())
  return org.teams[teamI].members[memberI].name


def _benchDocumentRead(path: Path, teamI: int, memberI: int) -> float64:
  t0: float64 = perfCounter()
  doc: JsonDocument[Org] = new.open(path.__str__(), "r")
  tOpen: float64 = perfCounter() - t0
  t1: float64 = perfCounter()
  _name: str = doc.teams[teamI].members[memberI].name
  tRead: float64 = perfCounter() - t1
  print(
    f"    document phases  open={formatDuration(tOpen)}  "
    f"read={formatDuration(tRead)}"
  )
  return tOpen + tRead


def _readNameDocument(path: Path, teamI: int, memberI: int) -> str:
  doc: JsonDocument[Org] = new.open(path.__str__(), "r")
  return doc.teams[teamI].members[memberI].name


class JsonDocumentPerfPatchTests(TestCaseMixin):
  """深路径字段写回：全量 RMW vs ``JsonDocument`` patch + ``commit``。"""

  _testTag = 1

  @override
  def test(self):
    ensureTestTemp()
    org: Org = _makeOrg(_NTeams, _NMembers)
    js: str = Json.dumps(org)
    nbytes: int = len(js)
    pathFull: Path = Path(join(_TestTemp, "_json_doc_perf_full.json"))
    pathDoc: Path = Path(join(_TestTemp, "_json_doc_perf_doc.json"))
    pathFull.writeText(js)
    pathDoc.writeText(js)

    tFull: float64 = _benchFullRmw(pathFull, _TeamIdx, _MemberIdx, _PatchName)
    tDoc: float64 = _benchDocumentPatch(pathDoc, _TeamIdx, _MemberIdx, _PatchName)

    print(
      f"patch teams[{_TeamIdx}].members[{_MemberIdx}].name "
      f"teams={_NTeams} members={_NMembers} bytes={nbytes}"
    )
    _printRow("full loads+dumps+write", tFull, nbytes)
    _printRow("document patch+commit", tDoc, nbytes)
    _printRatio("writeback", tFull, tDoc)

    orgFull: Org = Json.loads[Org](pathFull.readText())
    docCheck: JsonDocument[Org] = new.open(pathDoc.__str__(), "r")
    nameDoc: str = docCheck.teams[_TeamIdx].members[_MemberIdx].name
    self.assertEqual(orgFull.teams[_TeamIdx].members[_MemberIdx].name, _PatchName)
    self.assertEqual(nameDoc, _PatchName)


class JsonDocumentPerfReadTests(TestCaseMixin):
  """深路径只读：全量 ``loads`` vs ``JsonDocument`` 懒读（无写回）。"""

  _testTag = 2

  @override
  def test(self):
    ensureTestTemp()
    org: Org = _makeOrg(_NTeams, _NMembers)
    js: str = Json.dumps(org)
    nbytes: int = len(js)
    path: Path = Path(join(_TestTemp, "_json_doc_perf_read.json"))
    path.writeText(js)

    tFull: float64 = _benchFullRead(path, _TeamIdx, _MemberIdx)
    tDoc: float64 = _benchDocumentRead(path, _TeamIdx, _MemberIdx)

    print(
      f"read teams[{_TeamIdx}].members[{_MemberIdx}].name "
      f"teams={_NTeams} members={_NMembers} bytes={nbytes}"
    )
    _printRow("full read+loads", tFull, nbytes)
    _printRow("document lazy read", tDoc, nbytes)
    _printRatio("read", tFull, tDoc)

    self.assertEqual(_readNameFull(path, _TeamIdx, _MemberIdx), "user")
    self.assertEqual(_readNameDocument(path, _TeamIdx, _MemberIdx), "user")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
