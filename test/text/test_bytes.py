"""``bytes`` 与 ``StringMixin`` 共享 API 回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class BytesSequenceTests(TestCaseMixin):
  _testTag = 10

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
  _testTag = 20

  @override
  def test(self):
    # ``count`` / ``find`` / ``rfind`` / ``startsWith`` / ``endsWith``（KMP 路径）
    hay: bytes = b"spam, spam, eggs"
    self.assertEqual(hay.count(b"spam"), 2)
    self.assertEqual(hay.find(b"eggs"), 12)
    self.assertEqual(hay.rfind(b"spam"), 6)
    self.assertTrue(hay.startsWith(b"spam"))
    self.assertTrue(hay.endsWith(b"eggs"))


class BytesSplitTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    # ``split`` / ``rsplit`` / ``partition`` / ``replace``
    parts: list[bytes] = []
    parts.append(b"a")
    parts.append(b"b")
    parts.append(b"c")
    self.assertEqual(b"a,b,c".split(b","), parts)
    wsParts: list[bytes] = []
    wsParts.append(b"a")
    wsParts.append(b"b")
    self.assertEqual(b"  a  b  ".split(), wsParts)
    rsParts: list[bytes] = []
    rsParts.append(b"a|b")
    rsParts.append(b"c")
    self.assertEqual(b"a|b|c".rsplit(b"|", 1), rsParts)
    xparts: list[bytes] = []
    for part in b"a,b,c".xsplit(b","):
      xparts.append(part)
    self.assertEqual(xparts, parts)
    xrs: list[bytes] = []
    for part in b"a|b|c".xrsplit(b"|", 1):
      xrs.append(part)
    self.assertEqual(xrs, rsParts)
    xlines: list[bytes] = []
    for line in b"a\nb".xsplitLines():
      xlines.append(line)
    self.assertEqual(xlines, b"a\nb".splitLines())
    part: bytes = b"a=b".partition(b"=")[0]
    self.assertEqual(part, b"a")
    self.assertEqual(b"a=b".partition(b"=")[1], b"=")
    self.assertEqual(b"a=b".partition(b"=")[2], b"b")
    self.assertEqual(b"x".replace(b"x", b"y"), b"y")
    self.assertEqual(b"a,b,c".splitPrefix(b","), b"a")
    self.assertEqual(b"a,b,c".splitSuffix(b","), b"b,c")
    self.assertEqual(b"a|b|c".rsplitPrefix(b"|"), b"a|b")
    self.assertEqual(b"a|b|c".rsplitSuffix(b"|"), b"c")
    self.assertEqual(b"  a  b  ".splitPrefix(), b"a")
    self.assertEqual(b"  a  b  ".rsplitSuffix(), b"b")


class BytesStripTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    # ``strip`` / ``removePrefix`` / ``removeSuffix``
    ws: bytes = b"   hi   "
    self.assertEqual(ws.strip(), b"hi")
    self.assertEqual(b"pre_hook".removePrefix(b"pre_"), b"hook")
    self.assertEqual(b"file.txt".removeSuffix(b".txt"), b"file")
    self.assertEqual(b"\n  a\n    b\n".stripLines(1), b" a\n   b")


class BytesJoinDecodeTests(TestCaseMixin):
  _testTag = 50

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
  _testTag = 60

  @override
  def test(self):
    # ``bytes(n)`` 零填充构造
    z: bytes = bytes(4)
    self.assertEqual(len(z), 4)
    self.assertEqual(z[0], 0)
    self.assertEqual(z[3], 0)


class BytesTranslateTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    # ``makeTrans`` / ``translate``（含 delete 表项）
    tbl: dict[byte, byte] = bytes.makeTrans(b"ab", b"AB")
    self.assertEqual(b"abc".translate(tbl), b"ABc")
    self.assertEqual(b"abc".translate(tbl, delete=b""), b"ABc")
    self.assertEqual(b"abc".translate(tbl, delete=b"c"), b"AB")
    delTbl: dict[byte, byte] = {}
    delTbl[ord("b")] = 0xFF
    self.assertEqual(b"abc".translate(delTbl), b"ac")


class BytesStartswithListTests(TestCaseMixin):
  _testTag = 80

  @override
  def test(self):
    # ``startsWith`` / ``endsWith`` 多段 ``list[bytes]`` 与 ``byte[:]`` 缓冲
    prefixes: list[bytes] = []
    prefixes.append(b"spam")
    prefixes.append(b"ham")
    self.assertTrue(b"spam eggs".startsWith(prefixes))
    pref: byte[:] = b"egg"
    self.assertTrue(b"eggs".startsWith(pref))
    prefArr: bytes[:] = new(2)
    prefArr[0] = b"spam"
    prefArr[1] = b"ham"
    self.assertTrue(b"spam eggs".startsWith(prefArr))
    sufArr: bytes[:] = new(2)
    sufArr[0] = b"eggs"
    sufArr[1] = b"ham"
    self.assertTrue(b"spam eggs".endsWith(sufArr))
    self.assertFalse(b"spam egg".endsWith(sufArr))


class BytesGlobTests(TestCaseMixin):
  _testTag = 85

  @override
  def test(self):
    self.assertTrue(b"readme.txt".glob(b"*.txt"))
    self.assertTrue(b"readme.txt".glob(b"*.TXT"))
    self.assertFalse(b"readme.txt".glob(b"*.TXT", False))
    self.assertTrue(b"abc".glob(b"a?c"))


class BytesCaseTests(TestCaseMixin):
  _testTag = 90

  @override
  def test(self):
    # 大小写、``capitalize``、``expandTabs``、谓词、``ljust`` / ``zfill``
    self.assertEqual(b"ab".upper(), b"AB")
    self.assertEqual(b"AB".lower(), b"ab")
    self.assertEqual(b"hello".capitalize(), b"Hello")
    self.assertEqual(b"a\tb".expandTabs(4).find(b"   "), 1)
    self.assertTrue(b"abc1".isAlnum())
    self.assertTrue(b"abc".isAlpha())
    self.assertTrue(b"ascii".isAscii())
    self.assertTrue(b"123".isDigit())
    self.assertTrue(b"lower".isLower())
    self.assertTrue(b" \t".isSpace())
    self.assertTrue(b"UPPER".isUpper())
    self.assertEqual(b"x".ljust(3), b"x  ")
    self.assertEqual(b"42".zfill(5), b"00042")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
