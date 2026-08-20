"""Phase 4：命令写限制 + 建对象挂 Mesh 步进。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

from .command import CommandBus, CommandResult, ZeusCommandUnion
from .world import WORLD_PLAYING


class CommandPlayWriteLockTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    bus: CommandBus = new()
    bus.dispatch(ZeusCommandUnion.ObjectCreate("a", ""))
    bus.dispatch(ZeusCommandUnion.PlayStart())
    self.assertEqual(bus.world.state, WORLD_PLAYING)
    r: CommandResult = bus.dispatch(ZeusCommandUnion.ObjectCreate("b", ""))
    self.assertFalse(r.ok)
    r = bus.dispatch(ZeusCommandUnion.EditorSelect("a"))
    self.assertTrue(r.ok)
    bus.dispatch(ZeusCommandUnion.PlayStop())
    r = bus.dispatch(ZeusCommandUnion.ObjectCreate("b", ""))
    self.assertTrue(r.ok)


class CommandPipelineTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    bus: CommandBus = new()
    bus.dispatch(ZeusCommandUnion.ObjectCreate("cube", ""))
    bus.dispatch(ZeusCommandUnion.ObjectAddMesh("cube", 1.0))
    bus.dispatch(ZeusCommandUnion.ObjectSetPosition("cube", 1.0, 2.0, 3.0))
    r: CommandResult = bus.dispatch(ZeusCommandUnion.PlayStep(2))
    self.assertTrue(r.ok)
    self.assertEqual(bus.world.state, WORLD_PLAYING)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
