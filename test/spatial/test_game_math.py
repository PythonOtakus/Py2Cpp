"""游戏向 ``py2cpp.spatial`` 几何数学回归（``Vector`` / ``Rotator`` / ``Matrix``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import clamp, almost, lerp, smooth_step
from py2cpp.spatial.matrix import Matrix3, Matrix4
from py2cpp.spatial.rotator import Quaternion, Rotator
from py2cpp.spatial.vector import Vector2, Vector3


class MathScalarTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertTrue(almost(lerp(0.0, 10.0, 0.25), 2.5))
    self.assertTrue(almost(clamp(5.0, 0.0, 3.0), 3.0))
    self.assertTrue(almost(smooth_step(0.0, 1.0, 0.5), 0.5))


class Vector2Tests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    r: Vector2 = new.right
    d: Vector2 = new.down
    self.assertTrue(almost(r.x, 1.0))
    self.assertTrue(almost(r.y, 0.0))
    self.assertTrue(almost(d.x, 0.0))
    self.assertTrue(almost(d.y, 1.0))
    a: Vector2 = new(3.0, 4.0)
    b: Vector2 = new.right
    self.assertTrue(almost(a * b, 3.0))
    self.assertTrue(almost(a @ b, -4.0))
    self.assertTrue(almost(abs(a), 5.0))
    self.assertTrue(almost((a ^ Vector2.zero), 5.0))
    r: Vector2 = a.rotated90()
    self.assertTrue(almost(r.x, -4.0))
    self.assertTrue(almost(r.y, 3.0))
    self.assertEqual(len(a), 2)
    self.assertTrue(almost(a[0], 3.0))
    self.assertTrue(almost(a[1], 4.0))
    a[1] = 5.0
    self.assertTrue(almost(a.y, 5.0))
    a.x = 7.0
    self.assertTrue(almost(a[0], 7.0))
    self.assertTrue(almost(a.unsafe_get(0), 7.0))
    a.unsafe_set(1, 8.0)
    self.assertTrue(almost(a.y, 8.0))


class Vector3StorageTests(TestCaseMixin):
  _test_tag = 11

  @override
  def test(self):
    v: Vector3 = new(1.0, 2.0, 3.0)
    self.assertEqual(len(v), 3)
    self.assertTrue(almost(v[0], 1.0))
    self.assertTrue(almost(v.z, 3.0))
    v[2] = 4.0
    self.assertTrue(almost(v.z, 4.0))
    u: Vector3 = v
    self.assertTrue(almost(u.x, 1.0))
    self.assertTrue(almost(u.y, 2.0))
    self.assertTrue(almost(u.z, 4.0))
    self.assertTrue(almost(v.unsafe_get(0), 1.0))
    v.unsafe_set(1, 9.0)
    self.assertTrue(almost(v.y, 9.0))


class RotatorTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    r: Rotator = new.from_angle(90.0)
    v: Vector2 = new.right
    out: Vector2 = r * v
    self.assertTrue(almost(out.x, 0.0))
    self.assertTrue(almost(out.y, 1.0))
    self.assertEqual(len(r), 2)
    self.assertTrue(almost(r[0], r.w))
    self.assertTrue(almost(r[1], r.z))
    self.assertTrue(almost(r.unsafe_get(0), r.w))
    r.unsafe_set(1, 0.5)
    self.assertTrue(almost(r.z, 0.5))


class QuaternionUnsafeTests(TestCaseMixin):
  _test_tag = 21

  @override
  def test(self):
    axis: Vector3 = new.forward
    q: Quaternion = new.from_axis_angle(axis, 90.0)
    self.assertTrue(almost(q.unsafe_get(0), q.w))
    self.assertTrue(almost(q.unsafe_get(1), q.x))
    q.unsafe_set(2, 0.25)
    self.assertTrue(almost(q.y, 0.25))


class Matrix3Tests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    m: Matrix3 = new.from_position(Vector2(2.0, 3.0))
    p: Vector2 = new(1.0, 1.0)
    out: Vector2 = m.apply_to_point(p)
    self.assertTrue(almost(out.x, 3.0))
    self.assertTrue(almost(out.y, 4.0))
    op_out: Vector2 = m * p
    self.assertTrue(almost(op_out.x, 3.0))
    self.assertTrue(almost(op_out.y, 4.0))
    rot: Matrix3 = new.from_angle(90.0)
    v: Vector2 = rot.apply_to_vector(new.right)
    self.assertTrue(almost(v.x, 0.0))
    self.assertTrue(almost(v.y, 1.0))
    rot_v: Vector2 = rot * Vector2.right
    self.assertTrue(almost(rot_v.x, 0.0))
    self.assertTrue(almost(rot_v.y, 1.0))
    scaled: Matrix3 = m * 2.0
    self.assertTrue(almost(scaled[0, 0], 2.0))
    half: Matrix3 = m / 2.0
    self.assertTrue(almost(half[0, 0], 0.5))
    m /= 2.0
    self.assertTrue(almost(m[0, 0], 0.5))


class Matrix3AffineInvTests(TestCaseMixin):
  _test_tag = 31

  @override
  def test(self):
    m: Matrix3 = new.from_position(Vector2(2.0, 3.0))
    self.assertTrue(m.is_affine())
    inv: Matrix3 = m.inv
    p: Vector2 = m.apply_to_point(Vector2(1.0, 1.0))
    back: Vector2 = inv.apply_to_point(p)
    self.assertTrue(almost(back.x, 1.0))
    self.assertTrue(almost(back.y, 1.0))


class Matrix4QuaternionTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    axis_z: Vector3 = new.forward
    axis_x: Vector3 = new.right
    self.assertTrue(almost(axis_z.z, 1.0))
    self.assertTrue(almost(axis_x.x, 1.0))
    d: Vector3 = new.down
    self.assertTrue(almost(d.y, 1.0))
    q: Quaternion = new.from_axis_angle(axis_z, 90.0)
    v: Vector3 = axis_x
    out: Vector3 = q * v
    self.assertTrue(almost(out.x, 0.0))
    self.assertTrue(almost(out.y, 1.0))
    m2: Matrix4 = new.from_position(Vector3(1.0, 2.0, 3.0))
    self.assertTrue(m2.is_affine())
    inv4: Matrix4 = m2.inv
    p2: Vector3 = m2.apply_to_point(Vector3(0.5, 0.5, 0.5))
    back2: Vector3 = inv4.apply_to_point(p2)
    self.assertTrue(almost(back2.x, 0.5))
    self.assertTrue(almost(back2.y, 0.5))
    self.assertTrue(almost(back2.z, 0.5))
    m: Matrix4 = m2
    p: Vector3 = m.apply_to_point(Vector3(0.0, 0.0, 0.0))
    self.assertTrue(almost(p.x, 1.0))
    self.assertTrue(almost(p.y, 2.0))
    self.assertTrue(almost(p.z, 3.0))
    op_p: Vector3 = m * Vector3(0.0, 0.0, 0.0)
    self.assertTrue(almost(op_p.x, 1.0))
    self.assertTrue(almost(op_p.y, 2.0))
    self.assertTrue(almost(op_p.z, 3.0))
    scaled4: Matrix4 = m * 4.0
    self.assertTrue(almost(scaled4[0, 0], 4.0))
    half4: Matrix4 = scaled4 / 2.0
    self.assertTrue(almost(half4[0, 0], 2.0))


class SpatialOperatorTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    a: Vector2 = new(4.0, 6.0)
    b: Vector2 = new(1.0, 2.0)
    scaled: Vector2 = 2.0 * a
    self.assertTrue(almost(scaled.x, 8.0))
    self.assertTrue(almost(scaled.y, 12.0))
    a -= b
    self.assertTrue(almost(a.x, 3.0))
    self.assertTrue(almost(a.y, 4.0))
    rx: Vector2 = Vector2.right
    ry: Vector2 = Vector2.down
    cross_z: float64 = rx @ ry
    cross_z_rev: float64 = ry @ rx
    self.assertTrue(almost(cross_z, -cross_z_rev))
    u: Vector3 = Vector3.right
    v: Vector3 = Vector3.forward
    u @= v
    self.assertTrue(almost(u.y, -1.0))
    r: Rotator = new.from_angle(90.0)
    mag0: float64 = abs(r)
    half: Rotator = r / 2.0
    self.assertTrue(almost(abs(half), mag0 * 0.5))
    r /= 2.0
    self.assertTrue(almost(abs(r), mag0 * 0.5))
    comp: Rotator = new.from_angle(90.0)
    comp2: Rotator = new.from_angle(90.0)
    comp @= comp2
    comp_v: Vector2 = comp * Vector2.right
    self.assertTrue(almost(comp_v.x, -1.0))
    self.assertTrue(almost(comp_v.y, 0.0))
    m: Matrix3 = new.from_angle(90.0)
    doubled: Matrix3 = 2.0 * m
    self.assertTrue(almost(doubled[0, 0], 0.0))
    ma: Matrix3 = new()
    ma[0, 0] = 5.0
    mb: Matrix3 = new()
    mb[0, 0] = 2.0
    ma -= mb
    self.assertTrue(almost(ma[0, 0], 3.0))
    rot_a: Matrix3 = new.from_angle(90.0)
    rot_b: Matrix3 = new.from_angle(90.0)
    rot_a @= rot_b
    out: Vector2 = rot_a * Vector2.right
    self.assertTrue(almost(out.x, -1.0))
    self.assertTrue(almost(out.y, 0.0))
    q: Quaternion = new.from_axis_angle(Vector3.forward, 90.0)
    q2: Quaternion = new.from_axis_angle(Vector3.forward, 90.0)
    q @= q2
    qv: Vector3 = q * Vector3.right
    self.assertTrue(almost(qv.x, -1.0))
    self.assertTrue(almost(qv.y, 0.0))
    q3: Quaternion = new.from_axis_angle(Vector3.forward, 90.0)
    w0: float64 = q3.w
    q3 *= 2.0
    self.assertTrue(almost(q3.w, w0 * 2.0))


class MatrixPowerTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    m: Matrix3 = new.from_angle(30.0)
    back: Matrix3 = m.log().exp()
    self.assertTrue(back == m)
    sq: Matrix3 = m ** 2.0
    doubled: Matrix3 = m.ipow(2)
    self.assertTrue(sq == doubled)
    half: Matrix3 = m ** 0.5
    self.assertTrue(half @ half == m)
    mid: Matrix3 = new.identity
    inv: Matrix3 = m ** -1.0
    self.assertTrue(inv @ m == mid)
    id3: Matrix3 = m ** 0.0
    self.assertTrue(id3 == mid)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
