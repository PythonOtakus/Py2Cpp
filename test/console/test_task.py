"""``console.task`` / ``console.popen``：``Console`` 与 ``Popen``。"""
from py2cpp import *
from py2cpp.console.popen import CompletedProcess, Pipe, Popen
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


class ConsoleRunShellExitCodeTests(TestCaseMixin):
  _testTag = 35

  @override
  def test(self):
    result: CompletedProcess = Console.run("cmd.exe /c exit /b 7", captureOutput=True, shell=True)
    self.assertEqual(result.returnCode, 7)


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


class PopenPipeTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "echo", "pipe_ok"]
    task: Popen = new(args, "", None, 0, Pipe, Pipe)
    task.start()
    done: CompletedProcess = task.communicate()
    self.assertEqual(done.returnCode, 0)
    self.assertTrue("pipe_ok" in done.stdout)


class PopenLifecycleTests(TestCaseMixin):
  _testTag = 80

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "exit /b 7"]
    process: Popen = new(args)
    process.start()
    self.assertTrue(process.pid > 0)
    self.assertTrue(process.running)
    self.assertEqual(process.wait(), 7)
    self.assertFalse(process.running)
    self.assertEqual(process.returnCode, 7)
    self.assertEqual(process.poll(), 7)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
