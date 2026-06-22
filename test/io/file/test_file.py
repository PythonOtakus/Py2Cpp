"""``py2cpp.io.file``（``os`` 磁盘 API 子集）回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io import open
from py2cpp.io.file import getcwd, listdir, mkdir, remove, rmdir, stat, c_stat, scandir, DirEntry
from py2cpp.io.file.path import exists, isdir, isfile, join
from py2cpp.io.file.path import join
from py2cpp.test.test_temp import _TEST_TEMP, ensure_test_temp

_TEST_DIR: str = "test_file_dir"
_TEST_FILE: str = "test_file.txt"


class FileStatTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    cwd: str = getcwd()
    self.assertTrue(cwd)
    st: c_stat = stat(cwd)
    self.assertTrue(st.st_mode > 0)
    self.assertTrue(isdir(cwd))
    self.assertTrue(exists(cwd))


class FileDirOpsTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    ensure_test_temp()
    cwd: str = getcwd()
    dir_path: str = join(join(cwd, _TEST_TEMP), _TEST_DIR)
    file_path: str = join(dir_path, _TEST_FILE)
    if exists(dir_path):
      if exists(file_path):
        remove(file_path)
      rmdir(dir_path)
    mkdir(dir_path)
    self.assertTrue(isdir(dir_path))
    w = open(file_path, "wb")
    self.assertTrue(w)
    self.assertEqual(w.write("ok"), 2)
    w.close()
    self.assertTrue(isfile(file_path))
    self.assertFalse(isdir(file_path))
    names: list[str] = listdir(dir_path)
    self.assertEqual(len(names), 1)
    self.assertEqual(names[0], _TEST_FILE)
    cnt: int = 0
    ent: DirEntry = new()
    for ent in scandir(dir_path):
      cnt += 1
      self.assertEqual(ent.name, _TEST_FILE)
    self.assertEqual(cnt, 1)
    remove(file_path)
    rmdir(dir_path)
    self.assertFalse(exists(file_path))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
