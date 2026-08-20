"""``JsonDocument`` 部分访问与增删改查（静态字段链）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io.path import Path

from py2cpp.serde.json import Json, JsonDocument
from py2cpp.test.test_temp import _TestTemp, ensureTestTemp


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


_Sample: str = (
  '{"title":"acme","teams":[{"name":"eng","members":'
  '[{"id":1,"name":"bob","active":true,"tags":[]}'
  ']}]}'
)


class JsonDocumentLoadTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    ensureTestTemp()
    path: Path = Path(_TestTemp) / "_json_doc_load.json"
    path.writeText(_Sample)
    doc: JsonDocument[Org] = new.open(str(path), "r")
    org: Org = doc.load()
    org2: Org = Json.loads[Org](_Sample)
    self.assertEqual(org.title, org2.title)
    self.assertEqual(org.teams[0].name, org2.teams[0].name)
    self.assertEqual(org.teams[0].members[0].name, org2.teams[0].members[0].name)
    self.assertEqual(doc.dump(), _Sample)


class JsonDocumentReadTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    ensureTestTemp()
    path: Path = Path(_TestTemp) / "_json_doc_read.json"
    path.writeText(_Sample)
    doc: JsonDocument[Org] = new.open(str(path), "r")
    name: str = doc.teams[0].members[0].name
    self.assertEqual(name, "bob")
    title: str = doc.title
    self.assertEqual(title, "acme")


class JsonDocumentCrudTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    ensureTestTemp()
    path: Path = Path(_TestTemp) / "_json_doc_crud.json"
    path.writeText(_Sample)
    doc: JsonDocument[Org] = new.open(str(path), "r+")
    doc.teams[0].members[0].name = "alice"
    u: User = new(id=2, name="carol", active=True)
    doc.teams[0].members.append(u)
    del doc.teams[0].members[0]
    doc.commit()
    doc2: JsonDocument[Org] = new.open(str(path), "r")
    self.assertEqual(doc2.teams[0].members[0].name, "carol")
    org: Org = doc2.load()
    self.assertEqual(org.teams[0].members[0].id, 2)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
