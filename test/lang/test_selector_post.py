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
  min_score: int = 0
  members: list[Member] @optional = []


@copyable
class Org:
  teams: list[Team] @optional = []


def build_org() -> Org:
  m1: Member = new(10, "amy", "eng")
  m2: Member = new(0, "bob", "eng")
  m3: Member = new(5, "cara", "ops")
  t: Team = Team(name="alpha")
  t.min_score = 5
  t.members.append(m1)
  t.members.append(m2)
  t.members.append(m3)
  o: Org = new()
  o.teams.append(t)
  return o


class SelectPostSortTests(TestCaseMixin):
  _test_tag = 98

  @override
  def test(self):
    team: Team = build_org().teams[0]
    hits: list[Member] = team.select(".members{.score > 0}@sort(-.score, .name)")
    self.assertEqual(len(hits), 2)
    self.assertEqual(hits[0].name, "amy")
    self.assertEqual(hits[1].name, "cara")


class SelectPostCountTests(TestCaseMixin):
  _test_tag = 99

  @override
  def test(self):
    org: Org = build_org()
    self.assertEqual(org.select(".teams@count"), 1)
    team: Team = org.teams[0]
    freq: Counter[str] = team.select(".members@count(.dept)")
    self.assertEqual(freq["eng"], 2)
    self.assertEqual(freq["ops"], 1)


class SelectPostGroupTests(TestCaseMixin):
  _test_tag = 100

  @override
  def test(self):
    team: Team = build_org().teams[0]
    by_dept: dict[str, list[Member]] = team.select(".members@group(.dept)")
    self.assertEqual(len(by_dept["eng"]), 2)
    self.assertEqual(len(by_dept["ops"]), 1)


class SelectPostBindSortTests(TestCaseMixin):
  _test_tag = 101

  @override
  def test(self):
    org: Org = build_org()
    names: list[Member] = org.select(
      ".teams[0]:$t; $t.members{.score > $t.min_score}@sort(.name)",
    )
    self.assertEqual(len(names), 1)
    self.assertEqual(names[0].name, "amy")


class SelectPostSortExprKeyTests(TestCaseMixin):
  """``@sort`` 键支持与 ``{filter}`` 相同的算术表达式。"""

  _test_tag = 103

  @override
  def test(self):
    org: Org = build_org()
    ordered: list[Member] = org.select(
      ".teams[0]:$t; $t.members@sort(.score - $t.min_score, .name)",
    )
    self.assertEqual(len(ordered), 3)
    self.assertEqual(ordered[0].name, "bob")
    self.assertEqual(ordered[1].name, "cara")
    self.assertEqual(ordered[2].name, "amy")


class SelectPostBindSortParentKeyTests(TestCaseMixin):
  """方案 A：``@sort`` 键可用 ``:$t`` 快照的父字段（与 ``{filter}`` 同规则）。"""

  _test_tag = 102

  @override
  def test(self):
    org: Org = build_org()
    by_inline: list[Member] = org.select(
      ".teams[0]:$t.members{.score > 0}@sort($t.name, -.score, .name)",
    )
    by_chain: list[Member] = org.select(
      ".teams[0]:$t; $t.members{.score > 0}@sort($t.name, -.score, .name)",
    )
    self.assertEqual(len(by_inline), 2)
    self.assertEqual(by_inline[0].name, "amy")
    self.assertEqual(by_inline[1].name, "cara")
    self.assertEqual(len(by_chain), 2)
    self.assertEqual(by_chain[0].name, by_inline[0].name)
    self.assertEqual(by_chain[1].name, by_inline[1].name)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
