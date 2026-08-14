"""``bytes`` 与 ``StringMixin`` 共享 API 回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class BytesSequenceTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    # ``__len__``、布尔真值、下标与切片、``+`` / ``*`` / ``in``
    b: bytes = b"hello"
    self.assertEqual(len(b), 5)
    self.assertTrue(b)
    self.assertEqual(b[0], ord("h"))
    self.assertEqual(b[1:4], b"ell")
    self.assertEqual(b + b"!", b"hello!")
    self.assertTrue(b"ll" in b)
    self.assertEqual(b * 2, b"hellohello")


class BytesFindTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    # ``count`` / ``find`` / ``rfind`` / ``startswith`` / ``endswith``（KMP 路径）
    hay: bytes = b"spam, spam, eggs"
    self.assertEqual(hay.count(b"spam"), 2)
    self.assertEqual(hay.find(b"eggs"), 12)
    self.assertEqual(hay.rfind(b"spam"), 6)
    self.assertTrue(hay.startswith(b"spam"))
    self.assertTrue(hay.endswith(b"eggs"))


class BytesSplitTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    # ``split`` / ``rsplit`` / ``partition`` / ``replace``
    parts: list[bytes] = []
    parts.append(b"a")
    parts.append(b"b")
    parts.append(b"c")
    self.assertEqual(b"a,b,c".split(b","), parts)
    ws_parts: list[bytes] = []
    ws_parts.append(b"a")
    ws_parts.append(b"b")
    self.assertEqual(b"  a  b  ".split(), ws_parts)
    rs_parts: list[bytes] = []
    rs_parts.append(b"a|b")
    rs_parts.append(b"c")
    self.assertEqual(b"a|b|c".rsplit(b"|", 1), rs_parts)
    xparts: list[bytes] = []
    for part in b"a,b,c".xsplit(b","):
      xparts.append(part)
    self.assertEqual(xparts, parts)
    xrs: list[bytes] = []
    for part in b"a|b|c".xrsplit(b"|", 1):
      xrs.append(part)
    self.assertEqual(xrs, rs_parts)
    xlines: list[bytes] = []
    for line in b"a\nb".xsplitlines():
      xlines.append(line)
    self.assertEqual(xlines, b"a\nb".splitlines())
    part: bytes = b"a=b".partition(b"=")[0]
    self.assertEqual(part, b"a")
    self.assertEqual(b"a=b".partition(b"=")[1], b"=")
    self.assertEqual(b"a=b".partition(b"=")[2], b"b")
    self.assertEqual(b"x".replace(b"x", b"y"), b"y")
    self.assertEqual(b"a,b,c".split_prefix(b","), b"a")
    self.assertEqual(b"a,b,c".split_suffix(b","), b"b,c")
    self.assertEqual(b"a|b|c".rsplit_prefix(b"|"), b"a|b")
    self.assertEqual(b"a|b|c".rsplit_suffix(b"|"), b"c")
    self.assertEqual(b"  a  b  ".split_prefix(), b"a")
    self.assertEqual(b"  a  b  ".rsplit_suffix(), b"b")


class BytesStripTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    # ``strip`` / ``removeprefix`` / ``removesuffix``
    ws: bytes = b"   hi   "
    self.assertEqual(ws.strip(), b"hi")
    self.assertEqual(b"pre_hook".removeprefix(b"pre_"), b"hook")
    self.assertEqual(b"file.txt".removesuffix(b".txt"), b"file")
    self.assertEqual(b"\n  a\n    b\n".striplines(1), b" a\n   b")


class BytesJoinDecodeTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    # ``join``、``str.encode`` / ``bytes.decode``
    parts: list[bytes] = []
    parts.append(b"a")
    parts.append(b"b")
    self.assertEqual(b",".join(parts), b"a,b")
    self.assertEqual(b"Hi".decode(), "Hi")
    self.assertEqual("Hi".encode(), b"Hi")


class BytesCtorTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    # ``bytes(n)`` 零填充构造
    z: bytes = bytes(4)
    self.assertEqual(len(z), 4)
    self.assertEqual(z[0], 0)
    self.assertEqual(z[3], 0)


class BytesTranslateTests(TestCaseMixin):
  _test_tag = 70

  @override
  def test(self):
    # ``maketrans`` / ``translate``（含 delete 表项）
    tbl: dict[byte, byte] = bytes.maketrans(b"ab", b"AB")
    self.assertEqual(b"abc".translate(tbl), b"ABc")
    self.assertEqual(b"abc".translate(tbl, delete=b""), b"ABc")
    self.assertEqual(b"abc".translate(tbl, delete=b"c"), b"AB")
    del_tbl: dict[byte, byte] = {}
    del_tbl[ord("b")] = 0xFF
    self.assertEqual(b"abc".translate(del_tbl), b"ac")


class BytesStartswithListTests(TestCaseMixin):
  _test_tag = 80

  @override
  def test(self):
    # ``startswith`` / ``endswith`` 多段 ``list[bytes]`` 与 ``byte[:]`` 缓冲
    prefixes: list[bytes] = []
    prefixes.append(b"spam")
    prefixes.append(b"ham")
    self.assertTrue(b"spam eggs".startswith(prefixes))
    pref: byte[:] = b"egg"
    self.assertTrue(b"eggs".startswith(pref))
    pref_arr: bytes[:] = new(2)
    pref_arr[0] = b"spam"
    pref_arr[1] = b"ham"
    self.assertTrue(b"spam eggs".startswith(pref_arr))
    suf_arr: bytes[:] = new(2)
    suf_arr[0] = b"eggs"
    suf_arr[1] = b"ham"
    self.assertTrue(b"spam eggs".endswith(suf_arr))
    self.assertFalse(b"spam egg".endswith(suf_arr))


class BytesGlobTests(TestCaseMixin):
  _test_tag = 85

  @override
  def test(self):
    self.assertTrue(b"readme.txt".glob(b"*.txt"))
    self.assertTrue(b"readme.txt".glob(b"*.TXT"))
    self.assertFalse(b"readme.txt".glob(b"*.TXT", False))
    self.assertTrue(b"abc".glob(b"a?c"))


class BytesCaseTests(TestCaseMixin):
  _test_tag = 90

  @override
  def test(self):
    # 大小写、``capitalize``、``expandtabs``、谓词、``ljust`` / ``zfill``
    self.assertEqual(b"ab".upper(), b"AB")
    self.assertEqual(b"AB".lower(), b"ab")
    self.assertEqual(b"hello".capitalize(), b"Hello")
    self.assertEqual(b"a\tb".expandtabs(4).find(b"   "), 1)
    self.assertTrue(b"abc1".isalnum())
    self.assertTrue(b"abc".isalpha())
    self.assertTrue(b"ascii".isascii())
    self.assertTrue(b"123".isdigit())
    self.assertTrue(b"lower".islower())
    self.assertTrue(b" \t".isspace())
    self.assertTrue(b"UPPER".isupper())
    self.assertEqual(b"x".ljust(3), b"x  ")
    self.assertEqual(b"42".zfill(5), b"00042")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
