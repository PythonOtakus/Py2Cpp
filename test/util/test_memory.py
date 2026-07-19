"""``util.memory``：通用叶子 ``@native``（``copy_buf`` / ``load_u64_le*``）；``str.from_buf`` 见 ``test_str``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.util.memory import (
  append_chars,
  copy_buf,
  copy_buf_ref,
  load_u64_le,
  load_u64_le_bytes,
  load_u64_le_bytes_ref,
  load_u64_le_ref,
)


class MemoryAppendCharsTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    src: char[:] = new(8)
    src[0] = ord("a")
    src[1] = ord("b")
    src[2] = ord("c")
    dst: char[:] = new(4)
    dst[0] = ord("x")
    at: int = append_chars(dst, 1, src, 3)
    self.assertEqual(at, 4)
    self.assertEqual(str.from_buf(dst, 4), "xabc")


class MemoryLeafCopySegTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    raw: str = "hello"
    src_buf: char[:] = new(5)
    for i in range(5):
      src_buf[i] = char(raw[i])
    dst_f: char[:] = new(8)
    dst_r: char[:] = new(8)
    copy_buf(dst_f.view.at(0), src_buf.view.at(0), 5)
    copy_buf_ref(dst_r.view.at(0), src_buf.view.at(0), 5)
    self.assertEqual(str.from_buf(dst_f, 5), str.from_buf_ref(dst_r, 5))


class MemoryLeafLoadU64Tests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    raw: str = "ABCDEFGH"
    raw_buf: char[:] = new(8)
    for i in range(8):
      raw_buf[i] = char(raw[i])
    got_f = load_u64_le(raw_buf.view.at(0), 0)
    got_r = load_u64_le_ref(raw_buf.view.at(0), 0)
    self.assertEqual(got_f, got_r)
    expect: uint64 = 0
    for i in range(8):
      part: uint64 = int(raw[i]) & 0xFF
      sh: uint64 = i * 8
      expect |= part << sh
    self.assertEqual(got_f, expect)


class MemoryLeafLoadU64BytesTests(TestCaseMixin):
  _test_tag = 25

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
    got_f = load_u64_le_bytes(buf.view.at(0), 0)
    got_r = load_u64_le_bytes_ref(buf.view.at(0), 0)
    self.assertEqual(got_f, got_r)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
