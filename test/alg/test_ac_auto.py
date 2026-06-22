"""``alg.ac_auto``：多模式匹配 ``count``。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.ac_auto import ACAuto


class AcAutoBasicTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("ab")
    ac.add("abc")
    ac.add("bc")
    ac.flush()
    self.assertTrue(ac.count("abababc") == 5)
    self.assertTrue("ab" in ac)
    self.assertTrue("abc" in ac)
    self.assertFalse("a" in ac)
    self.assertTrue(len(ac) == 3)
    self.assertTrue(bool(ac))


class AcAutoOverlapTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("a")
    ac.add("aa")
    ac.flush()
    self.assertTrue(ac.count("aaa") == 5)


class AcAutoDuplicateAddTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("x")
    ac.add("x")
    ac.flush()
    self.assertTrue(ac.count("x") == 2)
    self.assertTrue(len(ac) == 2)


class AcAutoLazyBuildTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("he")
    ac.add("she")
    self.assertTrue(ac.count("ushers") == 2)


class AcAutoContainsTests(TestCaseMixin):
  _test_tag = 45

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("ab")
    self.assertTrue("ab" in ac)
    self.assertFalse("abc" in ac)
    self.assertFalse("x" in ac)


class AcAutoUpdateListTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    ac: ACAuto = new()
    words: list[str] = ["ab", "bc"]
    ac.update(words)
    self.assertTrue(ac.count("abc") == 2)
    self.assertTrue(len(ac) == 2)


class AcAutoUpdateSelfTests(TestCaseMixin):
  _test_tag = 55

  @override
  def test(self):
    src: ACAuto = new()
    src.add("he", False)
    src.add("she", False)
    src.flush()
    ac: ACAuto = new()
    ac.update(src)
    self.assertTrue(ac.count("ushers") == 2)
    self.assertTrue(len(ac) == 2)


class AcAutoAddFlushFalseTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("a", False)
    ac.add("aa", False)
    ac.flush()
    self.assertTrue(ac.count("aaa") == 5)


class AcAutoEmptyTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    ac: ACAuto = new()
    ac.flush()
    self.assertFalse(bool(ac))
    self.assertFalse(ac)
    self.assertTrue(ac.count("") == 0)
    self.assertTrue(ac.count("abc") == 0)
    self.assertFalse("x" in ac)


class AcAutoRemoveTests(TestCaseMixin):
  _test_tag = 70

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("ab")
    ac.add("abc")
    ac.remove("ab")
    self.assertFalse("ab" in ac)
    self.assertTrue("abc" in ac)
    self.assertTrue(ac.count("abc") == 1)
    self.assertTrue(len(ac) == 1)


class AcAutoRemoveDuplicateTests(TestCaseMixin):
  _test_tag = 71

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("x")
    ac.add("x")
    ac.remove("x")
    self.assertTrue(ac.count("x") == 1)
    self.assertTrue(len(ac) == 1)


class AcAutoClearTests(TestCaseMixin):
  _test_tag = 72

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("he")
    ac.clear()
    self.assertFalse(bool(ac))
    self.assertTrue(ac.count("he") == 0)
    self.assertFalse("he" in ac)


class AcAutoDiscardTests(TestCaseMixin):
  _test_tag = 73

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("ab")
    ac.discard("z")
    self.assertTrue(ac.count("abab") == 2)
    ac.discard("ab")
    self.assertTrue(ac.count("abab") == 0)
    ac.discard("ab")
    self.assertFalse(ac)


class AcAutoRemoveFlushFalseTests(TestCaseMixin):
  _test_tag = 74

  @override
  def test(self):
    ac: ACAuto = new()
    ac.add("a", False)
    ac.add("aa", False)
    ac.add("ab", False)
    ac.remove("ab", False)
    ac.flush()
    self.assertFalse("ab" in ac)
    self.assertTrue(ac.count("aaa") == 5)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(AcAutoBasicTests())
  suite.addTest(AcAutoOverlapTests())
  suite.addTest(AcAutoDuplicateAddTests())
  suite.addTest(AcAutoLazyBuildTests())
  suite.addTest(AcAutoContainsTests())
  suite.addTest(AcAutoUpdateListTests())
  suite.addTest(AcAutoUpdateSelfTests())
  suite.addTest(AcAutoAddFlushFalseTests())
  suite.addTest(AcAutoEmptyTests())
  suite.addTest(AcAutoRemoveTests())
  suite.addTest(AcAutoRemoveDuplicateTests())
  suite.addTest(AcAutoClearTests())
  suite.addTest(AcAutoDiscardTests())
  suite.addTest(AcAutoRemoveFlushFalseTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
