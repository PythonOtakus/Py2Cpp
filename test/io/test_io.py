"""``io`` 模块与 ``with``（``StringIO`` / ``open``）回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io import StringIO, open
from py2cpp.io.file.path import join
from py2cpp.test.test_temp import _TEST_TEMP, ensure_test_temp

_IO_TMP: str = join(_TEST_TEMP, "test_io_tmp.txt")
_IO_WRITELINES: str = join(_TEST_TEMP, "test_io_writelines.txt")
_IO_ITER: str = join(_TEST_TEMP, "test_io_iter.txt")
_WITH_TMP: str = join(_TEST_TEMP, "test_with_tmp.txt")


class StringIOWriteTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    sio: StringIO = new()
    self.assertEqual(sio.write("hello"), 5)
    self.assertEqual(sio.value, "hello")
    self.assertEqual(sio.tell(), 5)


class StringIOWriteCharsTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    sio: StringIO = new()
    buf: char[:] = new(3)
    buf[0] = ord("a")
    buf[1] = ord("b")
    buf[2] = ord("c")
    self.assertEqual(sio.write(buf, 3), 3)
    self.assertEqual(sio.value, "abc")
    self.assertEqual(sio.tell(), 3)


class StringIOReadTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    sio: StringIO = new("hello")
    sio.seek(0)
    self.assertEqual(sio.read(2), "he")
    self.assertEqual(sio.tell(), 2)
    self.assertEqual(sio.read(), "llo")
    self.assertEqual(sio.tell(), 5)


class StringIOReadlineTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    sio: StringIO = new("a\nb")
    self.assertEqual(sio.readline(), "a\n")
    self.assertEqual(sio.readline(), "b")
    self.assertEqual(sio.readline(), "")


class StringIOReadlinesTests(TestCaseMixin):
  _test_tag = 21

  @override
  def test(self):
    sio: StringIO = new("a\nbc\ndef\n")
    got: list[str] = sio.readlines()
    self.assertEqual(len(got), 3)
    self.assertEqual(got[0], "a\n")
    self.assertEqual(got[1], "bc\n")
    self.assertEqual(got[2], "def\n")
    sio.seek(0)
    got2: list[str] = sio.readlines(2)
    self.assertEqual(len(got2), 1)
    self.assertEqual(got2[0], "a\n")
    sio.seek(0)
    got3: list[str] = sio.readlines(5)
    self.assertEqual(len(got3), 2)
    self.assertEqual(got3[0], "a\n")
    self.assertEqual(got3[1], "bc\n")


class StringIOWritelinesTests(TestCaseMixin):
  _test_tag = 22

  @override
  def test(self):
    sio: StringIO = new()
    parts: list[str] = []
    parts.append("ab")
    parts.append("c\n")
    parts.append("d")
    sio.writelines(parts)
    self.assertEqual(sio.value, "abc\nd")


class StringIOIterTests(TestCaseMixin):
  _test_tag = 23

  @override
  def test(self):
    sio: StringIO = new("x\ny\n")
    out: list[str] = []
    for line in sio:
      out.append(line)
    self.assertEqual(len(out), 2)
    self.assertEqual(out[0], "x\n")
    self.assertEqual(out[1], "y\n")


class StringIOSeekOverwriteTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    sio: StringIO = new("hello")
    sio.seek(0)
    sio.write("hi")
    # 与 CPython StringIO 一致：覆盖前缀，不截断尾部
    self.assertEqual(sio.value, "hillo")


class StringIOCloseTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    sio: StringIO = new()
    sio.close()
    self.assertFalse(sio)
    self.assertEqual(sio.write("x"), 0)
    self.assertEqual(sio.value, "")


class StringIOTakeTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    sio: StringIO = new()
    sio.write("hello")
    out: str = sio.take()
    self.assertEqual(out, "hello")
    self.assertEqual(sio.value, "")
    self.assertEqual(sio.write("next"), 4)
    self.assertEqual(sio.take(), "next")
    sio2: StringIO = new("hello")
    sio2.seek(0)
    sio2.write("hi")
    self.assertEqual(sio2.take(), "hillo")


class StringIOPosTests(TestCaseMixin):
  _test_tag = 51

  @override
  def test(self):
    sio: StringIO = new("abcdef")
    self.assertEqual(sio.pos, 0)
    sio.pos = 3
    self.assertEqual(sio.tell(), 3)
    self.assertEqual(sio.read(2), "de")
    sio.pos = 0
    self.assertEqual(sio.read(1), "a")


class FileIOWriteReadTests(TestCaseMixin):
  _test_tag = 100

  @override
  def test(self):
    ensure_test_temp()
    w = open(_IO_TMP, "wb")
    self.assertTrue(w)
    self.assertEqual(w.write("abc\n"), 4)
    w.close()
    r = open(_IO_TMP, "rb")
    self.assertTrue(r)
    self.assertEqual(r.read(), "abc\n")
    r.close()


class FileIOReadlineTests(TestCaseMixin):
  _test_tag = 110

  @override
  def test(self):
    ensure_test_temp()
    w = open(_IO_TMP, "wb")
    w.write("line1\nline2\n")
    w.close()
    r = open(_IO_TMP, "rb")
    self.assertEqual(r.readline(), "line1\n")
    self.assertEqual(r.readline(), "line2\n")
    self.assertEqual(r.readline(), "")
    r.close()


class FileIOReadlinesTests(TestCaseMixin):
  _test_tag = 111

  @override
  def test(self):
    ensure_test_temp()
    w = open(_IO_TMP, "wb")
    w.write("a\nbb\nccc\n")
    w.close()
    r = open(_IO_TMP, "rb")
    got: list[str] = r.readlines()
    self.assertEqual(len(got), 3)
    self.assertEqual(got[0], "a\n")
    self.assertEqual(got[1], "bb\n")
    self.assertEqual(got[2], "ccc\n")
    r.seek(0)
    got2: list[str] = r.readlines(2)
    self.assertEqual(len(got2), 1)
    self.assertEqual(got2[0], "a\n")
    r.close()


class FileIOWritelinesTests(TestCaseMixin):
  _test_tag = 112

  @override
  def test(self):
    ensure_test_temp()
    w = open(_IO_WRITELINES, "wb")
    parts: list[str] = []
    parts.append("hi")
    parts.append("\n")
    parts.append("there")
    w.writelines(parts)
    w.close()
    r = open(_IO_WRITELINES, "rb")
    self.assertEqual(r.read(), "hi\nthere")
    r.close()


class FileIOIterTests(TestCaseMixin):
  _test_tag = 113

  @override
  def test(self):
    ensure_test_temp()
    w = open(_IO_ITER, "wb")
    w.write("p\nq\n")
    w.close()
    r = open(_IO_ITER, "rb")
    out: list[str] = []
    for line in r:
      out.append(line)
    self.assertEqual(len(out), 2)
    self.assertEqual(out[0], "p\n")
    self.assertEqual(out[1], "q\n")
    r.close()


class FileIOSeekTellTests(TestCaseMixin):
  _test_tag = 120

  @override
  def test(self):
    ensure_test_temp()
    w = open(_IO_TMP, "wb")
    w.write("abcdef")
    w.close()
    r = open(_IO_TMP, "rb")
    self.assertEqual(r.tell(), 0)
    self.assertEqual(r.read(3), "abc")
    self.assertEqual(r.tell(), 3)
    r.seek(0)
    self.assertEqual(r.tell(), 0)
    self.assertEqual(r.read(2), "ab")
    r.close()


class StringIOWithTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    with StringIO() as sio:
      sio.write("ab")
      self.assertEqual(sio.value, "ab")


class FileWithCloseTests(TestCaseMixin):
  _test_tag = 11

  @override
  def test(self):
    ensure_test_temp()
    with open(_WITH_TMP, "wb") as f:
      self.assertTrue(f)
      f.write("data")
    r = open(_WITH_TMP, "rb")
    self.assertEqual(r.read(), "data")
    r.close()


class NestedWithTests(TestCaseMixin):
  _test_tag = 24

  @override
  def test(self):
    with StringIO() as outer:
      outer.write("o")
      with StringIO() as inner:
        inner.write("i")
        self.assertEqual(inner.value, "i")
      self.assertEqual(outer.value, "o")

def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
