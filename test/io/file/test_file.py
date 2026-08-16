"""``py2cpp.io.file``（``os`` 磁盘 API 子集）回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io import open
from py2cpp.io.file import getCwd, listDir, mkdir, remove, rmdir, stat, CStat, scandir, DirEntry
from py2cpp.io.file.path import exists, isDir, isFile, join
from py2cpp.io.file.path import join
from py2cpp.test.test_temp import _TestTemp, ensureTestTemp

_TestDir: str = "test_file_dir"
_TestFile: str = "test_file.txt"


class FileStatTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    cwd: str = getCwd()
    self.assertTrue(cwd)
    st: CStat = stat(cwd)
    self.assertTrue(st.stMode > 0)
    self.assertTrue(isDir(cwd))
    self.assertTrue(exists(cwd))


class FileDirOpsTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    ensureTestTemp()
    cwd: str = getCwd()
    dirPath: str = join(join(cwd, _TestTemp), _TestDir)
    filePath: str = join(dirPath, _TestFile)
    if exists(dirPath):
      if exists(filePath):
        remove(filePath)
      rmdir(dirPath)
    mkdir(dirPath)
    self.assertTrue(isDir(dirPath))
    w = open(filePath, "wb")
    self.assertTrue(w)
    self.assertEqual(w.write("ok"), 2)
    w.close()
    self.assertTrue(isFile(filePath))
    self.assertFalse(isDir(filePath))
    names: list[str] = listDir(dirPath)
    self.assertEqual(len(names), 1)
    self.assertEqual(names[0], _TestFile)
    cnt: int = 0
    ent: DirEntry = new()
    for ent in scandir(dirPath):
      cnt += 1
      self.assertEqual(ent.name, _TestFile)
    self.assertEqual(cnt, 1)
    remove(filePath)
    rmdir(dirPath)
    self.assertFalse(exists(filePath))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
