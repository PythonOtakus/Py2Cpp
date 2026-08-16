"""``@union`` / ``@variant`` 与 ``match``（绑定、``|``、关键字、字面量、guard）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

@union
class MessageUnion:

    @variant
    class Quit:
        pass

    @variant
    class Move:
        x: int
        y: int

    @variant
    class Write:
        s: str

@union
class SignalUnion:

    @variant
    class Ping:
        code: int

    @variant
    class Pong:
        code: int

def dispatch(msg: MessageUnion) -> int:
    match msg:
        case new.Quit:
            return 0
        case new.Move(x, y):
            return x + y
        case new.Write(s):
            return len(s)

def dispatchMoveX(msg: MessageUnion) -> int:
    match msg:
        case new.Move(x) if x > 0:
            return x
        case new.Move(x, y):
            return x + y
        case new.Quit:
            return -1
        case new.Write(s):
            return len(s)

def dispatchKw(msg: MessageUnion) -> int:
    match msg:
        case new.Move(x=ax, y=ay):
            return ax * 10 + ay
        case new.Write(s=text):
            return len(text)
        case new.Quit:
            return -1

def dispatchLit(msg: MessageUnion) -> int:
    match msg:
        case new.Move(1, y) if y > 0:
            return y * 10
        case new.Move(x, _) if x != 0:
            return x
        case new.Move(0, y):
            return y
        case new.Move(x, y):
            return x + y
        case new.Write(_):
            return 1
        case new.Quit:
            return 0

def dispatchOr(sig: SignalUnion) -> int:
    match sig:
        case new.Ping(code) | new.Pong(code):
            return code

def messageKind(msg: MessageUnion) -> int:
    match msg:
        case new.Quit:
            return 0
        case new.Move(_, _):
            return 1
        case new.Write(_):
            return 2

class UnionMatchTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        self.assertEqual(dispatch(MessageUnion.Quit()), 0)
        m: MessageUnion = new.Move(3, 4)
        self.assertEqual(dispatch(m), 7)
        self.assertEqual(dispatch(MessageUnion.Write('hi')), 2)
        m2: MessageUnion = m
        self.assertEqual(dispatch(m2), 7)
        self.assertEqual(dispatch(MessageUnion.Move(1, y=2)), 3)
        self.assertEqual(dispatchMoveX(MessageUnion.Move(5, 1)), 5)
        self.assertEqual(dispatchMoveX(MessageUnion.Move(-1, 2)), 1)

class UnionMatchOrTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        self.assertEqual(dispatchOr(SignalUnion.Ping(7)), 7)
        self.assertEqual(dispatchOr(SignalUnion.Pong(9)), 9)

class UnionEnumDunderTests(TestCaseMixin):
    _testTag = 15

    @override
    def test(self):
        q: MessageUnion = new.Quit()
        self.assertEqual(messageKind(q), 0)
        self.assertEqual(q.__enum__, MessageUnion.Enum.Quit)
        m: MessageUnion = new.Move(1, 2)
        self.assertEqual(messageKind(m), 1)
        self.assertEqual(m.__enum__, MessageUnion.Enum.Move)
        w: MessageUnion = new.Write('x')
        self.assertEqual(messageKind(w), 2)
        self.assertTrue(w.__enum__ != m.__enum__)

class UnionKeywordMatchTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        self.assertEqual(dispatchKw(MessageUnion.Move(2, 3)), 23)
        self.assertEqual(dispatchKw(MessageUnion.Write('ab')), 2)
        self.assertEqual(dispatchKw(MessageUnion.Quit()), -1)

class UnionLiteralWildcardTests(TestCaseMixin):
    _testTag = 30

    @override
    def test(self):
        self.assertEqual(dispatchLit(MessageUnion.Move(0, 5)), 5)
        self.assertEqual(dispatchLit(MessageUnion.Move(3, 4)), 3)
        self.assertEqual(dispatchLit(MessageUnion.Move(1, 4)), 40)
        self.assertEqual(dispatchLit(MessageUnion.Write('x')), 1)
        self.assertEqual(dispatchLit(MessageUnion.Quit()), 0)

@variant
class HasCode:
    code: int

@union
class CoreUnion:

    @variant
    class Quit:
        pass

    @variant
    class Ping(HasCode):
        pass

@union
class ExtendedUnion(CoreUnion):

    @variant
    class Write:
        s: str

def dispatchExt(msg: ExtendedUnion) -> int:
    match msg:
        case new.Quit:
            return 0
        case new.Ping(code):
            return code
        case new.Write(s):
            return len(s)

class UnionInheritTests(TestCaseMixin):
    _testTag = 40

    @override
    def test(self):
        self.assertEqual(dispatchExt(ExtendedUnion.Quit()), 0)
        self.assertEqual(dispatchExt(ExtendedUnion.Quit()), 0)
        self.assertEqual(dispatchExt(ExtendedUnion.Ping(9)), 9)
        self.assertEqual(dispatchExt(ExtendedUnion.Ping(3)), 3)
        self.assertEqual(dispatchExt(ExtendedUnion.Write('ab')), 2)

@union
class CoreTUnion[Element]:

    @variant
    class Unit:
        n: int

@union
class BoxTUnion[Element](CoreTUnion[Element]):

    @variant
    class Payload:
        s: str

def dispatchBox(msg: BoxTUnion[int]) -> int:
    match msg:
        case new.Unit(n):
            return n
        case new.Payload(s):
            return len(s)

class UnionGenericInheritTests(TestCaseMixin):
    _testTag = 50

    @override
    def test(self):
        self.assertEqual(dispatchBox(BoxTUnion[int].Unit(7)), 7)
        self.assertEqual(dispatchBox(BoxTUnion[int].Unit(5)), 5)
        self.assertEqual(dispatchBox(BoxTUnion[int].Payload('xy')), 2)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
