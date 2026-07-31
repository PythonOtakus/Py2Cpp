"""Phase 6：跳一跳 headless + FBX/ZAS 资产烟雾。"""
from py2cpp import *
from py2cpp.io.file.path import join
from py2cpp.io.path import Path
from py2cpp.spatial.color import Color
from py2cpp.test.test_temp import _TEST_TEMP, ensure_test_temp
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

from .assets.fbx_ascii import mesh_to_fbx_ascii, read_fbx, write_fbx
from .command import CommandBus, ZeusCommand
from .jump.game import JumpGame
from .jump.motor import JUMP_FAILED, JUMP_IDLE, JUMP_LANDED
from .render.mesh import Mesh
from .scene_io import scene_load, scene_save


class JumpGameplayTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    game: JumpGame = new()
    game.setup_default()
    self.assertEqual(game.score, 0)
    game.simulate_perfect_jump()
    self.assertTrue(game.score >= 1)
    self.assertTrue(game.motor.state in {JUMP_LANDED, JUMP_IDLE})
    self.assertFalse(game.motor.state == JUMP_FAILED)


class FbxAsciiRoundTripTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    ensure_test_temp()
    col: Color = new(0.2, 0.6, 0.9, 1.0)
    cube: Mesh = new.colored_cube(1.0, col)
    path: str = join(_TEST_TEMP, "zeus_cube.fbx")
    write_fbx(cube, path)
    doc: Path = new(path)
    self.assertTrue(doc.exists())
    text: str = doc.read_text()
    self.assertTrue(text.find("Vertices") >= 0)
    loaded: Mesh = read_fbx(path, col)
    self.assertTrue(loaded.vertex_count > 0)
    ascii2: str = mesh_to_fbx_ascii(loaded)
    self.assertTrue(ascii2.find("Geometry") >= 0)


class ZasSceneRoundTripTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    ensure_test_temp()
    bus: CommandBus = new()
    bus.dispatch(ZeusCommand.ObjectCreate("p", ""))
    bus.dispatch(ZeusCommand.ObjectAddMesh("p", 1.0))
    path: str = join(_TEST_TEMP, "zeus_jump_scene.zas")
    scene_save(bus.world, path, "JumpDemo")
    doc: Path = new(path)
    self.assertTrue(doc.exists())
    text: str = doc.read_text()
    self.assertTrue(text.find("zas") >= 0)
    bus2: CommandBus = new()
    name: str = scene_load(bus2.world, path)
    self.assertEqual(name, "JumpDemo")
    self.assertTrue(bus2.world.root.find("p") is not None)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
