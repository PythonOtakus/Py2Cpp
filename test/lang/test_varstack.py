"""``VarStack`` + ``Self.iterFields``：mixin 内 ``push`` / ``new(*s)`` / ``fn(*s)`` 译期展开。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import almost, lerp
from py2cpp.spatial.vector import Vector2, Vector3, Vector4

@mixin
class VarStackMixin:
    """专用 mixin：演示 ``VarStack`` 在 Vector2/3 维宿主上的展开。"""

    @staticproperty
    @immutable
    def filled() -> Self:
        vs: VarStack = new()
        for f in Self.iterFields(publicOnly=True):
            vs.push(1.0)
        return new(*vs)

    @immutable
    def summed(self, other: Self) -> Self:
        vs: VarStack = new()
        for f in Self.iterFields(publicOnly=True):
            vs.push(getattr(self, f) + getattr(other, f))
        return new(*vs)

    @immutable
    def copied(self) -> Self:
        vs: VarStack = new()
        for f in Self.iterFields(publicOnly=True):
            vs.push(getattr(self, f))
        return new(*vs)

    @immutable
    def delta(self, other: Self) -> Self:
        vs: VarStack = new()
        for f in Self.iterFields(publicOnly=True):
            vs.push(getattr(other, f) - getattr(self, f))
        return new(*vs)

    @staticmethod
    @immutable
    def lerpPair(a: Self, b: Self, t: float64) -> Self:
        vs: VarStack = new()
        for f in Self.iterFields(publicOnly=True):
            vs.push(lerp(getattr(a, f), getattr(b, f), t))
        return new(*vs)

    @immutable
    def replaceTail(self, tail: float64) -> Self:
        vs: VarStack = new()
        for f in Self.iterFields(publicOnly=True):
            vs.push(getattr(self, f))
        _: float64 = vs.pop()
        vs.push(tail)
        return new(*vs)

@mixin
class VarStackPopMixin:
    """三维宿主专用：``pop`` 后 ``*vs`` 仍至少剩两分量。"""

    @immutable
    def sumExceptLast(self) -> float64:
        vs: VarStack = new()
        for f in Self.iterFields(publicOnly=True):
            vs.push(getattr(self, f))
        vs.pop()
        return sum2(*vs)

@mixin
class VarStackTopMixin:
    """``top()`` 可在 ``if`` 等内层作用域读取栈顶。"""

    @immutable
    def peekTop(self) -> float64:
        vs: VarStack = new()
        for f in Self.iterFields(publicOnly=True):
            vs.push(getattr(self, f))
        top: float64 = 0.0
        if self:
            top = vs.top()
        return top

def sum2(a: float64, b: float64) -> float64:
    return a + b

@copyable
@dataclass(eq=False, repr=False)
class Vec2Stack(VarStackMixin):
    x: float64 = 0.0
    y: float64 = 0.0

@copyable
@dataclass(eq=False, repr=False)
class Vec3Stack(VarStackMixin, VarStackPopMixin, VarStackTopMixin):
    x: float64 = 0.0
    y: float64 = 0.0
    z: float64 = 0.0

class MixinFilledVec2Tests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        v: Vec2Stack = Vec2Stack.filled
        self.assertTrue(almost(v.x, 1.0))
        self.assertTrue(almost(v.y, 1.0))

class MixinFilledVec3Tests(TestCaseMixin):
    _testTag = 2

    @override
    def test(self):
        v: Vec3Stack = Vec3Stack.filled
        self.assertTrue(almost(v.x, 1.0))
        self.assertTrue(almost(v.y, 1.0))
        self.assertTrue(almost(v.z, 1.0))

class MixinSummedVec2Tests(TestCaseMixin):
    _testTag = 3

    @override
    def test(self):
        a: Vec2Stack = new(1.0, 2.0)
        s: Vec2Stack = a.summed(Vec2Stack(3.0, 4.0))
        self.assertTrue(almost(s.x, 4.0))
        self.assertTrue(almost(s.y, 6.0))

class MixinDualStackVec2Tests(TestCaseMixin):
    _testTag = 4

    @override
    def test(self):
        a: Vec2Stack = new(1.0, 2.0)
        b: Vec2Stack = new(5.0, 8.0)
        c: Vec2Stack = a.copied()
        d: Vec2Stack = a.delta(b)
        self.assertTrue(almost(c.x, 1.0))
        self.assertTrue(almost(c.y, 2.0))
        self.assertTrue(almost(d.x, 4.0))
        self.assertTrue(almost(d.y, 6.0))

class MixinLerpPairVec2Tests(TestCaseMixin):
    _testTag = 5

    @override
    def test(self):
        a: Vec2Stack = new(0.0, 10.0)
        b: Vec2Stack = new(10.0, 0.0)
        m: Vec2Stack = new.lerpPair(a, b, 0.25)
        self.assertTrue(almost(m.x, 2.5))
        self.assertTrue(almost(m.y, 7.5))

class MixinPopReplaceTailVec2Tests(TestCaseMixin):
    _testTag = 6

    @override
    def test(self):
        v: Vec2Stack = new(1.0, 2.0)
        r: Vec2Stack = v.replaceTail(9.0)
        self.assertTrue(almost(r.x, 1.0))
        self.assertTrue(almost(r.y, 9.0))

class MixinPopUnpackVec3Tests(TestCaseMixin):
    _testTag = 7

    @override
    def test(self):
        v: Vec3Stack = new(1.0, 2.0, 30.0)
        s: float64 = v.sumExceptLast()
        self.assertTrue(almost(s, 3.0))

class MixinTopInnerScopeVec3Tests(TestCaseMixin):
    _testTag = 8

    @override
    def test(self):
        v: Vec3Stack = new(1.0, 2.0, 30.0)
        t: float64 = v.peekTop()
        self.assertTrue(almost(t, 30.0))

class SpatialVector2ZeroTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        z: Vector2 = Vector2.zero
        self.assertTrue(almost(z.x, 0.0))
        self.assertTrue(almost(z.y, 0.0))
        self.assertFalse(z)

class SpatialVector3AddTests(TestCaseMixin):
    _testTag = 11

    @override
    def test(self):
        a: Vector3 = new(1.0, 2.0, 3.0)
        b: Vector3 = new(4.0, 5.0, 6.0)
        s: Vector3 = a + b
        self.assertTrue(almost(s.x, 5.0))
        self.assertTrue(almost(s.y, 7.0))
        self.assertTrue(almost(s.z, 9.0))

class SpatialVector4NegTests(TestCaseMixin):
    _testTag = 12

    @override
    def test(self):
        v: Vector4 = new(1.0, -2.0, 3.0, -4.0)
        n: Vector4 = -v
        self.assertTrue(almost(n.x, -1.0))
        self.assertTrue(almost(n.y, 2.0))
        self.assertTrue(almost(n.z, -3.0))
        self.assertTrue(almost(n.w, 4.0))

class SpatialVector3LerpTests(TestCaseMixin):
    _testTag = 13

    @override
    def test(self):
        a: Vector3 = new(0.0, 0.0, 0.0)
        m: Vector3 = a.lerp(Vector3(10.0, 20.0, 30.0), 0.5)
        self.assertTrue(almost(m.x, 5.0))
        self.assertTrue(almost(m.y, 10.0))
        self.assertTrue(almost(m.z, 15.0))

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
