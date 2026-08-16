"""``is`` / ``is not`` 对象身份比较（非 ``==`` 值相等）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class Widget:

    def __init__(self, tag: int):
        self.tag: int = tag

def sameVariable(w: Widget) -> bool:
    return w is w

def copyNotSame(src: Widget) -> bool:
    other: Widget = src
    return src is other

def aliasSame(a: Widget, b: Widget) -> bool:
    return a is b

class IsIdentityTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        w: Widget = new(Widget(1))
        self.assertTrue(sameVariable(w))
        self.assertFalse(copyNotSame(w))
        self.assertTrue(aliasSame(w, w))
        self.assertFalse(aliasSame(w, Widget(1)))

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
