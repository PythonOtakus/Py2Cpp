"""``is`` / ``is not`` 对象身份比较（非 ``==`` 值相等）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class Widget:

    def __init__(self, tag: int):
        self.tag: int = tag

def same_variable(w: Widget) -> bool:
    return w is w

def copy_not_same(src: Widget) -> bool:
    other: Widget = src
    return src is other

def alias_same(a: Widget, b: Widget) -> bool:
    return a is b

class IsIdentityTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        w: Widget = new(Widget(1))
        self.assertTrue(same_variable(w))
        self.assertFalse(copy_not_same(w))
        self.assertTrue(alias_same(w, w))
        self.assertFalse(alias_same(w, Widget(1)))

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
