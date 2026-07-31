"""``py2cpp.spatial.color``：``Color`` / ``ColorMatrix``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import almost
from py2cpp.spatial.color import Color, ColorMatrix

class ColorBasicTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        c: Color = new(1.5, -0.5, 0.25, 0.5)
        self.assertTrue(almost(c.r, 1.0))
        self.assertTrue(almost(c.g, 0.0))
        self.assertTrue(almost(c.b, 0.25))
        self.assertTrue(almost(c.a, 0.5))
        self.assertTrue(c)
        self.assertFalse(Color.clear)
        white: Color = new.white
        mid: Color = new.black.lerp(white, 0.5)
        self.assertTrue(almost(mid.r, 0.5))
        self.assertTrue(almost(mid.g, 0.5))
        self.assertTrue(almost(mid.b, 0.5))
        faded: Color = white.with_alpha(0.25)
        self.assertTrue(almost(faded.a, 0.25))
        red: Color = new(1.0, 0.0, 0.0, 1.0)
        packed: int = red.to_argb()
        back: Color = new.from_argb(packed)
        self.assertTrue(almost(back.r, 1.0))
        self.assertTrue(almost(back.g, 0.0))
        self.assertTrue(almost(back.b, 0.0))
        self.assertTrue(almost(back.a, 1.0))

class ColorOpsTests(TestCaseMixin):
    _test_tag = 2

    @override
    def test(self):
        a: Color = new(0.2, 0.4, 0.6, 0.8)
        b: Color = new(0.5, 0.1, 0.3, 0.5)
        summed: Color = a + b
        self.assertTrue(almost(summed.r, 0.7))
        self.assertTrue(almost(summed.g, 0.5))
        muted: Color = a & b
        self.assertTrue(almost(muted.r, 0.2))
        self.assertTrue(almost(muted.g, 0.1))
        bright: Color = a | b
        self.assertTrue(almost(bright.r, 0.5))
        self.assertTrue(almost(bright.g, 0.4))
        had: Color = a * b
        self.assertTrue(almost(had.r, 0.1))
        self.assertTrue(almost(had.g, 0.04))
        scaled: Color = a * 0.5
        self.assertTrue(almost(scaled.r, 0.1))
        inv: Color = ~a
        self.assertTrue(almost(inv.r, 0.8))
        self.assertTrue(almost(inv.a, 0.2))
        self.assertTrue(a @ b == a * b)

class ColorMatrixTests(TestCaseMixin):
    _test_tag = 3

    @override
    def test(self):
        c: Color = new(0.2, 0.4, 0.6, 1.0)
        ident: ColorMatrix = new.identity
        out: Color = ident.apply(c)
        self.assertTrue(almost(out.r, 0.2))
        self.assertTrue(almost(out.g, 0.4))
        self.assertTrue(almost(out.b, 0.6))
        gray_m: ColorMatrix = new.grayscale()
        g: Color = gray_m.apply(c)
        self.assertTrue(almost(g.r, g.g))
        self.assertTrue(almost(g.g, g.b))
        self.assertFalse(ColorMatrix.zero)
        back: ColorMatrix = ~ident
        self.assertTrue(back @ ident == ident)
        self.assertTrue(almost(abs(ident), 1.0))
        sq: ColorMatrix = ident ** 2.0
        self.assertTrue(sq == ident)

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
