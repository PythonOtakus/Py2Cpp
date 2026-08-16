"""``py2cpp.serde.base64``：对齐 Python 3.13 ``base64`` RFC 4648 子集。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.serde.base64 import (
  b64decode,
  b64encode,
  encodeBytes,
  urlsafeB64decode,
  urlsafeB64encode,
)


class B64EncodeTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(b64encode(b""), b"")
    self.assertEqual(b64encode(b"f"), b"Zg==")
    self.assertEqual(b64encode(b"fo"), b"Zm8=")
    self.assertEqual(b64encode(b"foo"), b"Zm9v")
    self.assertEqual(b64encode(b"foobar"), b"Zm9vYmFy")
    self.assertEqual(b64encode(b"\xfb\xef\xbe"), b"++++")


class B64DecodeTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    self.assertEqual(b64decode(b"Zm9v"), b"foo")
    self.assertEqual(b64decode("Zm9v"), b"foo")
    self.assertEqual(b64decode(b"Zm9vYmFy"), b"foobar")
    got: bytes = b64decode(b"Zm9v\nYmFy\r\n")
    self.assertEqual(got, b"foobar")


class UrlSafeTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    raw: bytes = b"\xfb\xef\xbe"
    enc: bytes = urlsafeB64encode(raw)
    self.assertEqual(enc, b"----")
    self.assertEqual(urlsafeB64decode(enc), raw)
    self.assertEqual(urlsafeB64decode("----"), raw)


class EncodeBytesTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    payload: bytes = b"x" * 57 + b"y"
    wrapped: bytes = encodeBytes(payload)
    self.assertEqual(b64decode(wrapped), payload)


def main():
  suite: TestSuite = new()
  suite.addTest(B64EncodeTests())
  suite.addTest(B64DecodeTests())
  suite.addTest(UrlSafeTests())
  suite.addTest(EncodeBytesTests())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
