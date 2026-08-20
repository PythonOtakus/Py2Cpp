"""``util.memory``：通用叶子 ``@native``（``copyArray`` / ``loadU64Le*``）；``str.fromArray`` 见 ``test_str``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.util.memory import (
  appendChars,
  copyArray,
  copyArrayRef,
  loadU64Le,
  loadU64LeBytes,
  loadU64LeBytesRef,
  loadU64LeRef,
)


class MemoryAppendCharsTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    src: char[:] = new(8)
    src[0] = ord("a")
    src[1] = ord("b")
    src[2] = ord("c")
    dst: char[:] = new(4)
    dst[0] = ord("x")
    at: int = appendChars(dst, 1, src)
    self.assertEqual(at, 4)
    self.assertEqual(str.fromArray(dst, 4), "xabc")


class MemoryCstrTests(TestCaseMixin):
  _testTag = 7

  @override
  def test(self):
    data: byte[:] = "abc".toArrayUtf8()
    p: utf8ptr = data.view.at(0)
    self.assertEqual(str.fromArrayBytes(data, 3), "abc")
    seg: span[byte] = p.view
    self.assertEqual(len(seg), 3)
    self.assertEqual(int(seg[0]), ord("a"))
    self.assertEqual(int(seg[2]), ord("c"))
    null: utf8ptr = cast(None)
    self.assertEqual(len(null.view), 0)
    self.assertEqual(str.fromSpanBytes(p.view[:3]), "abc")
    self.assertEqual(str.fromSpanBytes(p.view[1:3]), "bc")
    self.assertEqual(str.fromSpanBytes(p.view[3:3]), "")
    with "xyz".useUtf8() as scoped:
      self.assertEqual(str.fromSpanBytes(scoped.view), "xyz")


class MemoryLeafCopySegTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    raw: str = "hello"
    srcArray: char[:] = new(5)
    for i in range(5):
      srcArray[i] = char(raw[i])
    dstF: char[:] = new(8)
    dstR: char[:] = new(8)
    copyArray(dstF.view.at(0), srcArray.view.at(0), 5)
    copyArrayRef(dstR.view.at(0), srcArray.view.at(0), 5)
    self.assertEqual(str.fromArray(dstF, 5), str.fromArrayRef(dstR, 5))


class MemoryLeafLoadU64Tests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    raw: str = "ABCDEFGH"
    rawArray: char[:] = new(8)
    for i in range(8):
      rawArray[i] = char(raw[i])
    gotF = loadU64Le(rawArray.view.at(0), 0)
    gotR = loadU64LeRef(rawArray.view.at(0), 0)
    self.assertEqual(gotF, gotR)
    expect: uint64 = 0
    for i in range(8):
      part: uint64 = int(raw[i]) & 0xFF
      sh: uint64 = i * 8
      expect |= part << sh
    self.assertEqual(gotF, expect)


class MemoryLeafLoadU64BytesTests(TestCaseMixin):
  _testTag = 25

  @override
  def test(self):
    buf: byte[:] = new(8)
    buf[0] = ord("1")
    buf[1] = ord("2")
    buf[2] = ord("3")
    buf[3] = ord("4")
    buf[4] = ord("5")
    buf[5] = ord("6")
    buf[6] = ord("7")
    buf[7] = ord("8")
    gotF = loadU64LeBytes(buf.view.at(0), 0)
    gotR = loadU64LeBytesRef(buf.view.at(0), 0)
    self.assertEqual(gotF, gotR)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
