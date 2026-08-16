"""``select`` 后处理集成测（``@sort`` / ``@group`` / ``@count``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@dataclass
class Member:
  score: int
  name: str
  dept: str = ""


@dataclass
class Team:
  name: str
  minScore: int = 0
  members: list[Member] @optional = []


@copyable
class Org:
  teams: list[Team] = []


def buildOrg() -> Org:
  m1: Member = new(10, "amy", "eng")
  m2: Member = new(0, "bob", "eng")
  m3: Member = new(5, "cara", "ops")
  t: Team = Team(name="alpha")
  t.minScore = 5
  t.members.append(m1)
  t.members.append(m2)
  t.members.append(m3)
  o: Org = new()
  o.teams.append(t)
  return o


class SelectPostSortTests(TestCaseMixin):
  _testTag = 98

  @override
  def test(self):
    team: Team = buildOrg().teams[0]
    hits: list[Member] = team.select(".members{.score > 0}@sort(-.score, .name)")
    self.assertEqual(len(hits), 2)
    self.assertEqual(hits[0].name, "amy")
    self.assertEqual(hits[1].name, "cara")


class SelectPostCountTests(TestCaseMixin):
  _testTag = 99

  @override
  def test(self):
    org: Org = buildOrg()
    self.assertEqual(org.select(".teams@count"), 1)
    team: Team = org.teams[0]
    freq: Counter[str] = team.select(".members@count(.dept)")
    self.assertEqual(freq["eng"], 2)
    self.assertEqual(freq["ops"], 1)


class SelectPostGroupTests(TestCaseMixin):
  _testTag = 100

  @override
  def test(self):
    team: Team = buildOrg().teams[0]
    byDept: dict[str, list[Member]] = team.select(".members@group(.dept)")
    self.assertEqual(len(byDept["eng"]), 2)
    self.assertEqual(len(byDept["ops"]), 1)


class SelectPostBindSortTests(TestCaseMixin):
  _testTag = 101

  @override
  def test(self):
    org: Org = buildOrg()
    names: list[Member] = org.select(
      ".teams[0]:$t; $t.members{.score > $t.minScore}@sort(.name)",
    )
    self.assertEqual(len(names), 1)
    self.assertEqual(names[0].name, "amy")


class SelectPostSortExprKeyTests(TestCaseMixin):
  """``@sort`` 键支持与 ``{filter}`` 相同的算术表达式。"""

  _testTag = 103

  @override
  def test(self):
    org: Org = buildOrg()
    ordered: list[Member] = org.select(
      ".teams[0]:$t; $t.members@sort(.score - $t.minScore, .name)",
    )
    self.assertEqual(len(ordered), 3)
    self.assertEqual(ordered[0].name, "bob")
    self.assertEqual(ordered[1].name, "cara")
    self.assertEqual(ordered[2].name, "amy")


class SelectPostBindSortParentKeyTests(TestCaseMixin):
  """方案 A：``@sort`` 键可用 ``:$t`` 快照的父字段（与 ``{filter}`` 同规则）。"""

  _testTag = 102

  @override
  def test(self):
    org: Org = buildOrg()
    byInline: list[Member] = org.select(
      ".teams[0]:$t.members{.score > 0}@sort($t.name, -.score, .name)",
    )
    byChain: list[Member] = org.select(
      ".teams[0]:$t; $t.members{.score > 0}@sort($t.name, -.score, .name)",
    )
    self.assertEqual(len(byInline), 2)
    self.assertEqual(byInline[0].name, "amy")
    self.assertEqual(byInline[1].name, "cara")
    self.assertEqual(len(byChain), 2)
    self.assertEqual(byChain[0].name, byInline[0].name)
    self.assertEqual(byChain[1].name, byInline[1].name)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
