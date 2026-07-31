"""Phase 4：命令写限制 + 建对象挂 Mesh 步进。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

from .command import CommandBus, CommandResult, ZeusCommand
from .world import WORLD_PLAYING


class CommandPlayWriteLockTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    bus: CommandBus = new()
    bus.dispatch(ZeusCommand.ObjectCreate("a", ""))
    bus.dispatch(ZeusCommand.PlayStart())
    self.assertEqual(bus.world.state, WORLD_PLAYING)
    r: CommandResult = bus.dispatch(ZeusCommand.ObjectCreate("b", ""))
    self.assertFalse(r.ok)
    r = bus.dispatch(ZeusCommand.EditorSelect("a"))
    self.assertTrue(r.ok)
    bus.dispatch(ZeusCommand.PlayStop())
    r = bus.dispatch(ZeusCommand.ObjectCreate("b", ""))
    self.assertTrue(r.ok)


class CommandPipelineTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    bus: CommandBus = new()
    bus.dispatch(ZeusCommand.ObjectCreate("cube", ""))
    bus.dispatch(ZeusCommand.ObjectAddMesh("cube", 1.0))
    bus.dispatch(ZeusCommand.ObjectSetPosition("cube", 1.0, 2.0, 3.0))
    r: CommandResult = bus.dispatch(ZeusCommand.PlayStep(2))
    self.assertTrue(r.ok)
    self.assertEqual(bus.world.state, WORLD_PLAYING)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
