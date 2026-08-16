"""``py2cpp.io.file.path``（``os.path`` 子集）回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io.file.path import (
  baseName,
  dirName,
  isAbs,
  join,
  normPath,
  split,
  splitDrive,
  splitExt,
)


class FilePathJoinTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    p: str = join("foo", "bar")
    self.assertEqual(p, "foo\\bar")
    self.assertEqual(baseName(p), "bar")
    self.assertEqual(dirName(p), "foo")
    self.assertEqual(normPath("foo//bar\\"), "foo\\bar")


class FilePathSplitTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    pair: (str, str) = splitExt("dir\\file.txt")
    self.assertEqual(pair[0], "dir\\file")
    self.assertEqual(pair[1], ".txt")
    pair = splitExt("archive.tar.gz")
    self.assertEqual(pair[0], "archive.tar")
    self.assertEqual(pair[1], ".gz")
    pair = splitExt(".cshrc")
    self.assertEqual(pair[0], ".cshrc")
    self.assertEqual(pair[1], "")
    parts: (str, str) = split("foo\\bar")
    self.assertEqual(parts[0], "foo")
    self.assertEqual(parts[1], "bar")
    parts = split("\\foo")
    self.assertEqual(parts[0], "\\")
    self.assertEqual(parts[1], "foo")
    drvPair: (str, str) = splitDrive("C:\\Windows")
    self.assertEqual(drvPair[0], "C:")
    self.assertEqual(drvPair[1], "\\Windows")
    self.assertTrue(isAbs("C:\\x"))
    self.assertFalse(isAbs("relative"))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
