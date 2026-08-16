"""``alg.trie``：``str`` 前缀字典树。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.trie import Trie


class TriePrefixTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    t: Trie = new()
    t.add("ab")
    t.add("abc")
    t.add("bc")
    self.assertTrue("ab" in t)
    self.assertTrue("abc" in t)
    self.assertFalse("a" in t)
    self.assertTrue(t.startsWith("ab") == 2)
    self.assertTrue(t.startsWith("b") == 1)
    self.assertTrue(t.startsWith("z") == 0)
    self.assertTrue(len(t) == 3)
    self.assertTrue(bool(t))


class TrieSingleTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    t: Trie = new()
    t.add("x")
    self.assertTrue("x" in t)
    self.assertTrue(t.startsWith("") == 1)
    self.assertFalse("xy" in t)
    self.assertTrue(len(t) == 1)


class TrieUpdateListTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    t: Trie = new()
    words: list[str] = ["ab", "bc"]
    t.update(words)
    self.assertTrue("ab" in t)
    self.assertTrue("bc" in t)
    self.assertTrue(t.startsWith("a") == 1)
    self.assertTrue(len(t) == 2)


class TrieUpdateSelfTests(TestCaseMixin):
  _testTag = 35

  @override
  def test(self):
    src: Trie = new()
    src.add("he")
    src.add("she")
    t: Trie = new()
    t.update(src)
    self.assertTrue("he" in t)
    self.assertTrue("she" in t)
    self.assertTrue(t.startsWith("sh") == 1)
    self.assertTrue(len(t) == 2)


class TrieEmptyTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    t: Trie = new()
    self.assertFalse(bool(t))
    self.assertFalse(t)
    self.assertFalse("x" in t)
    self.assertTrue(t.startsWith("") == 0)


class TrieRemoveTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    t: Trie = new()
    t.add("ab")
    t.add("abc")
    t.remove("ab")
    self.assertFalse("ab" in t)
    self.assertTrue("abc" in t)
    self.assertTrue(t.startsWith("ab") == 1)
    self.assertTrue(len(t) == 1)


class TrieRemoveDuplicateTests(TestCaseMixin):
  _testTag = 41

  @override
  def test(self):
    t: Trie = new()
    t.add("x")
    t.add("x")
    t.remove("x")
    self.assertTrue("x" in t)
    self.assertTrue(len(t) == 1)


class TrieClearTests(TestCaseMixin):
  _testTag = 42

  @override
  def test(self):
    t: Trie = new()
    t.add("a")
    t.clear()
    self.assertFalse(bool(t))
    self.assertFalse("a" in t)
    self.assertTrue(t.startsWith("a") == 0)


class TrieDiscardTests(TestCaseMixin):
  _testTag = 43

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
