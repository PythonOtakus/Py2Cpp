"""``@enum.mro``、``__id__`` / ``__class_id__``、``of`` / ``create``（模块内自建 MRO，勿依赖 ``ExcSlot``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass

class Plain:
    pass

@enum.mro
class PetKind(base=Animal):
    OTHER = -1

def classify(p: Animal) -> PetKind:
    return PetKind.of(p)

def make_dog() -> Animal:
    return PetKind.create(PetKind.Dog)

class EnumMroIdTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        d: Dog = new()
        self.assertEqual(d.__class_id__, Dog.__id__)
        self.assertEqual(classify(d), PetKind.Dog)
        made: Animal = make_dog()
        self.assertTrue(made)
        w: Plain = new()
        self.assertTrue(w.__class_id__ == Plain.__id__)

class EnumMroEnumTests(TestCaseMixin):
    _test_tag = 10

    @override
    def test(self):
        self.assertEqual(classify(Cat()), PetKind.Cat)
        self.assertTrue(PetKind.OTHER != PetKind.Dog)
        self.assertEqual(str(PetKind.Dog), 'PetKind.Dog')
        self.assertEqual(repr(PetKind.OTHER), '<PetKind.OTHER: -1>')

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
