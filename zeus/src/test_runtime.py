"""Phase 1：World / GameObject / Component / Transform headless 测例。"""
from py2cpp import *
from py2cpp.math import almost
from py2cpp.spatial.vector import Vector3
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

from .scene import CameraComponent, Component, GameObject, MeshComponent, Transform
from .simple_world import SimpleBody, SimpleWorld
from .world import World


@refcount
class ScoreBoard(Component):
  score: int

  def __init__(self):
    self.kind = "ScoreBoard"
    self.score = 0

  @override
  def on_update(self, dt: float64) -> None:
    self.score += 1


class GameObjectTreeTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    root: GameObject = new("root")
    child: GameObject = new("player")
    child.parent = root
    self.assertEqual(root.child_count, 1)
    found: GameObject | None = root.find("player")
    self.assertTrue(found is not None)
    self.assertEqual(found.name, "player")
    child.parent = None
    self.assertEqual(root.child_count, 0)


class ComponentLifecycleTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    go: GameObject = new("actor")
    self.assertEqual(go.component_count(), 1)
    board: ScoreBoard = new()
    go.add_component(board)
    self.assertEqual(go.component_count(), 2)
    found: Component | None = go.find_component("ScoreBoard")
    self.assertTrue(found is not None)
    go.update(0.016)
    self.assertEqual(board.score, 1)
    self.assertTrue(go.remove_component("ScoreBoard"))
    self.assertEqual(go.component_count(), 1)


class TransformComposeTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    parent: Transform = new()
    child: Transform = new()
    parent.localPosition = Vector3(10.0, 0.0, 0.0)
    child.localPosition = Vector3(2.0, 3.0, 0.0)
    parent.attach(child)
    wp: Vector3 = child.position
    self.assertTrue(almost(wp.x, 12.0))
    self.assertTrue(almost(wp.y, 3.0))


class WorldTaskTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    world: World = new()
    child: GameObject = new("cube")
    child.parent = world.root
    n: int = world.run_frames(3)
    self.assertEqual(n, 3)
    self.assertEqual(world.state, 1)


class MeshCameraComponentTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    go: GameObject = new("prop")
    mesh: MeshComponent = new()
    mesh.set_cube(1.0)
    go.add_component(mesh)
    go.add_component(CameraComponent())
    self.assertTrue(go.find_component("MeshComponent") is not None)
    self.assertTrue(go.find_component("CameraComponent") is not None)
    self.assertTrue(mesh.has_mesh)
    self.assertEqual(mesh.mesh.vertex_count, 36)


class SimplePhysicsTests(TestCaseMixin):
  _test_tag = 6

  @override
  def test(self):
    phys: SimpleWorld = new(-9.8, 0.0)
    body: SimpleBody = new()
    xf: Transform = new()
    xf.position = Vector3(0.0, 5.0, 0.0)
    for i in range(200):
      phys.step(body, xf, 0.016)
    self.assertTrue(body.grounded)
    self.assertTrue(almost(xf.position.y, 0.0))


class SceneSerializeSmokeTests(TestCaseMixin):
  _test_tag = 7

  @override
  def test(self):
    world: World = new()
    # 简易烟雾：快照字段可读（完整 @serializable 见后续；避免用户模块 .inl 双包含）
    self.assertEqual(world.root.name, "world_root")
    self.assertEqual(world.root.component_count(), 1)
    self.assertEqual(world.root.child_count, 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
