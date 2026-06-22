"""``Type.build("…")`` / ``list[T].build("…")`` 集成测。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@dataclass
class Member:
  score: int
  name: str


@dataclass
class Team:
  name: str
  min_score: int = 0
  members: list[Member] @optional = []


@copyable
class Org:
  teams: list[Team] @optional = []


class BuildStructRootTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    org: Org = Org.build(
      'teams[:1] > name="alpha", min_score=5, '
      'members[:2] > score=10,name="amy"'
    )
    self.assertEqual(len(org.teams), 1)
    t: Team = org.teams[0]
    self.assertEqual(t.name, "alpha")
    self.assertEqual(t.min_score, 5)
    self.assertEqual(len(t.members), 2)
    self.assertEqual(t.members[0].score, 10)
    self.assertEqual(t.members[0].name, "amy")
    self.assertEqual(t.members[1].score, 10)
    self.assertEqual(t.members[1].name, "amy")


class BuildIndexBindTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    prefix: str = "t"
    org: Org = Org.build(
      "teams[:3]: $i > name={prefix + str($i)}, min_score=$i, "
      "members[:2]: $j > score={$i * 10 + $j}, name={str($j)}"
    )
    self.assertEqual(len(org.teams), 3)
    self.assertEqual(org.teams[0].name, "t0")
    self.assertEqual(org.teams[0].min_score, 0)
    self.assertEqual(org.teams[1].name, "t1")
    self.assertEqual(org.teams[1].min_score, 1)
    self.assertEqual(org.teams[2].name, "t2")
    self.assertEqual(org.teams[2].min_score, 2)
    self.assertEqual(len(org.teams[0].members), 2)
    self.assertEqual(org.teams[0].members[0].score, 0)
    self.assertEqual(org.teams[0].members[1].score, 1)
    self.assertEqual(org.teams[1].members[0].score, 10)


class BuildListRootTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    teams: list[Team] = list[Team].build("[:2]: $i > name={str($i)}")
    self.assertEqual(len(teams), 2)
    self.assertEqual(teams[0].name, "0")
    self.assertEqual(teams[1].name, "1")


class BuildEmptyListTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    prefix: str = "eng"
    org: Org = Org.build(
      "teams[:1] > name={prefix + \"-1\"}, members[:0] >"
    )
    self.assertEqual(len(org.teams), 1)
    self.assertEqual(org.teams[0].name, "eng-1")
    self.assertEqual(len(org.teams[0].members), 0)


class BuildMatchesHandWrittenTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    via_build: Org = Org.build(
      'teams[:1] > name="alpha", min_score=5, members[:2] > score=10,name="amy"'
    )
    m1: Member = new(score=10, name="amy")
    m2: Member = new(score=10, name="amy")
    t: Team = new(name="alpha", min_score=5)
    t.members.append(m1)
    t.members.append(m2)
    via_hand: Org = new()
    via_hand.teams.append(t)
    self.assertEqual(len(via_build.teams), len(via_hand.teams))
    self.assertEqual(via_build.teams[0].name, via_hand.teams[0].name)
    self.assertEqual(via_build.teams[0].min_score, via_hand.teams[0].min_score)
    self.assertEqual(len(via_build.teams[0].members), len(via_hand.teams[0].members))
    self.assertEqual(
      via_build.teams[0].members[0].score,
      via_hand.teams[0].members[0].score,
    )


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
