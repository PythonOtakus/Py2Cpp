"""``str`` 回归：序列 API、查找、split、哈希、``format`` / f-string、字面量内联。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class StrSequenceTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    # ``__len__``、布尔真值、下标/切片（含步长与 ``[::-1]``）、``+`` / ``*`` / ``in`` / ``==``
    s: str = "hello"
    self.assertEqual(len(s), 5)
    self.assertTrue(s)
    self.assertFalse("")
    self.assertEqual(int(s[0]), 104)
    self.assertEqual(int(s[-1]), 111)
    self.assertEqual(s[1:4], "ell")
    ab: str = "abcdef"
    self.assertEqual(ab[:-1:2], "ace")
    ba: str = "abc"
    self.assertEqual(ba[::-1], "cba")
    self.assertEqual(s + "!", "hello!")
    self.assertTrue(s == "hello")
    self.assertTrue("ll" in s)
    self.assertEqual(s * 2, "hellohello")
    self.assertEqual("x" * 3, "xxx")


class StrCaseTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    self.assertEqual("hello WORLD".capitalize(), "Hello world")
    self.assertEqual("Hello".casefold(), "hello")
    self.assertEqual("hi".center(6), "  hi  ")
    self.assertEqual("hi".center(6, 46), "..hi..")
    self.assertEqual("ab".lower(), "ab")
    self.assertEqual("AB".upper(), "AB")
    self.assertEqual("AbC".swapcase(), "aBc")
    self.assertEqual("hello world".title(), "Hello World")
    self.assertEqual("hi".ljust(5), "hi   ")
    self.assertEqual("hi".rjust(5), "   hi")
    self.assertEqual("42".zfill(5), "00042")
    self.assertEqual("-42".zfill(5), "-0042")


class StrFindTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    hay: str = "spam, spam, eggs"
    self.assertEqual(hay.count("spam"), 2)
    self.assertEqual(hay.find("eggs"), 12)
    self.assertEqual(hay.find("ham"), -1)
    self.assertEqual(hay.rfind("spam"), 6)
    self.assertEqual(hay.index("spam"), 0)
    self.assertTrue(hay.startswith("spam"))
    self.assertTrue(hay.endswith("eggs"))


class StrKmpPathTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    needle: str = "needle"
    unit: str = "ab"
    hay: str = unit * 80 + needle + unit * 80
    self.assertEqual(hay.find(needle), 160)
    self.assertEqual(hay.rfind(needle), 160)
    self.assertEqual(hay.count(unit), 160)
    self.assertEqual(hay.replace(needle, "z"), unit * 80 + "z" + unit * 80)
    parts: str = (unit + ",") * 40 + "tail"
    self.assertEqual(len(parts.split(",")), 41)
    self.assertEqual(parts.rsplit(",", 1)[1], "tail")
    p: (str, str, str) = hay.partition(needle)
    self.assertEqual(p[0], unit * 80)
    self.assertEqual(p[2], unit * 80)


class StrStripTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    ws: str = "   spacious   "
    self.assertEqual(ws.strip(), "spacious")
    self.assertEqual(ws.lstrip(), "spacious   ")
    self.assertEqual(ws.rstrip(), "   spacious")
    self.assertEqual("www.example.com".strip("cmowz."), "example")
    self.assertEqual("TestHook".removeprefix("Test"), "Hook")
    self.assertEqual("MiscTests".removesuffix("Tests"), "Misc")
    self.assertEqual("spam eggs".replace("spam", "ham"), "ham eggs")
    self.assertEqual("spam spam".replace("spam", "x", 1), "x spam")


class StrSplitTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    csv: str = "a,b,c"
    parts: list[str] = csv.split(",")
    self.assertEqual(len(parts), 3)
    self.assertEqual(parts[0], "a")
    self.assertEqual(parts[2], "c")
    ws_parts: list[str] = "  a  b  ".split()
    self.assertEqual(len(ws_parts), 2)
    self.assertEqual(ws_parts[0], "a")
    rparts: list[str] = "a b c".rsplit(" ", 1)
    self.assertEqual(len(rparts), 2)
    self.assertEqual(rparts[0], "a b")
    self.assertEqual(rparts[1], "c")
    lines: list[str] = "a\nb".splitlines()
    self.assertEqual(len(lines), 2)
    jlist: list[str] = []
    jlist.append("a")
    jlist.append("b")
    self.assertEqual("-".join(jlist), "a-b")


class StrXSplitTests(TestCaseMixin):
  _test_tag = 61

  @override
  def test(self):
    csv: str = "a,b,c"
    collected: list[str] = []
    for part in csv.xsplit(","):
      collected.append(part)
    self.assertEqual(collected, csv.split(","))
    ws_collected: list[str] = []
    for part in "  a  b  ".xsplit():
      ws_collected.append(part)
    self.assertEqual(ws_collected, "  a  b  ".split())
    g = csv.xsplit(",")
    first: str = ""
    for part in g:
      first = part
      break
    self.assertEqual(first, "a")
    limited: list[str] = []
    for part in csv.xsplit(",", 1):
      limited.append(part)
    self.assertEqual(limited, csv.split(",", 1))
    r_collected: list[str] = []
    for part in "a b c".xrsplit(" ", 1):
      r_collected.append(part)
    self.assertEqual(r_collected, "a b c".rsplit(" ", 1))
    r_ws: list[str] = []
    for part in "  a  b  ".xrsplit(1):
      r_ws.append(part)
    self.assertEqual(r_ws, "  a  b  ".rsplit(1))
    sep_parts: list[str] = []
    for part in "a,b,".xsplit(","):
      sep_parts.append(part)
    self.assertEqual(sep_parts, "a,b,".split(","))


class StrXSplitlinesTests(TestCaseMixin):
  _test_tag = 62

  @override
  def test(self):
    lines: list[str] = []
    for line in "a\nb\r\nc".xsplitlines():
      lines.append(line)
    self.assertEqual(lines, "a\nb\r\nc".splitlines())
    kept: list[str] = []
    for line in "a\n".xsplitlines(True):
      kept.append(line)
    self.assertEqual(kept, "a\n".splitlines(True))
    empty: list[str] = []
    for line in "".xsplitlines():
      empty.append(line)
    self.assertEqual(len(empty), 0)


class StrPartitionTests(TestCaseMixin):
  _test_tag = 70

  @override
  def test(self):
    p: (str, str, str) = "a-b".partition("-")
    self.assertEqual(p[0], "a")
    self.assertEqual(p[1], "-")
    self.assertEqual(p[2], "b")
    rp: (str, str, str) = "a-b-c".rpartition("-")
    self.assertEqual(rp[2], "c")


class StrSplitAffixTests(TestCaseMixin):
  _test_tag = 71

  @override
  def test(self):
    csv: str = "a,b,c"
    self.assertEqual(csv.split_prefix(","), csv.split(",", 1)[0])
    self.assertEqual(csv.split_suffix(","), csv.split(",", 1)[1])
    self.assertEqual(csv.rsplit_prefix(","), csv.rsplit(",", 1)[0])
    self.assertEqual(csv.rsplit_suffix(","), csv.rsplit(",", 1)[-1])
    self.assertEqual("no_sep".split_prefix(","), "no_sep")
    self.assertEqual("no_sep".split_suffix(","), "")
    self.assertEqual("no_sep".rsplit_prefix(","), "")
    self.assertEqual("no_sep".rsplit_suffix(","), "no_sep")
    ws: str = "  a  b  "
    self.assertEqual(ws.split_prefix(), ws.split(maxsplit=1)[0])
    self.assertEqual(ws.split_suffix(), ws.split(maxsplit=1)[1])
    self.assertEqual(ws.rsplit_prefix(), ws.rsplit(maxsplit=1)[0])
    self.assertEqual(ws.rsplit_suffix(), ws.rsplit(maxsplit=1)[-1])
    self.assertEqual("a".split_suffix(), "")
    self.assertEqual("a".rsplit_suffix(), "a")


class StrPredicateTests(TestCaseMixin):
  _test_tag = 80

  @override
  def test(self):
    self.assertTrue("abc1".isalnum())
    self.assertTrue("abc".isalpha())
    self.assertTrue("ascii".isascii())
    self.assertTrue("123".isdecimal())
    self.assertTrue("9".isdigit())
    self.assertTrue("var_1".isidentifier())
    self.assertTrue("lower".islower())
    self.assertTrue("123".isnumeric())
    self.assertTrue("a b".isprintable())
    self.assertTrue(" \t".isspace())
    self.assertTrue("Hello World".istitle())
    self.assertTrue("UPPER".isupper())


class StrMiscTests(TestCaseMixin):
  _test_tag = 90

  @override
  def test(self):
    enc: bytes = "Hi".encode()
    self.assertEqual(len(enc), 2)
    bsum: int = 0
    for c in enc:
      bsum += int(c)
    self.assertEqual(bsum, int(ord("H")) + int(ord("i")))
    subsum: int = 0
    for c in "abcde"[1:4]:
      subsum += int(c)
    self.assertEqual(subsum, int(ord("b")) + int(ord("c")) + int(ord("d")))
    tabbed: str = "a\tb".expandtabs(4)
    self.assertEqual(tabbed.find("   "), 1)
    tbl: dict[char, char] = str.maketrans("ab", "AB")
    self.assertEqual("abc".translate(tbl), "ABc")


class StrStartswithListTests(TestCaseMixin):
  _test_tag = 100

  @override
  def test(self):
    prefixes: list[str] = []
    prefixes.append("http://")
    prefixes.append("https://")
    self.assertTrue("https://x.com".startswith(prefixes))
    self.assertFalse("ftp://x".startswith(prefixes))
    pref: char[:] = "spam"
    self.assertTrue("spam eggs".startswith(pref))
    pref_arr: str[:] = new(2)
    pref_arr[0] = "http://"
    pref_arr[1] = "https://"
    self.assertTrue("https://x.com".startswith(pref_arr))
    self.assertFalse("ftp://x".startswith(pref_arr))
    suf_arr: str[:] = new(2)
    suf_arr[0] = ".txt"
    suf_arr[1] = ".md"
    self.assertTrue("readme.txt".endswith(suf_arr))
    self.assertFalse("readme.py".endswith(suf_arr))


class StrGlobTests(TestCaseMixin):
  _test_tag = 105

  @override
  def test(self):
    self.assertTrue("readme.txt".glob("*.txt"))
    self.assertTrue("readme.txt".glob("*.TXT"))
    self.assertFalse("readme.txt".glob("*.TXT", False))
    self.assertTrue("abc".glob("a?c"))
    self.assertTrue("abc".glob("a??"))
    self.assertTrue("a.c".glob("?.c"))
    self.assertFalse("x".glob("[abc]"))
    self.assertTrue("x".glob("[!abc]"))
    self.assertTrue("]".glob("[]]"))
    self.assertFalse("x".glob("[!]"))
    self.assertTrue("file.txt".glob("*"))
    self.assertTrue("".glob("*"))
    self.assertFalse("abc".glob("abcd"))
    self.assertTrue("A\\B".glob("a/b", True))
    self.assertFalse("A\\B".glob("a/b", False))


class CharArrayLiteralTests(TestCaseMixin):
  _test_tag = 110

  @override
  def test(self):
    buf: char[:] = "Hi"
    self.assertEqual(len(buf), 2)
    self.assertEqual(buf[0], 72)
    self.assertEqual(buf[1], 105)
    self.assertEqual(str(buf), "Hi")
    fixed: char[:3] = "abc"
    self.assertEqual(len(fixed), 3)
    self.assertEqual(fixed[2], 99)


class StrFloatScalarInitTests(TestCaseMixin):
  _test_tag = 120

  @override
  def test(self):
    self.assertEqual(str(42), "42")
    self.assertEqual(str(-7), "-7")
    self.assertEqual(str(1.5), "1.5")
    self.assertEqual(str(10000000000), "10000000000")


class StrHashCompareTests(TestCaseMixin):
  _test_tag = 130

  @override
  def test(self):
    a: str = "id"
    b: str = "id"
    c: str = "name"
    self.assertEqual(hash(a), hash(b))
    self.assertEqual(hash(a), hash(a))
    self.assertTrue(a == b)
    self.assertFalse(a == c)
    self.assertTrue(a != c)
    self.assertTrue(a < c)
    self.assertTrue(c > a)
    self.assertTrue(a <= b)
    self.assertTrue(b >= a)


class ModDivTests(TestCaseMixin):
  _test_tag = 140

  @override
  def test(self):
    self.assertEqual(7 % 3, 1)
    self.assertEqual(-7 % 3, 2)
    self.assertEqual(7 // 3, 2)
    self.assertEqual(-7 // 3, -3)
    qr: (int, int) = divmod(7, 3)
    self.assertEqual(qr[0], 2)
    self.assertEqual(qr[1], 1)
    self.assertEqual(divmod(-7, 3)[0], -3)
    self.assertEqual(divmod(-7, 3)[1], 2)
    self.assertEqual(format(7 / 2, ""), "3.5")
    self.assertEqual("%d %d" % (1, 2), "1 2")
    self.assertEqual("%d" % 42, "42")


class A:
  pass


class B:
  def __str__(self) -> str:
    return "custom-str"


class DefaultReprTests(TestCaseMixin):
  _test_tag = 200

  @override
  def test(self):
    a: A = new()
    ra = repr(a)
    self.assertTrue(ra.startswith("<__main__.A object at 0x"))
    sa = str(a)
    self.assertEqual(sa, ra)


class CustomStrTests(TestCaseMixin):
  _test_tag = 210

  @override
  def test(self):
    b: B = new()
    self.assertEqual(str(b), "custom-str")
    rb = repr(b)
    self.assertTrue(rb.startswith("<__main__.B object at 0x"))


class FormatIntTests(TestCaseMixin):
  _test_tag = 220

  @override
  def test(self):
    self.assertEqual(format(7, ""), "7")
    self.assertEqual(format(7, "d"), "7")
    self.assertEqual(format(7, "02d"), "07")
    self.assertEqual(format(0, "05d"), "00000")
    self.assertEqual(format(-3, "d"), "-3")
    self.assertEqual(f"{42:02d}", "42")
    self.assertEqual(f"{7:02d}", "07")
    self.assertEqual(f"{0:05d}", "00000")


class FormatFloatTests(TestCaseMixin):
  _test_tag = 230

  @override
  def test(self):
    self.assertEqual(format(1.5, ""), "1.5")
    self.assertEqual(format(3.14159, ".3f"), "3.142")
    self.assertEqual(format(2.5, ".1f"), "2.5")
    self.assertEqual(format(1.25, ".2f"), "1.25")
    self.assertEqual(f"{3.14159:.3f}", "3.142")
    self.assertEqual(f"{2.5:.1f}", "2.5")
    self.assertEqual(f"{1.25:.2f}", "1.25")


class FormatBoolTests(TestCaseMixin):
  _test_tag = 240

  @override
  def test(self):
    self.assertEqual(format(True, ""), "True")
    self.assertEqual(format(False, ""), "False")
    self.assertEqual(f"{True}", "True")
    self.assertEqual(f"{False}", "False")


class FormatStrTests(TestCaseMixin):
  _test_tag = 250

  @override
  def test(self):
    s: str = "hello"
    self.assertEqual(format(s, ""), "hello")
    self.assertEqual(f"{s}", "hello")
    self.assertEqual(f"prefix{s}suffix", "prefixhellosuffix")


class FormatListTests(TestCaseMixin):
  _test_tag = 260

  @override
  def test(self):
    empty: list[int] = []
    self.assertEqual(format(empty, ""), "[]")
    self.assertEqual(f"{empty}", "[]")
    xs: list[int] = [1, 2, 3]
    self.assertEqual(format(xs, ""), "[1, 2, 3]")
    self.assertEqual(f"{xs}", "[1, 2, 3]")
    ys: list[str] = ["a", "b"]
    self.assertEqual(format(ys, ""), "['a', 'b']")


class FormatDictTests(TestCaseMixin):
  _test_tag = 270

  @override
  def test(self):
    empty: dict[int, int] = {}
    self.assertEqual(format(empty, ""), "{}")
    d: dict[int, int] = {}
    d[1] = 10
    self.assertEqual(format(d, ""), "{1: 10}")
    self.assertEqual(f"{d}", "{1: 10}")


class FormatDequeTests(TestCaseMixin):
  _test_tag = 280

  @override
  def test(self):
    q: deque[int] = []
    q.append(1)
    q.append(2)
    self.assertEqual(format(q, ""), "deque([1, 2])")
    self.assertEqual(f"{q}", "deque([1, 2])")


class FormatCombinedTests(TestCaseMixin):
  _test_tag = 290

  @override
  def test(self):
    x: float = 3.14159
    y: int = 7
    self.assertEqual(f"{x:.3f}{y:02d}", "3.14207")
    a: float = 1.5
    b: int = 3
    self.assertEqual(f"{a:.3f}{b:02d}", "1.50003")
    pi: float = 3.14159
    n: int = 42
    self.assertEqual(f"pi={pi:.3f}, n={n:04d}", "pi=3.142, n=0042")


class FormatStrFormatTests(TestCaseMixin):
  _test_tag = 300

  @override
  def test(self):
    x: float = 3.14159
    y: int = 7
    a: str = format(x, ".3f")
    b: str = format(y, "02d")
    self.assertEqual("{}{}".format(a, b), "3.14207")
    self.assertEqual("{} {}".format("a", "b"), "a b")
    parts: list[str] = ["x", "y"]
    self.assertEqual("{}-{}".format(parts[0], parts[1]), "x-y")


class FormatMixedFstringTests(TestCaseMixin):
  _test_tag = 310

  @override
  def test(self):
    xs: list[int] = [10, 20]
    self.assertEqual(f"len={len(xs)} {xs}", "len=2 [10, 20]")
    flag: bool = True
    self.assertEqual(f"ok={flag} val={42:d}", "ok=True val=42")


class StrLiteralFindTests(TestCaseMixin):
  _test_tag = 330

  @override
  def test(self):
    self.assertEqual("spam and eggs".find("eggs"), 9)
    self.assertEqual("spam and eggs".find("ham"), -1)
    self.assertEqual("abc".index("b"), 1)
    self.assertEqual("abcabc".rfind("abc"), 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
