"""``@union.mro``、嵌套 ``Enum``、``__enum__``、``Enum.of`` / ``Enum.create``（模块内自建，勿依赖 ``ExcTypeUnion``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.exceptions import Exception

class LocalError(Exception):
    pass

class AlphaError(LocalError):
    pass

class BetaError(LocalError):
    pass

@union.mro
class ErrorTypeUnion(base=Exception):

    @variant
    class Unknown:
        pass

def classify(e: Exception) -> ErrorTypeUnion.Enum:
    return ErrorTypeUnion.Enum.of(e)

def makeAlpha() -> AlphaError:
    return new()

def slotTag(slot: ErrorTypeUnion) -> int:
    if slot.__enum__ == ErrorTypeUnion.Enum.AlphaError:
        return 1
    if slot.__enum__ == ErrorTypeUnion.Enum.BetaError:
        return 2
    return 0

class UnionMroEnumTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        self.assertEqual(classify(AlphaError()), ErrorTypeUnion.Enum.AlphaError)
        made: AlphaError = makeAlpha()
        self.assertEqual(ErrorTypeUnion.Enum.of(made), ErrorTypeUnion.Enum.AlphaError)
        created: Exception = ErrorTypeUnion.Enum.create(ErrorTypeUnion.Enum.AlphaError)
        self.assertTrue(created)
        self.assertEqual(str(ErrorTypeUnion.Enum.BetaError), 'ErrorTypeUnion.Enum.BetaError')
        self.assertEqual(repr(ErrorTypeUnion.Enum.Unknown), '<ErrorTypeUnion.Enum.Unknown: -1>')

class UnionMroDunderTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        ae: AlphaError = new()
        sa: ErrorTypeUnion = new.AlphaError(ae)
        self.assertEqual(slotTag(sa), 1)
        be: BetaError = new()
        sb: ErrorTypeUnion = new.BetaError(be)
        self.assertEqual(slotTag(sb), 2)
        self.assertEqual(sa.__enum__, ErrorTypeUnion.Enum.AlphaError)
        self.assertTrue(sb.__enum__ != sa.__enum__)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
