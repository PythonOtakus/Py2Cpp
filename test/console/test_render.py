"""``console.render``：表格、日志 MemorySink、Progress、paint。"""
from py2cpp import *
from py2cpp.console import setColorEnabled, supportsColor, terminalSize
from py2cpp.console.render import (
  AnsiColorEnum,
  LogLevelEnum,
  Logger,
  MemorySink,
  Progress,
  Style,
  Table,
  paint,
)
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class StyleConstructTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    style: Style = new(fg=AnsiColorEnum.Red, bold=True)
    self.assertEqual(style.fg, AnsiColorEnum.Red)
    self.assertTrue(style.bold)


class TableRenderTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    headers: list[str] = ["a", "b"]
    t: Table = new(headers, 10)
    row: list[str] = ["1", "2"]
    t.addRow(row)
    text: str = t.render()
    self.assertTrue("a" in text)
    self.assertTrue("1" in text)


class LoggerMemoryTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    # Debug=10；勿把 ``int(Enum)`` 嵌进 ``new(...)``（易触发 MSVC 栈 cookie 崩溃）。
    log: Logger = new("t", 10)
    mem: MemorySink = new(10)
    log.addMemorySink(mem)
    log.info("hello", "k=v")
    self.assertEqual(len(mem.records), 1)
    self.assertEqual(mem.records[0].message, "hello")
    self.assertTrue("k=v" in mem.records[0].fields)


class ProgressContextTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    with Progress() as progress:
      task = progress.addTask("job", 2)
      progress.advance(task)
      progress.complete(task)
    self.assertTrue(True)


class PaintNoColorTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    setColorEnabled(False)
    style: Style = new(fg=AnsiColorEnum.Red, bold=True)
    text: str = paint("x", style)
    self.assertEqual(text, "x")
    self.assertFalse(supportsColor())
    size: (int, int) = terminalSize()
    self.assertTrue(size[0] >= 1)
    self.assertTrue(size[1] >= 1)
    setColorEnabled(True)
    setColorEnabled(False)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
