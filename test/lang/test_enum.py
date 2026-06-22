"""``@enum`` 整型枚举（``...`` 顺延、``int``/``int64`` 底层、单继承、Flag 位运算与 match）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@enum
class Mode:
  OFF = 0
  ON = ...
  DEBUG = ...


@enum
class Wide(int64):
  LO = 1
  HI = ...


@enum
class Ext(Mode):
  EXTRA = 10
  MORE = ...


@enum(flag=True)
class Perm:
  READ = ...
  WRITE = ...
  EXEC = ...


@enum(flag=True)
class PermExt(Perm):
  ADMIN = ...


def match_perm_single(v: Perm) -> int:
  match v:
    case Perm.READ:
      return 1
    case Perm.WRITE:
      return 2
    case _:
      return 0


def match_perm_flags(v: Perm) -> int:
  match v:
    case Perm.READ | Perm.WRITE:
      return 3
    case Perm.READ:
      return 1
    case _:
      return 0


def count_modes() -> int:
  n: int = 0
  for m in Mode:
    n += 1
  return n


def first_mode() -> Mode:
  first: Mode = Mode.OFF
  for m in Mode:
    first = m
    break
  return first


class EnumBasicTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertTrue(Mode.ON != Mode.OFF)
    self.assertTrue(Mode.DEBUG != Mode.ON)
    lo: Wide = Wide.LO
    self.assertTrue(lo == Wide.LO)
    self.assertTrue(Wide.HI != Wide.LO)
    self.assertTrue(Ext.ON != Ext.OFF)
    self.assertTrue(Ext.OFF != Ext.EXTRA)
    self.assertTrue(Ext.MORE != Ext.EXTRA)
    self.assertTrue(Ext.ON != Ext.EXTRA)
    self.assertEqual(str(Mode.ON), "Mode.ON")
    self.assertEqual(repr(Mode.ON), "<Mode.ON: 1>")
    self.assertEqual(repr(Mode.OFF), "<Mode.OFF: 0>")


class EnumInheritTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    self.assertTrue(Ext.EXTRA == Ext.EXTRA)
    self.assertTrue(Ext.MORE != Ext.ON)
    on: Ext = Ext.ON
    self.assertTrue(on == Ext.ON)
    self.assertTrue(Ext.OFF != Ext.ON)


class EnumFlagTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    self.assertTrue(Perm.READ != Perm.WRITE)
    self.assertTrue(Perm.WRITE != Perm.EXEC)
    self.assertTrue(Perm.READ != Perm.EXEC)
    rw: Perm = Perm.READ
    self.assertTrue(rw == Perm.READ)
    self.assertTrue(PermExt.ADMIN != PermExt.EXEC)
    self.assertTrue(PermExt.READ == PermExt.READ)
    both: Perm = Perm.READ | Perm.WRITE
    self.assertTrue(both != Perm.READ)
    self.assertTrue(both != Perm.WRITE)
    all3: Perm = Perm.READ | Perm.WRITE | Perm.EXEC
    self.assertTrue(all3 != both)
    self.assertEqual(str(both), "Perm.READ|Perm.WRITE")
    self.assertEqual(repr(both), "<Perm.READ|Perm.WRITE: 3>")
    self.assertEqual(repr(Perm.READ), "<Perm.READ: 1>")


class EnumFlagMatchTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    self.assertEqual(match_perm_single(Perm.READ), 1)
    self.assertEqual(match_perm_single(Perm.WRITE), 2)
    self.assertEqual(match_perm_single(Perm.EXEC), 0)
    self.assertEqual(match_perm_flags(Perm.READ), 3)
    self.assertEqual(match_perm_flags(Perm.WRITE), 3)
    self.assertEqual(match_perm_flags(Perm.READ | Perm.WRITE), 0)


class EnumLenIterTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    self.assertEqual(len(Mode), 3)
    self.assertEqual(len(Ext), 5)
    self.assertEqual(len(Perm), 3)
    self.assertEqual(count_modes(), 3)
    self.assertTrue(first_mode() == Mode.OFF)


class EnumIntCtorTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    self.assertEqual(int(Mode.ON), 1)
    self.assertTrue(Mode(1) == Mode.ON)
    self.assertEqual(int(Wide.LO), 1)
    self.assertTrue(Wide(1) == Wide.LO)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
