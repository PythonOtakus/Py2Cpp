"""``py2cpp.concur.process``：外部进程基础生命周期回归。"""
from py2cpp import *
from py2cpp.concur.process import CompletedProcess, Pipe, Process, ProcessPool, run as processRun
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class ProcessLifecycleTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "exit /b 7"]
    process: Process = new(args)
    process.start()
    self.assertTrue(process.pid > 0)
    self.assertTrue(process.running)
    self.assertEqual(process.wait(), 7)
    self.assertFalse(process.running)
    self.assertEqual(process.returnCode, 7)
    self.assertEqual(process.poll(), 7)


class ProcessPipeTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "echo process-output"]
    process: Process = new(args, "", None, 0, Pipe, Pipe)
    process.start()
    completed = process.communicate()
    self.assertEqual(completed.returnCode, 0)
    self.assertEqual(completed.stdout, "process-output\r\n")
    self.assertEqual(completed.stderr, "")


class ProcessRunTests(TestCaseMixin):
  _testTag = 15

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "echo process-run"]
    completed: CompletedProcess = processRun(args)
    self.assertEqual(completed.returnCode, 0)
    self.assertTrue("process-run" in completed.stdout)

class ProcessContextTests(TestCaseMixin):
  _testTag = 18

  @override
  def test(self):
    args: list[str] = ["cmd.exe", "/c", "exit /b 0"]
    process: Process = new(args)
    with process as active:
      self.assertTrue(active.pid > 0)
      self.assertTrue(active.running)
    self.assertEqual(process.wait(), 0)
    pool: ProcessPool = new(1)
    with pool:
      completed: CompletedProcess = pool.submit(args).result(timeout=2.0)
      self.assertEqual(completed.returnCode, 0)

class ProcessPoolTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    pool: ProcessPool = new(2)
    oneArgs: list[str] = ["cmd.exe", "/c", "echo pool-one"]
    twoArgs: list[str] = ["cmd.exe", "/c", "echo pool-two"]
    first = pool.submit(oneArgs)
    second = pool.submit(twoArgs)
    self.assertEqual(first.result(timeout=2.0).returnCode, 0)
    self.assertTrue("pool-two" in second.result(timeout=2.0).stdout)
    commands: list[list[str]] = [oneArgs, twoArgs]
    completed = pool.map(commands)
    self.assertEqual(len(completed), 2)
    self.assertTrue("pool-one" in completed[0].stdout)
    self.assertTrue("pool-two" in completed[1].stdout)
    pool.shutdown()

suite = TestSuite()
suite.addTests([
  ProcessLifecycleTests(),
  ProcessPipeTests(),
  ProcessRunTests(),
  ProcessContextTests(),
  ProcessPoolTests(),
])
TextTestRunner().run(suite)