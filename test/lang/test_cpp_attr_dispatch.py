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


def read_prop(obj) -> int:
  return obj.value


def write_prop(obj) -> None:
  obj.value = 7


def read_field(obj) -> int:
  return obj.x


def write_field(obj) -> None:
  obj.x = 3


def exercise_templates(h: HasField) -> int:
  write_field(h)
  return read_field(h)


class CppAttrDispatchTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    row: HasField = new()
    row.x = 3
    self.assertEqual(exercise_templates(row), 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
