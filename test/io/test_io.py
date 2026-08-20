"""``io`` 模块与 ``with``（``StringIO`` / ``open``）回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io import StringIO, open
from py2cpp.io.path import Path
from py2cpp.test.test_temp import _TestTemp, ensureTestTemp



class StringIOWriteTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    sio: StringIO = new()
    self.assertEqual(sio.write("hello"), 5)
    self.assertEqual(sio.value, "hello")
    self.assertEqual(sio.tell(), 5)


class StringIOWriteCharsTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    sio: StringIO = new()
    buf: char[:] = new(3)
    buf[0] = ord("a")
    buf[1] = ord("b")
    buf[2] = ord("c")
    self.assertEqual(sio.write(buf), 3)
    self.assertEqual(sio.value, "abc")
    self.assertEqual(sio.tell(), 3)


class StringIOReadTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    sio: StringIO = new("hello")
    sio.seek(0)
    self.assertEqual(sio.read(2), "he")
    self.assertEqual(sio.tell(), 2)
    self.assertEqual(sio.read(), "llo")
    self.assertEqual(sio.tell(), 5)


class StringIOReadlineTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    sio: StringIO = new("a\nb")
    self.assertEqual(sio.readLine(), "a\n")
    self.assertEqual(sio.readLine(), "b")
    self.assertEqual(sio.readLine(), "")


class StringIOReadlinesTests(TestCaseMixin):
  _testTag = 21

  @override
  def test(self):
    sio: StringIO = new("a\nbc\ndef\n")
    got: list[str] = sio.readLines()
    self.assertEqual(len(got), 3)
    self.assertEqual(got[0], "a\n")
    self.assertEqual(got[1], "bc\n")
    self.assertEqual(got[2], "def\n")
    sio.seek(0)
    got2: list[str] = sio.readLines(2)
    self.assertEqual(len(got2), 1)
    self.assertEqual(got2[0], "a\n")
    sio.seek(0)
    got3: list[str] = sio.readLines(5)
    self.assertEqual(len(got3), 2)
    self.assertEqual(got3[0], "a\n")
    self.assertEqual(got3[1], "bc\n")


class StringIOWritelinesTests(TestCaseMixin):
  _testTag = 22

  @override
  def test(self):
    sio: StringIO = new()
    parts: list[str] = []
    parts.append("ab")
    parts.append("c\n")
    parts.append("d")
    sio.writeLines(parts)
    self.assertEqual(sio.value, "abc\nd")


class StringIOIterTests(TestCaseMixin):
  _testTag = 23

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
  _testTag = 30

  @override
  def test(self):
    sio: StringIO = new("hello")
    sio.seek(0)
    sio.write("hi")
    # 与 CPython StringIO 一致：覆盖前缀，不截断尾部
    self.assertEqual(sio.value, "hillo")


class StringIOCloseTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    sio: StringIO = new()
    sio.close()
    self.assertFalse(sio)
    self.assertEqual(sio.write("x"), 0)
    self.assertEqual(sio.value, "")


class StringIOTakeTests(TestCaseMixin):
  _testTag = 50

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
  _testTag = 51

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
  _testTag = 100

  @override
  def test(self):
    ensureTestTemp()
    w = open(str(Path(_TestTemp) / "test_io_tmp.txt"), "wb")
    self.assertTrue(w)
    self.assertEqual(w.write("abc\n"), 4)
    w.close()
    r = open(str(Path(_TestTemp) / "test_io_tmp.txt"), "rb")
    self.assertTrue(r)
    self.assertEqual(r.read(), "abc\n")
    r.close()


class FileIOReadlineTests(TestCaseMixin):
  _testTag = 110

  @override
  def test(self):
    ensureTestTemp()
    w = open(str(Path(_TestTemp) / "test_io_tmp.txt"), "wb")
    w.write("line1\nline2\n")
    w.close()
    r = open(str(Path(_TestTemp) / "test_io_tmp.txt"), "rb")
    self.assertEqual(r.readLine(), "line1\n")
    self.assertEqual(r.readLine(), "line2\n")
    self.assertEqual(r.readLine(), "")
    r.close()


class FileIOReadlinesTests(TestCaseMixin):
  _testTag = 111

  @override
  def test(self):
    ensureTestTemp()
    w = open(str(Path(_TestTemp) / "test_io_tmp.txt"), "wb")
    w.write("a\nbb\nccc\n")
    w.close()
    r = open(str(Path(_TestTemp) / "test_io_tmp.txt"), "rb")
    got: list[str] = r.readLines()
    self.assertEqual(len(got), 3)
    self.assertEqual(got[0], "a\n")
    self.assertEqual(got[1], "bb\n")
    self.assertEqual(got[2], "ccc\n")
    r.seek(0)
    got2: list[str] = r.readLines(2)
    self.assertEqual(len(got2), 1)
    self.assertEqual(got2[0], "a\n")
    r.close()


class FileIOWritelinesTests(TestCaseMixin):
  _testTag = 112

  @override
  def test(self):
    ensureTestTemp()
    w = open(str(Path(_TestTemp) / "test_io_writelines.txt"), "wb")
    parts: list[str] = []
    parts.append("hi")
    parts.append("\n")
    parts.append("there")
    w.writeLines(parts)
    w.close()
    r = open(str(Path(_TestTemp) / "test_io_writelines.txt"), "rb")
    self.assertEqual(r.read(), "hi\nthere")
    r.close()


class FileIOIterTests(TestCaseMixin):
  _testTag = 113

  @override
  def test(self):
    ensureTestTemp()
    w = open(str(Path(_TestTemp) / "test_io_iter.txt"), "wb")
    w.write("p\nq\n")
    w.close()
    r = open(str(Path(_TestTemp) / "test_io_iter.txt"), "rb")
    out: list[str] = []
    for line in r:
      out.append(line)
    self.assertEqual(len(out), 2)
    self.assertEqual(out[0], "p\n")
    self.assertEqual(out[1], "q\n")
    r.close()


class FileIOSeekTellTests(TestCaseMixin):
  _testTag = 120

  @override
  def test(self):
    ensureTestTemp()
    w = open(str(Path(_TestTemp) / "test_io_tmp.txt"), "wb")
    w.write("abcdef")
    w.close()
    r = open(str(Path(_TestTemp) / "test_io_tmp.txt"), "rb")
    self.assertEqual(r.tell(), 0)
    self.assertEqual(r.read(3), "abc")
    self.assertEqual(r.tell(), 3)
    r.seek(0)
    self.assertEqual(r.tell(), 0)
    self.assertEqual(r.read(2), "ab")
    r.close()


class StringIOWithTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    with StringIO() as sio:
      sio.write("ab")
      self.assertEqual(sio.value, "ab")


class FileWithCloseTests(TestCaseMixin):
  _testTag = 11

  @override
  def test(self):
    ensureTestTemp()
    with open(str(Path(_TestTemp) / "test_with_tmp.txt"), "wb") as f:
      self.assertTrue(f)
      f.write("data")
    r = open(str(Path(_TestTemp) / "test_with_tmp.txt"), "rb")
    self.assertEqual(r.read(), "data")
    r.close()


class NestedWithTests(TestCaseMixin):
  _testTag = 24

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
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
