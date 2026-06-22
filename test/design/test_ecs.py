"""ECS 集成测：演示用 ``ECSWorld`` / ``ECSPosition`` / ``ECSVelocity``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

from py2cpp.design.ecs import ECSComponentTable, ECSEntity, ECSWorldMixin


@copyable
@dataclass(eq=True)
class ECSPosition:
  x: int = 0
  y: int = 0


@copyable
@dataclass(eq=True)
class ECSVelocity:
  dx: int = 0
  dy: int = 0


@dataclass
class ECSSpawnComponents:
  """``ECSWorld.create(new(...))`` 组件包（标量字段，避免类体默认构造）。"""

  spawn_position: int = 0
  pos_x: int = 0
  pos_y: int = 0
  spawn_velocity: int = 0
  vel_dx: int = 0
  vel_dy: int = 0


class ECSWorld(ECSWorldMixin):
  """演示 World：``Position`` / ``Velocity`` 组件表。"""

  position: ECSComponentTable[ECSPosition] @property = new()
  velocity: ECSComponentTable[ECSVelocity] @property = new()

  def create(self, bundle: ECSSpawnComponents) -> ECSEntity:
    e: ECSEntity = self._alloc_entity()
    if bundle.spawn_position:
      pos: ECSPosition = new(x=bundle.pos_x, y=bundle.pos_y)
      self.position[e] = pos
    if bundle.spawn_velocity:
      vel: ECSVelocity = new(dx=bundle.vel_dx, dy=bundle.vel_dy)
      self.velocity[e] = vel
    return e


def move_system(
  pos: ECSComponentTable[ECSPosition] @ref,
  vel: ECSComponentTable[ECSVelocity] @ref,
) -> None:
  for e in pos & vel:
    p: ECSPosition @ref = pos[e]
    v: ECSVelocity = vel[e]
    p.x += v.dx
    p.y += v.dy


class EcsCreateTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    w: ECSWorld = new()
    e: ECSEntity = w.create(
      new(
        spawn_position=1,
        pos_x=3,
        pos_y=4,
        spawn_velocity=1,
        vel_dx=1,
        vel_dy=2,
      ),
    )
    self.assertTrue(w.is_alive(e))
    self.assertTrue(e in w.position)
    self.assertTrue(e in w.velocity)
    self.assertEqual(w.position[e].x, 3)
    self.assertEqual(w.position[e].y, 4)


class EcsInlineMakeTests(TestCaseMixin):
  _test_tag = 15

  @override
  def test(self):
    w: ECSWorld = new()
    bundle: ECSSpawnComponents = new(spawn_position=1, pos_x=5, pos_y=6)
    e: ECSEntity = w.create(bundle)
    self.assertEqual(w.position[e].x, 5)


class EcsSystemTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    w: ECSWorld = new()
    bundle: ECSSpawnComponents = new(
      spawn_position=1,
      pos_x=0,
      pos_y=0,
      spawn_velocity=1,
      vel_dx=2,
      vel_dy=3,
    )
    e: ECSEntity = w.create(bundle)
    move_system(w.position, w.velocity)
    self.assertEqual(w.position[e].x, 2)
    self.assertEqual(w.position[e].y, 3)


class EcsDestroyTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    w: ECSWorld = new()
    bundle: ECSSpawnComponents = new(spawn_position=1, pos_x=1, pos_y=1)
    e: ECSEntity = w.create(bundle)
    w.destroy(e)
    self.assertFalse(w.is_alive(e))
    self.assertFalse(e in w.position)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
