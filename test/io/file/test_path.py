"""``py2cpp.io.file.path``（``os.path`` 子集）回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io.file.path import (
  basename,
  dirname,
  isabs,
  join,
  normpath,
  split,
  splitdrive,
  splitext,
)


class FilePathJoinTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    p: str = join("foo", "bar")
    self.assertEqual(p, "foo\\bar")
    self.assertEqual(basename(p), "bar")
    self.assertEqual(dirname(p), "foo")
    self.assertEqual(normpath("foo//bar\\"), "foo\\bar")


class FilePathSplitTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    pair: (str, str) = splitext("dir\\file.txt")
    self.assertEqual(pair[0], "dir\\file")
    self.assertEqual(pair[1], ".txt")
    pair = splitext("archive.tar.gz")
    self.assertEqual(pair[0], "archive.tar")
    self.assertEqual(pair[1], ".gz")
    pair = splitext(".cshrc")
    self.assertEqual(pair[0], ".cshrc")
    self.assertEqual(pair[1], "")
    parts: (str, str) = split("foo\\bar")
    self.assertEqual(parts[0], "foo")
    self.assertEqual(parts[1], "bar")
    parts = split("\\foo")
    self.assertEqual(parts[0], "\\")
    self.assertEqual(parts[1], "foo")
    drv_pair: (str, str) = splitdrive("C:\\Windows")
    self.assertEqual(drv_pair[0], "C:")
    self.assertEqual(drv_pair[1], "\\Windows")
    self.assertTrue(isabs("C:\\x"))
    self.assertFalse(isabs("relative"))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
