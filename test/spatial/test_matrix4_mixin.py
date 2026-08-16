"""Matrix4 mixin 回归（``getAxis`` / ``setAxis`` / ``applyToPoint``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import almost
from py2cpp.spatial.matrix import Matrix4
from py2cpp.spatial.vector import Vector3

class FromPositionTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        m: Matrix4 = new.fromPosition(Vector3(1.0, 2.0, 3.0))
        p: Vector3 = m.applyToPoint(Vector3(0.0, 0.0, 0.0))
        self.assertTrue(almost(p.x, 1.0))
        self.assertTrue(almost(p.y, 2.0))
        self.assertTrue(almost(p.z, 3.0))

class GetSetAxisTests(TestCaseMixin):
    _testTag = 2

    @override
    def test(self):
        m: Matrix4 = new()
        m.setAxis(3, Vector3(4.0, 5.0, 6.0))
        got: Vector3 = m.getAxis(3)
        self.assertTrue(almost(got.x, 4.0))
        self.assertTrue(almost(got.y, 5.0))
        self.assertTrue(almost(got.z, 6.0))
        self.assertTrue(almost(m.position.x, 4.0))
        m.setAxis(2, Vector3(0.1, 0.2, 0.3))
        ax: Vector3 = m.zAxis
        self.assertTrue(almost(ax.x, 0.1))
        self.assertTrue(almost(ax.y, 0.2))
        self.assertTrue(almost(ax.z, 0.3))

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
