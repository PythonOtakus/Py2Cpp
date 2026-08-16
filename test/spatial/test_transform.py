"""``py2cpp.spatial.transform``：``Transform2D`` / ``Transform3D`` 场景图。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import almost
from py2cpp.spatial.matrix import Matrix3
from py2cpp.spatial.rotator import Quaternion, Rotator
from py2cpp.spatial.transform import Transform2D, Transform3D
from py2cpp.spatial.vector import Vector2, Vector3

class Transform2DHierarchyTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        root: Transform2D = new('root')
        child: Transform2D = new('cam')
        child.parent = root
        self.assertEqual(child.parent.name, 'root')
        self.assertEqual(root.childCount, 1)
        self.assertEqual(root.root.name, 'root')
        self.assertEqual(child.root.name, 'root')
        found: Transform2D = root.find('cam')
        self.assertEqual(found.name, 'cam')
        child.parent = None
        self.assertTrue(child.parent is None)
        self.assertEqual(root.childCount, 0)

class Transform2DWorldTests(TestCaseMixin):
    _testTag = 2

    @override
    def test(self):
        root: Transform2D = new('root')
        root.localPosition = Vector2(10.0, 0.0)
        child: Transform2D = new('child')
        child.parent = root
        child.localPosition = Vector2(2.0, 3.0)
        world: Vector2 = child.position
        self.assertTrue(almost(world.x, 12.0))
        self.assertTrue(almost(world.y, 3.0))
        child.position = Vector2(20.0, 5.0)
        lp: Vector2 = child.localPosition
        self.assertTrue(almost(lp.x, 10.0))
        self.assertTrue(almost(lp.y, 5.0))
        out: Vector2 = child.localToWorldPoint(Vector2.right)
        self.assertTrue(almost(out.x, 21.0))
        self.assertTrue(almost(out.y, 5.0))

class Transform2DActionTests(TestCaseMixin):
    _testTag = 3

    @override
    def test(self):
        node: Transform2D = new('n')
        node.rotate(90.0)
        self.assertTrue(almost(node.angle, 90.0))
        node.translate(Vector2(1.0, 2.0))
        pos: Vector2 = node.position
        self.assertTrue(almost(pos.x, 1.0))
        self.assertTrue(almost(pos.y, 2.0))
        node.lookAt(Vector2(2.0, 2.0))
        self.assertTrue(almost(node.angle, 0.0))
        m: Matrix3 = node.localMatrix
        v: Vector2 = m.applyToVector(new.right)
        self.assertTrue(almost(v.x, 1.0))
        self.assertTrue(almost(v.y, 0.0))

class Transform3DWorldTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        root: Transform3D = new('root')
        root.localPosition = Vector3(1.0, 0.0, 0.0)
        child: Transform3D = new('child')
        child.parent = root
        child.localPosition = Vector3(0.0, 2.0, 0.0)
        world: Vector3 = child.position
        self.assertTrue(almost(world.x, 1.0))
        self.assertTrue(almost(world.y, 2.0))
        self.assertTrue(almost(world.z, 0.0))
        child.rotate(Vector3.forward, 90.0)
        fwd: Vector3 = child.forward
        self.assertTrue(almost(fwd.x, 0.0))
        self.assertTrue(almost(fwd.y, 0.0))
        self.assertTrue(almost(fwd.z, 1.0))

class Transform3DQuaternionTests(TestCaseMixin):
    _testTag = 11

    @override
    def test(self):
        node: Transform3D = new('n')
        axisZ: Vector3 = new.forward
        axisX: Vector3 = new.right
        node.rotation = new.fromAxisAngle(axisZ, 90.0)
        v: Vector3 = node.localToWorldVector(axisX)
        self.assertTrue(almost(v.x, 0.0))
        self.assertTrue(almost(v.y, 1.0))
        node.lookAt(Vector3(2.0, 0.0, 1.0))
        pos: Vector3 = node.position
        self.assertTrue(almost(pos.x, 0.0))
        self.assertTrue(almost(pos.y, 0.0))

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
