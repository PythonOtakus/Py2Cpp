"""``alg.trie``：``str`` 前缀字典树。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.trie import Trie


class TriePrefixTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    t: Trie = new()
    t.add("ab")
    t.add("abc")
    t.add("bc")
    self.assertTrue("ab" in t)
    self.assertTrue("abc" in t)
    self.assertFalse("a" in t)
    self.assertTrue(t.startswith("ab") == 2)
    self.assertTrue(t.startswith("b") == 1)
    self.assertTrue(t.startswith("z") == 0)
    self.assertTrue(len(t) == 3)
    self.assertTrue(bool(t))


class TrieSingleTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    t: Trie = new()
    t.add("x")
    self.assertTrue("x" in t)
    self.assertTrue(t.startswith("") == 1)
    self.assertFalse("xy" in t)
    self.assertTrue(len(t) == 1)


class TrieUpdateListTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    t: Trie = new()
    words: list[str] = ["ab", "bc"]
    t.update(words)
    self.assertTrue("ab" in t)
    self.assertTrue("bc" in t)
    self.assertTrue(t.startswith("a") == 1)
    self.assertTrue(len(t) == 2)


class TrieUpdateSelfTests(TestCaseMixin):
  _test_tag = 35

  @override
  def test(self):
    src: Trie = new()
    src.add("he")
    src.add("she")
    t: Trie = new()
    t.update(src)
    self.assertTrue("he" in t)
    self.assertTrue("she" in t)
    self.assertTrue(t.startswith("sh") == 1)
    self.assertTrue(len(t) == 2)


class TrieEmptyTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    t: Trie = new()
    self.assertFalse(bool(t))
    self.assertFalse(t)
    self.assertFalse("x" in t)
    self.assertTrue(t.startswith("") == 0)


class TrieRemoveTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    t: Trie = new()
    t.add("ab")
    t.add("abc")
    t.remove("ab")
    self.assertFalse("ab" in t)
    self.assertTrue("abc" in t)
    self.assertTrue(t.startswith("ab") == 1)
    self.assertTrue(len(t) == 1)


class TrieRemoveDuplicateTests(TestCaseMixin):
  _test_tag = 41

  @override
  def test(self):
    t: Trie = new()
    t.add("x")
    t.add("x")
    t.remove("x")
    self.assertTrue("x" in t)
    self.assertTrue(len(t) == 1)


class TrieClearTests(TestCaseMixin):
  _test_tag = 42

  @override
  def test(self):
    t: Trie = new()
    t.add("a")
    t.clear()
    self.assertFalse(bool(t))
    self.assertFalse("a" in t)
    self.assertTrue(t.startswith("a") == 0)


class TrieDiscardTests(TestCaseMixin):
  _test_tag = 43

  @override
  def test(self):
    t: Trie = new()
    t.add("ab")
    t.discard("z")
    self.assertTrue("ab" in t)
    t.discard("ab")
    self.assertFalse("ab" in t)
    t.discard("ab")
    self.assertFalse(t)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(TriePrefixTests())
  suite.addTest(TrieSingleTests())
  suite.addTest(TrieUpdateListTests())
  suite.addTest(TrieUpdateSelfTests())
  suite.addTest(TrieEmptyTests())
  suite.addTest(TrieRemoveTests())
  suite.addTest(TrieRemoveDuplicateTests())
  suite.addTest(TrieClearTests())
  suite.addTest(TrieDiscardTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
