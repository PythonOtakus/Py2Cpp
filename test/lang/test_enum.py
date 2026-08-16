"""``@enum`` 整型枚举（``...`` 顺延、``int``/``int64`` 底层、单继承、Flag 位运算与 match）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@enum
class ModeEnum:
  Off = 0
  On = ...
  Debug = ...


@enum
class WideEnum(int64):
  Lo = 1
  Hi = ...


@enum
class ExtEnum(ModeEnum):
  Extra = 10
  More = ...


@enum(flag=True)
class PermFlag:
  Read = ...
  Write = ...
  Exec = ...


@enum(flag=True)
class PermExtFlag(PermFlag):
  Admin = ...


def matchPermSingle(v: PermFlag) -> int:
  match v:
    case PermFlag.Read:
      return 1
    case PermFlag.Write:
      return 2
    case _:
      return 0


def matchPermFlags(v: PermFlag) -> int:
  match v:
    case PermFlag.Read | PermFlag.Write:
      return 3
    case PermFlag.Read:
      return 1
    case _:
      return 0


def countModes() -> int:
  n: int = 0
  for m in ModeEnum:
    n += 1
  return n


def firstMode() -> ModeEnum:
  first: ModeEnum = ModeEnum.Off
  for m in ModeEnum:
    first = m
    break
  return first


class EnumBasicTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertTrue(ModeEnum.On != ModeEnum.Off)
    self.assertTrue(ModeEnum.Debug != ModeEnum.On)
    lo: WideEnum = WideEnum.Lo
    self.assertTrue(lo == WideEnum.Lo)
    self.assertTrue(WideEnum.Hi != WideEnum.Lo)
    self.assertTrue(ExtEnum.On != ExtEnum.Off)
    self.assertTrue(ExtEnum.Off != ExtEnum.Extra)
    self.assertTrue(ExtEnum.More != ExtEnum.Extra)
    self.assertTrue(ExtEnum.On != ExtEnum.Extra)
    self.assertEqual(str(ModeEnum.On), "ModeEnum.On")
    self.assertEqual(repr(ModeEnum.On), "<ModeEnum.On: 1>")
    self.assertEqual(repr(ModeEnum.Off), "<ModeEnum.Off: 0>")


class EnumInheritTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    self.assertTrue(ExtEnum.Extra == ExtEnum.Extra)
    self.assertTrue(ExtEnum.More != ExtEnum.On)
    on: ExtEnum = ExtEnum.On
    self.assertTrue(on == ExtEnum.On)
    self.assertTrue(ExtEnum.Off != ExtEnum.On)


class EnumFlagTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    self.assertTrue(PermFlag.Read != PermFlag.Write)
    self.assertTrue(PermFlag.Write != PermFlag.Exec)
    self.assertTrue(PermFlag.Read != PermFlag.Exec)
    rw: PermFlag = PermFlag.Read
    self.assertTrue(rw == PermFlag.Read)
    self.assertTrue(PermExtFlag.Admin != PermExtFlag.Exec)
    self.assertTrue(PermExtFlag.Read == PermExtFlag.Read)
    both: PermFlag = PermFlag.Read | PermFlag.Write
    self.assertTrue(both != PermFlag.Read)
    self.assertTrue(both != PermFlag.Write)
    all3: PermFlag = PermFlag.Read | PermFlag.Write | PermFlag.Exec
    self.assertTrue(all3 != both)
    self.assertEqual(str(both), "PermFlag.Read|PermFlag.Write")
    self.assertEqual(repr(both), "<PermFlag.Read|PermFlag.Write: 3>")
    self.assertEqual(repr(PermFlag.Read), "<PermFlag.Read: 1>")


class EnumFlagMatchTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    self.assertEqual(matchPermSingle(PermFlag.Read), 1)
    self.assertEqual(matchPermSingle(PermFlag.Write), 2)
    self.assertEqual(matchPermSingle(PermFlag.Exec), 0)
    self.assertEqual(matchPermFlags(PermFlag.Read), 3)
    self.assertEqual(matchPermFlags(PermFlag.Write), 3)
    self.assertEqual(matchPermFlags(PermFlag.Read | PermFlag.Write), 0)


class EnumLenIterTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    self.assertEqual(len(ModeEnum), 3)
    self.assertEqual(len(ExtEnum), 5)
    self.assertEqual(len(PermFlag), 3)
    self.assertEqual(countModes(), 3)
    self.assertTrue(firstMode() == ModeEnum.Off)


class EnumIntCtorTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    self.assertEqual(int(ModeEnum.On), 1)
    self.assertTrue(ModeEnum(1) == ModeEnum.On)
    self.assertEqual(int(WideEnum.Lo), 1)
    self.assertTrue(WideEnum(1) == WideEnum.Lo)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
