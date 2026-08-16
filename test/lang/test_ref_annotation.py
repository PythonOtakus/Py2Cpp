"""``T @ref``：形参/返回值/局部绑定 → C++ ``T&``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.design.ecs import ECSComponentTable, ECSEntity


@copyable
@dataclass(eq=True)
class Position:
  x: int = 0
  y: int = 0


def bumpX(table: ECSComponentTable[Position] @ref, e: ECSEntity) -> None:
  p: Position @ref = table[e]
  p.x += 1


class RefAnnotationTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    table: ECSComponentTable[Position] = new()
    e: ECSEntity = new(index=0, generation=0)
    table[e] = new(x=5, y=0)
    bumpX(table, e)
    self.assertEqual(table[e].x, 6)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
