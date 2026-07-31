"""Matrix4 mixin 回归（``get_axis`` / ``set_axis`` / ``apply_to_point``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import almost
from py2cpp.spatial.matrix import Matrix4
from py2cpp.spatial.vector import Vector3

class FromPositionTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        m: Matrix4 = new.from_position(Vector3(1.0, 2.0, 3.0))
        p: Vector3 = m.apply_to_point(Vector3(0.0, 0.0, 0.0))
        self.assertTrue(almost(p.x, 1.0))
        self.assertTrue(almost(p.y, 2.0))
        self.assertTrue(almost(p.z, 3.0))

class GetSetAxisTests(TestCaseMixin):
    _test_tag = 2

    @override
    def test(self):
        m: Matrix4 = new()
        m.set_axis(3, Vector3(4.0, 5.0, 6.0))
        got: Vector3 = m.get_axis(3)
        self.assertTrue(almost(got.x, 4.0))
        self.assertTrue(almost(got.y, 5.0))
        self.assertTrue(almost(got.z, 6.0))
        self.assertTrue(almost(m.position.x, 4.0))
        m.set_axis(2, Vector3(0.1, 0.2, 0.3))
        ax: Vector3 = m.z_axis
        self.assertTrue(almost(ax.x, 0.1))
        self.assertTrue(almost(ax.y, 0.2))
        self.assertTrue(almost(ax.z, 0.3))

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
