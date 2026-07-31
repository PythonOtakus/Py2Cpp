"""Phase 3：命令总线 + 场景 JSON + Hierarchy/Inspector 烟雾。"""
from py2cpp import *
from py2cpp.math import almost
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.test.test_temp import _TEST_TEMP, ensure_test_temp
from py2cpp.io.file.path import join
from py2cpp.ui.app import UIApp

from .command import CommandBus, CommandResult, ZeusCommand
from .editor.inspector import InspectorPanel
from .editor.session import EditorSession
from .editor.shell import EditorShell
from .scene import GameObject
from .world import WORLD_PLAYING, WORLD_STOPPED
from py2cpp.spatial.vector import Vector3

_EDITOR_TMP: str = join(_TEST_TEMP, "zeus_editor_scene.zas")


class CommandObjectTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    bus: CommandBus = new()
    r: CommandResult = bus.dispatch(ZeusCommand.ObjectCreate("player", ""))
    self.assertTrue(r.ok)
    found: GameObject | None = bus.world.root.find("player")
    self.assertTrue(found is not None)
    r = bus.dispatch(ZeusCommand.ObjectSetPosition("player", 1.5, 2.0, -3.0))
    self.assertTrue(r.ok)
    pos0: Vector3 = found.root.local_position
    self.assertTrue(almost(pos0.x, 1.5))
    self.assertTrue(almost(pos0.y, 2.0))
    self.assertTrue(almost(pos0.z, -3.0))
    r = bus.dispatch(ZeusCommand.ObjectAddMesh("player", 1.0))
    self.assertTrue(r.ok)
    self.assertTrue(found.find_component("MeshComponent") is not None)
    r = bus.dispatch(ZeusCommand.EditorSelect("player"))
    self.assertTrue(r.ok)
    self.assertEqual(bus.selected, "player")


class CommandPlayStepTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    bus: CommandBus = new()
    bus.dispatch(ZeusCommand.ObjectCreate("cube", ""))
    r: CommandResult = bus.dispatch(ZeusCommand.PlayStep(3))
    self.assertTrue(r.ok)
    self.assertEqual(bus.world.state, WORLD_PLAYING)
    bus.dispatch(ZeusCommand.PlayStop())
    self.assertEqual(bus.world.state, WORLD_STOPPED)


class SceneJsonRoundTripTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    ensure_test_temp()
    bus: CommandBus = new()
    bus.dispatch(ZeusCommand.ObjectCreate("player", ""))
    bus.dispatch(ZeusCommand.ObjectSetPosition("player", 4.0, 5.0, 6.0))
    bus.dispatch(ZeusCommand.ObjectAddMesh("player", 1.0))
    bus.dispatch(ZeusCommand.ObjectSetActive("player", False))
    text: str = bus.dump_json()
    self.assertTrue("player" in text)
    self.assertTrue("MeshComponent" in text)
    bus2: CommandBus = new()
    r: CommandResult = bus2.dispatch(ZeusCommand.SceneFromJson(text))
    self.assertTrue(r.ok)
    p: GameObject | None = bus2.world.root.find("player")
    self.assertTrue(p is not None)
    self.assertFalse(p.active)
    pos1: Vector3 = p.root.local_position
    self.assertTrue(almost(pos1.x, 4.0))
    self.assertTrue(almost(pos1.y, 5.0))
    self.assertTrue(almost(pos1.z, 6.0))
    self.assertTrue(p.find_component("MeshComponent") is not None)
    bus2.dispatch(ZeusCommand.SceneSave(_EDITOR_TMP, "RoundTrip"))
    bus3: CommandBus = new()
    bus3.dispatch(ZeusCommand.SceneLoad(_EDITOR_TMP))
    p2: GameObject | None = bus3.world.root.find("player")
    self.assertTrue(p2 is not None)
    pos2: Vector3 = p2.root.local_position
    self.assertTrue(almost(pos2.x, 4.0))


class EditorSessionSelectTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    session: EditorSession = new()
    session.dispatch(ZeusCommand.ObjectCreate("a", ""))
    session.dispatch(ZeusCommand.ObjectCreate("b", "a"))
    session.rebuild_hierarchy()
    self.assertTrue(len(session.rows) >= 3)
    r: CommandResult = session.select_index(1)
    self.assertTrue(r.ok)
    self.assertTrue(session.bus.selected != "")


class InspectorApplyTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    bus: CommandBus = new()
    bus.dispatch(ZeusCommand.ObjectCreate("hero", ""))
    bus.dispatch(ZeusCommand.EditorSelect("hero"))
    panel: InspectorPanel = new()
    panel.bind_bus(bus)
    panel.load_from_selection()
    self.assertEqual(panel.object_name, "hero")
    panel.pos_x = "9"
    panel.pos_y = "8"
    panel.pos_z = "7"
    panel.active = False
    panel.apply()
    go: GameObject | None = bus.world.root.find("hero")
    self.assertTrue(go is not None)
    self.assertFalse(go.active)
    pos: Vector3 = go.root.local_position
    self.assertTrue(almost(pos.x, 9.0))
    self.assertTrue(almost(pos.y, 8.0))
    self.assertTrue(almost(pos.z, 7.0))


class EditorUiSmokeTests(TestCaseMixin):
  _test_tag = 6

  @override
  def test(self):
    if not UIApp.is_available():
      return
    shell: EditorShell = new()
    shell.session.dispatch(ZeusCommand.ObjectCreate("cube", ""))
    shell.session.dispatch(ZeusCommand.ObjectSetPosition("cube", 1.0, 0.0, 0.0))
    shell.session.dispatch(ZeusCommand.EditorSelect("cube"))
    ok: bool = shell.open()
    self.assertTrue(ok)
    self.assertTrue(shell.hier_win.handle != 0)
    self.assertTrue(shell.insp_win.handle != 0)
    self.assertTrue(shell.hierarchy.handle != 0)
    shell.close()


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
