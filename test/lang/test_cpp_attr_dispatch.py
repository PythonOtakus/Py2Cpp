"""``PY2CPP_GETATTR``：无注解/模板形参上的 ``@property`` 与字段。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@copyable
class HasProp:
  _v: int = 0

  @property
  def value(self) -> int:
    return self._v

  @property.setter
  def value(self, v: int) -> None:
    self._v = v


@dataclass
@copyable
class HasField:
  x: int = 0


def readProp(obj) -> int:
  return obj.value


def writeProp(obj) -> None:
  obj.value = 7


def readField(obj) -> int:
  return obj.x


def writeField(obj) -> None:
  obj.x = 3


def exerciseTemplates(h: HasField) -> int:
  writeField(h)
  return readField(h)


class CppAttrDispatchTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    row: HasField = new()
    row.x = 3
    self.assertEqual(exerciseTemplates(row), 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
