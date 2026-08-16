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
  minScore: int = 0
  members: list[Member] @optional = []


@copyable
class Org:
  teams: list[Team] = []


class BuildStructRootTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    org: Org = Org.build(
      'teams[:1] > name="alpha", minScore=5, '
      'members[:2] > score=10,name="amy"'
    )
    self.assertEqual(len(org.teams), 1)
    t: Team = org.teams[0]
    self.assertEqual(t.name, "alpha")
    self.assertEqual(t.minScore, 5)
    self.assertEqual(len(t.members), 2)
    self.assertEqual(t.members[0].score, 10)
    self.assertEqual(t.members[0].name, "amy")
    self.assertEqual(t.members[1].score, 10)
    self.assertEqual(t.members[1].name, "amy")


class BuildIndexBindTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    prefix: str = "t"
    org: Org = Org.build(
      "teams[:3]: $i > name={prefix + str($i)}, minScore=$i, "
      "members[:2]: $j > score={$i * 10 + $j}, name={str($j)}"
    )
    self.assertEqual(len(org.teams), 3)
    self.assertEqual(org.teams[0].name, "t0")
    self.assertEqual(org.teams[0].minScore, 0)
    self.assertEqual(org.teams[1].name, "t1")
    self.assertEqual(org.teams[1].minScore, 1)
    self.assertEqual(org.teams[2].name, "t2")
    self.assertEqual(org.teams[2].minScore, 2)
    self.assertEqual(len(org.teams[0].members), 2)
    self.assertEqual(org.teams[0].members[0].score, 0)
    self.assertEqual(org.teams[0].members[1].score, 1)
    self.assertEqual(org.teams[1].members[0].score, 10)


class BuildListRootTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    teams: list[Team] = list[Team].build("[:2]: $i > name={str($i)}")
    self.assertEqual(len(teams), 2)
    self.assertEqual(teams[0].name, "0")
    self.assertEqual(teams[1].name, "1")


class BuildEmptyListTests(TestCaseMixin):
  _testTag = 30

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
  _testTag = 40

  @override
  def test(self):
    viaBuild: Org = Org.build(
      'teams[:1] > name="alpha", minScore=5, members[:2] > score=10,name="amy"'
    )
    m1: Member = new(score=10, name="amy")
    m2: Member = new(score=10, name="amy")
    t: Team = new(name="alpha", minScore=5)
    t.members.append(m1)
    t.members.append(m2)
    viaHand: Org = new()
    viaHand.teams.append(t)
    self.assertEqual(len(viaBuild.teams), len(viaHand.teams))
    self.assertEqual(viaBuild.teams[0].name, viaHand.teams[0].name)
    self.assertEqual(viaBuild.teams[0].minScore, viaHand.teams[0].minScore)
    self.assertEqual(len(viaBuild.teams[0].members), len(viaHand.teams[0].members))
    self.assertEqual(
      viaBuild.teams[0].members[0].score,
      viaHand.teams[0].members[0].score,
    )


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
