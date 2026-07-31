"""``@union`` / ``@variant`` 与 ``match``（绑定、``|``、关键字、字面量、guard）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

@union
class Message:

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
class Signal:

    @variant
    class Ping:
        code: int

    @variant
    class Pong:
        code: int

def dispatch(msg: Message) -> int:
    match msg:
        case new.Quit:
            return 0
        case new.Move(x, y):
            return x + y
        case new.Write(s):
            return len(s)

def dispatch_move_x(msg: Message) -> int:
    match msg:
        case new.Move(x) if x > 0:
            return x
        case new.Move(x, y):
            return x + y
        case new.Quit:
            return -1
        case new.Write(s):
            return len(s)

def dispatch_kw(msg: Message) -> int:
    match msg:
        case new.Move(x=ax, y=ay):
            return ax * 10 + ay
        case new.Write(s=text):
            return len(text)
        case new.Quit:
            return -1

def dispatch_lit(msg: Message) -> int:
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

def dispatch_or(sig: Signal) -> int:
    match sig:
        case new.Ping(code) | new.Pong(code):
            return code

def message_kind(msg: Message) -> int:
    match msg:
        case new.Quit:
            return 0
        case new.Move(_, _):
            return 1
        case new.Write(_):
            return 2

class UnionMatchTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        self.assertEqual(dispatch(Message.Quit()), 0)
        m: Message = new.Move(3, 4)
        self.assertEqual(dispatch(m), 7)
        self.assertEqual(dispatch(Message.Write('hi')), 2)
        m2: Message = m
        self.assertEqual(dispatch(m2), 7)
        self.assertEqual(dispatch(Message.Move(1, y=2)), 3)
        self.assertEqual(dispatch_move_x(Message.Move(5, 1)), 5)
        self.assertEqual(dispatch_move_x(Message.Move(-1, 2)), 1)

class UnionMatchOrTests(TestCaseMixin):
    _test_tag = 10

    @override
    def test(self):
        self.assertEqual(dispatch_or(Signal.Ping(7)), 7)
        self.assertEqual(dispatch_or(Signal.Pong(9)), 9)

class UnionEnumDunderTests(TestCaseMixin):
    _test_tag = 15

    @override
    def test(self):
        q: Message = new.Quit()
        self.assertEqual(message_kind(q), 0)
        self.assertEqual(q.__enum__, Message.Enum.Quit)
        m: Message = new.Move(1, 2)
        self.assertEqual(message_kind(m), 1)
        self.assertEqual(m.__enum__, Message.Enum.Move)
        w: Message = new.Write('x')
        self.assertEqual(message_kind(w), 2)
        self.assertTrue(w.__enum__ != m.__enum__)

class UnionKeywordMatchTests(TestCaseMixin):
    _test_tag = 20

    @override
    def test(self):
        self.assertEqual(dispatch_kw(Message.Move(2, 3)), 23)
        self.assertEqual(dispatch_kw(Message.Write('ab')), 2)
        self.assertEqual(dispatch_kw(Message.Quit()), -1)

class UnionLiteralWildcardTests(TestCaseMixin):
    _test_tag = 30

    @override
    def test(self):
        self.assertEqual(dispatch_lit(Message.Move(0, 5)), 5)
        self.assertEqual(dispatch_lit(Message.Move(3, 4)), 3)
        self.assertEqual(dispatch_lit(Message.Move(1, 4)), 40)
        self.assertEqual(dispatch_lit(Message.Write('x')), 1)
        self.assertEqual(dispatch_lit(Message.Quit()), 0)

@variant
class HasCode:
    code: int

@union
class Core:

    @variant
    class Quit:
        pass

    @variant
    class Ping(HasCode):
        pass

@union
class Extended(Core):

    @variant
    class Write:
        s: str

def dispatch_ext(msg: Extended) -> int:
    match msg:
        case new.Quit:
            return 0
        case new.Ping(code):
            return code
        case new.Write(s):
            return len(s)

class UnionInheritTests(TestCaseMixin):
    _test_tag = 40

    @override
    def test(self):
        self.assertEqual(dispatch_ext(Extended.Quit()), 0)
        self.assertEqual(dispatch_ext(Extended.Quit()), 0)
        self.assertEqual(dispatch_ext(Extended.Ping(9)), 9)
        self.assertEqual(dispatch_ext(Extended.Ping(3)), 3)
        self.assertEqual(dispatch_ext(Extended.Write('ab')), 2)

@union
class CoreT[T]:

    @variant
    class Unit:
        n: int

@union
class BoxT[T](CoreT[T]):

    @variant
    class Payload:
        s: str

def dispatch_box(msg: BoxT[int]) -> int:
    match msg:
        case new.Unit(n):
            return n
        case new.Payload(s):
            return len(s)

class UnionGenericInheritTests(TestCaseMixin):
    _test_tag = 50

    @override
    def test(self):
        self.assertEqual(dispatch_box(BoxT[int].Unit(7)), 7)
        self.assertEqual(dispatch_box(BoxT[int].Unit(5)), 5)
        self.assertEqual(dispatch_box(BoxT[int].Payload('xy')), 2)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
