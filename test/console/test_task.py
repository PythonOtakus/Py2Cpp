"""``console.task``：``Console.system`` / ``popen`` / ``run``。"""
from py2cpp import *
from py2cpp.concur.process import CompletedProcess, Pipe, Process
from py2cpp.console.task import Console
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class ConsoleSystemTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    code: int = Console.system("echo py2cpp_console_ok")
    self.assertEqual(code, 0)


class ConsolePopenTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    reader = Console.popen("echo hello_popen")
    out: str = reader.read()
    self.assertTrue("hello_popen" in out)


class ConsoleRunShellTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    result: CompletedProcess = Console.run("echo run_shell", shell=True)
    self.assertEqual(result.returnCode, 0)


class ConsoleRunListTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "echo", "hello_run"]
    result: CompletedProcess = Console.run(args, captureOutput=True)
    self.assertEqual(result.returnCode, 0)
    self.assertTrue("hello_run" in result.stdout)


class ConsoleRunStartFailTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    args: list[str] = ["py2cpp_missing_exe_zzz"]
    caught: bool = False
    try:
      Console.run(args, captureOutput=True)
    except OSError:
      caught = True
    self.assertTrue(caught)


class ConsoleRunTimeoutTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "ping", "-n", "20", "127.0.0.1"]
    caught: bool = False
    try:
      Console.run(args, captureOutput=True, timeout=0.2)
    except RuntimeError:
      caught = True
    self.assertTrue(caught)


class TaskPipeTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "echo", "pipe_ok"]
    task: Process = new(args, "", None, 0, Pipe, Pipe)
    task.start()
    done: CompletedProcess = task.communicate()
    self.assertEqual(done.returnCode, 0)
    self.assertTrue("pipe_ok" in done.stdout)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
