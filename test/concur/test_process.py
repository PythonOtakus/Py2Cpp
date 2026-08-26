"""``py2cpp.concur.process``：callable ``Process`` / ``ProcessPool`` 与跨进程 IPC。"""
from py2cpp import *
from py2cpp.concur.process import Process, ProcessChannel, ProcessEvent, ProcessMutex, ProcessPool, ProcessSemaphore, SharedMemory
from py2cpp.concur.thread import Future, Thread
from py2cpp.system.time import perfCounter, sleep
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@copyable
class Box:
  value: int = 0


def _noop() -> None:
  return


def _markBox(box: Box) -> None:
  box.value = 7


def _signalChildDone() -> None:
  done: ProcessEvent = new("Local\\py2cpp-process-child-done")
  done.set()


def _poolAdd() -> int:
  return 21


def _poolMul() -> int:
  return 3


def _tryMutexPeer(name: str, peer: Box) -> None:
  mutex: ProcessMutex = new(name)
  if mutex.acquire(timeout=1.0):
    peer.value = 1
    mutex.release()


class ProcessLifecycleTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    done: ProcessEvent = new("Local\\py2cpp-process-child-done")
    done.clear()
    process: Process = new(_signalChildDone, "worker")
    process.start()
    self.assertTrue(process.pid > 0)
    self.assertTrue(process.alive)
    self.assertTrue(done.wait(timeout=5.0))
    process.join()
    self.assertFalse(process.alive)
    self.assertEqual(process.exitCode, 0)
    process.close()


class ProcessRunTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    box: Box = new()
    process: Process = new(lambda: _markBox(box))
    process.run()
    self.assertEqual(box.value, 7)
    self.assertFalse(process.alive)


class ProcessNoopJoinTests(TestCaseMixin):
  _testTag = 15

  @override
  def test(self):
    process: Process = new(_noop)
    process.start()
    process.join(timeout=5.0)
    self.assertEqual(process.exitCode, 0)
    process.close()


class ProcessPoolTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    pool: ProcessPool[int] = new(2)
    first: Future[int] = pool.submit(_poolAdd)
    second: Future[int] = pool.submit(_poolMul)
    self.assertEqual(first.result(timeout=5.0), 21)
    self.assertEqual(second.result(timeout=5.0), 3)
    mapped_fns: list[Callable[[], int]] = []
    mapped_fns.append(_poolAdd)
    mapped_fns.append(_poolMul)
    mapped: list[int] = pool.map(mapped_fns)
    self.assertEqual(len(mapped), 2)
    self.assertEqual(mapped[0], 21)
    self.assertEqual(mapped[1], 3)
    pool.shutdown()


class ProcessPoolShutdownTests(TestCaseMixin):
  _testTag = 25

  @override
  def test(self):
    pool: ProcessPool[int] = new(1)
    self.assertEqual(pool.submit(_poolAdd).result(timeout=5.0), 21)
    pool.shutdown()


class ProcessSynchronizationTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    syncKey: str = "Local\\py2cpp-process-sync-" + str(int(perfCounter() * 1000000.0))
    eventOne: ProcessEvent = new(syncKey + "-event")
    eventTwo: ProcessEvent = new(syncKey + "-event")
    self.assertTrue(eventOne.created)
    self.assertFalse(eventTwo.created)
    self.assertFalse(eventTwo.wait(timeout=0.0))
    eventOne.set()
    self.assertTrue(eventTwo.wait(timeout=0.0))
    eventTwo.clear()
    self.assertFalse(eventOne.isSet())

    semOne: ProcessSemaphore = new(syncKey + "-semaphore", 1, 2)
    semTwo: ProcessSemaphore = new(syncKey + "-semaphore", 0, 2)
    self.assertTrue(semOne.created)
    self.assertFalse(semTwo.created)
    self.assertTrue(semTwo.acquire(timeout=0.0))
    semOne.release()
    self.assertTrue(semTwo.acquire(timeout=0.0))

    mutexOne: ProcessMutex = new(syncKey + "-mutex")
    mutexTwo: ProcessMutex = new(syncKey + "-mutex")
    self.assertTrue(mutexOne.created)
    self.assertFalse(mutexTwo.created)
    self.assertTrue(mutexOne.acquire(timeout=0.0))
    peer: Box = new()
    mutexName: str = syncKey + "-mutex"
    waiter: Thread = new(lambda: _tryMutexPeer(mutexName, peer))
    waiter.start()
    sleep(0.02)
    self.assertEqual(peer.value, 0)
    mutexOne.release()
    waiter.join(timeout=1.0)
    self.assertEqual(peer.value, 1)


class SharedMemoryTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    left: SharedMemory = new("Local\\py2cpp-shared-memory", 8)
    right: SharedMemory = new("Local\\py2cpp-shared-memory", 8)
    self.assertTrue(left.created)
    self.assertFalse(right.created)
    view = left.view
    view[0] = 11
    view[1] = 22
    self.assertEqual(right.view[0], 11)
    self.assertEqual(right.view[1], 22)
    left.close()
    right.close()


class ProcessChannelTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    sender: ProcessChannel = new("Local\\py2cpp-process-channel", 16)
    receiver: ProcessChannel = new("Local\\py2cpp-process-channel", 16)
    self.assertTrue(sender.created)
    self.assertFalse(receiver.created)
    payload: byte[:] = new(3)
    payload[0] = 7
    payload[1] = 21
    payload[2] = 99
    sender.send(payload)
    got: byte[:] = receiver.receive(timeout=0.0)
    self.assertEqual(len(got), 3)
    self.assertEqual(got[0], 7)
    self.assertEqual(got[1], 21)
    self.assertEqual(got[2], 99)
    sender.close()
    receiver.close()


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
