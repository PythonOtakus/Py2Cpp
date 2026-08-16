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

  spawnPosition: int = 0
  posX: int = 0
  posY: int = 0
  spawnVelocity: int = 0
  velDx: int = 0
  velDy: int = 0


class ECSWorld(ECSWorldMixin):
  """演示 World：``Position`` / ``Velocity`` 组件表。"""

  position: ECSComponentTable[ECSPosition] @property = new()
  velocity: ECSComponentTable[ECSVelocity] @property = new()

  def create(self, bundle: ECSSpawnComponents) -> ECSEntity:
    e: ECSEntity = self._allocEntity()
    if bundle.spawnPosition:
      self.position[e] = new(x=bundle.posX, y=bundle.posY)
    if bundle.spawnVelocity:
      self.velocity[e] = new(dx=bundle.velDx, dy=bundle.velDy)
    return e


def moveSystem(
  pos: ECSComponentTable[ECSPosition] @ref,
  vel: ECSComponentTable[ECSVelocity] @ref,
) -> None:
  for e in pos & vel:
    p: ECSPosition @ref = pos[e]
    v: ECSVelocity = vel[e]
    p.x += v.dx
    p.y += v.dy


class EcsCreateTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    w: ECSWorld = new()
    e: ECSEntity = w.create(
      new(
        spawnPosition=1,
        posX=3,
        posY=4,
        spawnVelocity=1,
        velDx=1,
        velDy=2,
      ),
    )
    self.assertTrue(w.isAlive(e))
    self.assertTrue(e in w.position)
    self.assertTrue(e in w.velocity)
    self.assertEqual(w.position[e].x, 3)
    self.assertEqual(w.position[e].y, 4)


class EcsInlineMakeTests(TestCaseMixin):
  _testTag = 15

  @override
  def test(self):
    w: ECSWorld = new()
    bundle: ECSSpawnComponents = new(spawnPosition=1, posX=5, posY=6)
    e: ECSEntity = w.create(bundle)
    self.assertEqual(w.position[e].x, 5)


class EcsSystemTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    w: ECSWorld = new()
    bundle: ECSSpawnComponents = new(
      spawnPosition=1,
      posX=0,
      posY=0,
      spawnVelocity=1,
      velDx=2,
      velDy=3,
    )
    e: ECSEntity = w.create(bundle)
    moveSystem(w.position, w.velocity)
    self.assertEqual(w.position[e].x, 2)
    self.assertEqual(w.position[e].y, 3)


class EcsDestroyTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    w: ECSWorld = new()
    bundle: ECSSpawnComponents = new(spawnPosition=1, posX=1, posY=1)
    e: ECSEntity = w.create(bundle)
    w.destroy(e)
    self.assertFalse(w.isAlive(e))
    self.assertFalse(e in w.position)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
