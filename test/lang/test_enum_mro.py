"""``@enum.mro``、``__id__`` / ``__class_id__``、``of`` / ``create``（模块内自建 MRO，勿依赖 ``ExcTypeUnion``）。"""
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
class PetKindTypeEnum(base=Animal):
    Other = -1

def classify(p: Animal) -> PetKindTypeEnum:
    return PetKindTypeEnum.of(p)

def makeDog() -> Animal:
    return PetKindTypeEnum.create(PetKindTypeEnum.Dog)

class EnumMroIdTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        d: Dog = new()
        self.assertEqual(d.__class_id__, Dog.__id__)
        self.assertEqual(classify(d), PetKindTypeEnum.Dog)
        made: Animal = makeDog()
        self.assertTrue(made)
        w: Plain = new()
        self.assertTrue(w.__class_id__ == Plain.__id__)

class EnumMroEnumTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        self.assertEqual(classify(Cat()), PetKindTypeEnum.Cat)
        self.assertTrue(PetKindTypeEnum.Other != PetKindTypeEnum.Dog)
        self.assertEqual(str(PetKindTypeEnum.Dog), 'PetKindTypeEnum.Dog')
        self.assertEqual(repr(PetKindTypeEnum.Other), '<PetKindTypeEnum.Other: -1>')

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
