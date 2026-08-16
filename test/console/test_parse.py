"""``console.parse``：``ArgumentParserMixin.parse[T]`` 与 Meta 字段。"""
from py2cpp import *
from py2cpp.console.parse import ArgumentParserMixin, FlagArgMeta, OptArgMeta, PosArgMeta
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@dataclass
class BuildArgs:
  source: str @PosArgMeta(help="src")
  jobs: int @OptArgMeta(short="-j") = 1
  release: bool @FlagArgMeta() = False


@dataclass
class FlagArgs:
  source: str @PosArgMeta()
  verbose: bool @FlagArgMeta(short="-v") = False
  quiet: bool @FlagArgMeta(short="-q") = False


@dataclass
class EqArgs:
  mode: str @OptArgMeta(short="-m") = "dev"


class ParseBasicTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    argv: list[str] = ["src", "-j", "4", "--release"]
    args: BuildArgs = ArgumentParserMixin.parse[BuildArgs](argv)
    self.assertEqual(args.source, "src")
    self.assertEqual(args.jobs, 4)
    self.assertTrue(args.release)


class ParseDefaultsTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    argv: list[str] = ["only"]
    args: BuildArgs = ArgumentParserMixin.parse[BuildArgs](argv)
    self.assertEqual(args.source, "only")
    self.assertEqual(args.jobs, 1)
    self.assertFalse(args.release)


class ParseLongOptTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    argv: list[str] = ["x", "--jobs", "8"]
    args: BuildArgs = ArgumentParserMixin.parse[BuildArgs](argv)
    self.assertEqual(args.jobs, 8)


class ParseEqOptTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    argv: list[str] = ["--mode=release"]
    args: EqArgs = ArgumentParserMixin.parse[EqArgs](argv)
    self.assertEqual(args.mode, "release")


class ParseCombinedFlagsTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    argv: list[str] = ["-vq", "src"]
    args: FlagArgs = ArgumentParserMixin.parse[FlagArgs](argv)
    self.assertEqual(args.source, "src")
    self.assertTrue(args.verbose)
    self.assertTrue(args.quiet)


class ParseDashDashTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    argv: list[str] = ["--", "--jobs"]
    args: BuildArgs = ArgumentParserMixin.parse[BuildArgs](argv)
    self.assertEqual(args.source, "--jobs")
    self.assertEqual(args.jobs, 1)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
