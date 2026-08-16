"""游戏向 ``py2cpp.spatial`` 几何数学回归（``Vector`` / ``Rotator`` / ``Matrix``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import clamp, almost, lerp, smoothStep
from py2cpp.spatial.matrix import Matrix3, Matrix4
from py2cpp.spatial.rotator import Quaternion, Rotator
from py2cpp.spatial.vector import Vector2, Vector3


class MathScalarTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertTrue(almost(lerp(0.0, 10.0, 0.25), 2.5))
    self.assertTrue(almost(clamp(5.0, 0.0, 3.0), 3.0))
    self.assertTrue(almost(smoothStep(0.0, 1.0, 0.5), 0.5))


class Vector2Tests(TestCaseMixin):
  _testTag = 10

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
    self.assertTrue(almost(a.unsafeGet(0), 7.0))
    a.unsafeSet(1, 8.0)
    self.assertTrue(almost(a.y, 8.0))


class Vector3StorageTests(TestCaseMixin):
  _testTag = 11

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
    self.assertTrue(almost(v.unsafeGet(0), 1.0))
    v.unsafeSet(1, 9.0)
    self.assertTrue(almost(v.y, 9.0))


class RotatorTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    r: Rotator = new.fromAngle(90.0)
    v: Vector2 = new.right
    out: Vector2 = r * v
    self.assertTrue(almost(out.x, 0.0))
    self.assertTrue(almost(out.y, 1.0))
    self.assertEqual(len(r), 2)
    self.assertTrue(almost(r[0], r.w))
    self.assertTrue(almost(r[1], r.z))
    self.assertTrue(almost(r.unsafeGet(0), r.w))
    r.unsafeSet(1, 0.5)
    self.assertTrue(almost(r.z, 0.5))


class QuaternionUnsafeTests(TestCaseMixin):
  _testTag = 21

  @override
  def test(self):
    axis: Vector3 = new.forward
    q: Quaternion = new.fromAxisAngle(axis, 90.0)
    self.assertTrue(almost(q.unsafeGet(0), q.w))
    self.assertTrue(almost(q.unsafeGet(1), q.x))
    q.unsafeSet(2, 0.25)
    self.assertTrue(almost(q.y, 0.25))


class Matrix3Tests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    m: Matrix3 = new.fromPosition(Vector2(2.0, 3.0))
    p: Vector2 = new(1.0, 1.0)
    out: Vector2 = m.applyToPoint(p)
    self.assertTrue(almost(out.x, 3.0))
    self.assertTrue(almost(out.y, 4.0))
    opOut: Vector2 = m * p
    self.assertTrue(almost(opOut.x, 3.0))
    self.assertTrue(almost(opOut.y, 4.0))
    rot: Matrix3 = new.fromAngle(90.0)
    v: Vector2 = rot.applyToVector(new.right)
    self.assertTrue(almost(v.x, 0.0))
    self.assertTrue(almost(v.y, 1.0))
    rotV: Vector2 = rot * Vector2.right
    self.assertTrue(almost(rotV.x, 0.0))
    self.assertTrue(almost(rotV.y, 1.0))
    scaled: Matrix3 = m * 2.0
    self.assertTrue(almost(scaled[0, 0], 2.0))
    half: Matrix3 = m / 2.0
    self.assertTrue(almost(half[0, 0], 0.5))
    m /= 2.0
    self.assertTrue(almost(m[0, 0], 0.5))


class Matrix3AffineInvTests(TestCaseMixin):
  _testTag = 31

  @override
  def test(self):
    m: Matrix3 = new.fromPosition(Vector2(2.0, 3.0))
    self.assertTrue(m.isAffine())
    inv: Matrix3 = m.inv
    p: Vector2 = m.applyToPoint(Vector2(1.0, 1.0))
    back: Vector2 = inv.applyToPoint(p)
    self.assertTrue(almost(back.x, 1.0))
    self.assertTrue(almost(back.y, 1.0))


class Matrix4QuaternionTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    axisZ: Vector3 = new.forward
    axisX: Vector3 = new.right
    self.assertTrue(almost(axisZ.z, 1.0))
    self.assertTrue(almost(axisX.x, 1.0))
    d: Vector3 = new.down
    self.assertTrue(almost(d.y, 1.0))
    q: Quaternion = new.fromAxisAngle(axisZ, 90.0)
    v: Vector3 = axisX
    out: Vector3 = q * v
    self.assertTrue(almost(out.x, 0.0))
    self.assertTrue(almost(out.y, 1.0))
    m2: Matrix4 = new.fromPosition(Vector3(1.0, 2.0, 3.0))
    self.assertTrue(m2.isAffine())
    inv4: Matrix4 = m2.inv
    p2: Vector3 = m2.applyToPoint(Vector3(0.5, 0.5, 0.5))
    back2: Vector3 = inv4.applyToPoint(p2)
    self.assertTrue(almost(back2.x, 0.5))
    self.assertTrue(almost(back2.y, 0.5))
    self.assertTrue(almost(back2.z, 0.5))
    m: Matrix4 = m2
    p: Vector3 = m.applyToPoint(Vector3(0.0, 0.0, 0.0))
    self.assertTrue(almost(p.x, 1.0))
    self.assertTrue(almost(p.y, 2.0))
    self.assertTrue(almost(p.z, 3.0))
    opP: Vector3 = m * Vector3(0.0, 0.0, 0.0)
    self.assertTrue(almost(opP.x, 1.0))
    self.assertTrue(almost(opP.y, 2.0))
    self.assertTrue(almost(opP.z, 3.0))
    scaled4: Matrix4 = m * 4.0
    self.assertTrue(almost(scaled4[0, 0], 4.0))
    half4: Matrix4 = scaled4 / 2.0
    self.assertTrue(almost(half4[0, 0], 2.0))


class SpatialOperatorTests(TestCaseMixin):
  _testTag = 50

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
    crossZ: float64 = rx @ ry
    crossZRev: float64 = ry @ rx
    self.assertTrue(almost(crossZ, -crossZRev))
    u: Vector3 = Vector3.right
    v: Vector3 = Vector3.forward
    u @= v
    self.assertTrue(almost(u.y, -1.0))
    r: Rotator = new.fromAngle(90.0)
    mag0: float64 = abs(r)
    half: Rotator = r / 2.0
    self.assertTrue(almost(abs(half), mag0 * 0.5))
    r /= 2.0
    self.assertTrue(almost(abs(r), mag0 * 0.5))
    comp: Rotator = new.fromAngle(90.0)
    comp2: Rotator = new.fromAngle(90.0)
    comp @= comp2
    compV: Vector2 = comp * Vector2.right
    self.assertTrue(almost(compV.x, -1.0))
    self.assertTrue(almost(compV.y, 0.0))
    m: Matrix3 = new.fromAngle(90.0)
    doubled: Matrix3 = 2.0 * m
    self.assertTrue(almost(doubled[0, 0], 0.0))
    ma: Matrix3 = new()
    ma[0, 0] = 5.0
    mb: Matrix3 = new()
    mb[0, 0] = 2.0
    ma -= mb
    self.assertTrue(almost(ma[0, 0], 3.0))
    rotA: Matrix3 = new.fromAngle(90.0)
    rotB: Matrix3 = new.fromAngle(90.0)
    rotA @= rotB
    out: Vector2 = rotA * Vector2.right
    self.assertTrue(almost(out.x, -1.0))
    self.assertTrue(almost(out.y, 0.0))
    q: Quaternion = new.fromAxisAngle(Vector3.forward, 90.0)
    q2: Quaternion = new.fromAxisAngle(Vector3.forward, 90.0)
    q @= q2
    qv: Vector3 = q * Vector3.right
    self.assertTrue(almost(qv.x, -1.0))
    self.assertTrue(almost(qv.y, 0.0))
    q3: Quaternion = new.fromAxisAngle(Vector3.forward, 90.0)
    w0: float64 = q3.w
    q3 *= 2.0
    self.assertTrue(almost(q3.w, w0 * 2.0))


class MatrixPowerTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    m: Matrix3 = new.fromAngle(30.0)
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
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
