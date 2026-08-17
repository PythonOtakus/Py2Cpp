"""``py2cpp.concur.thread`` 首版线程/Lock 回归。"""
from py2cpp import *
from py2cpp.concur.thread import Barrier, BoundedSemaphore, BrokenBarrierError, CancelledError, Condition, EmptyError, Event, FullError, Future, Lock, Queue, RLock, Semaphore, ShutDownError, Thread, ThreadPool, TimeoutError, atomic
from py2cpp.system.time import sleep
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

@copyable
class Box:
    value: int = 0
_barrierActionCount: atomic[int] = new(0)
_poolBlockStarted: Event = new()
_poolBlockRelease: Event = new()
_poolBlockValue: atomic[int] = new(0)

def setBox(box: Box) -> None:
    box.value = 42

def holdLock(lock: Lock, box: Box) -> None:
    lock.acquire()
    box.value = 7
    sleep(0.02)
    lock.release()

def addMany(counter: atomic[int], times: int) -> None:
    for _i in range(times):
        counter.fetchAdd(1)

def queueConsume(q: Queue[int], box: Box) -> None:
    box.value = q.get()
    q.taskDone()

def queueDelayedPut(q: Queue[int], value: int) -> None:
    sleep(0.02)
    q.put(value)

def registryWorker(ready: Event, release: Event, box: Box) -> None:
    current: Thread = Thread.current
    if current.ident != 0 and current.nativeId != 0 and (Thread.activeCount >= 2):
        box.value = 1
    ready.set()
    release.wait(timeout=1.0)

def rlockReleaseFromOther(lock: RLock, box: Box) -> None:
    try:
        lock.release()
    except RuntimeError:
        box.value = 1

def rlockAcquireAfterRelease(lock: RLock, box: Box) -> None:
    lock.acquire()
    box.value = 2
    lock.release()

def conditionWaiter(cond: Condition, ready: Event, box: Box) -> None:
    cond.acquire()
    ready.set()
    if cond.wait(timeout=1.0):
        box.value = 11
    cond.release()

def conditionRecursiveWaiter(cond: Condition, ready: Event, box: Box) -> None:
    cond.acquire()
    cond.acquire()
    ready.set()
    if cond.wait(timeout=1.0):
        box.value = 22
    cond.release()
    cond.release()

def conditionSetFlag(cond: Condition, box: Box) -> None:
    cond.acquire()
    box.value = 33
    cond.notifyAll()
    cond.release()

def eventWaiter(evt: Event, box: Box) -> None:
    if evt.wait(timeout=1.0):
        box.value = 44

def semaphoreWaiter(sem: Semaphore, box: Box) -> None:
    sem.acquire()
    box.value = 55
    sem.release()

def barrierWaiter(barrier: Barrier @ ref, ready: Event, done: Event, box: Box) -> None:
    ready.set()
    try:
        box.value = barrier.wait(timeout=1.0)
    except BrokenBarrierError:
        box.value = -1
    done.set()

def barrierRoundsWaiter(barrier: Barrier @ ref, rounds: int, counter: atomic[int]) -> None:
    for _i in range(rounds):
        barrier.wait(timeout=1.0)
        counter.fetchAdd(1)

def barrierBrokenWaiter(barrier: Barrier @ ref, ready: Event, box: Box) -> None:
    ready.set()
    try:
        barrier.wait(timeout=1.0)
    except BrokenBarrierError:
        box.value = 1

def barrierGlobalAction() -> None:
    _barrierActionCount.fetchAdd(1)

def waitBarrierWaiting(barrier: Barrier @ ref, n: int) -> bool:
    for _i in range(1000):
        if barrier.nWaiting == n:
            return True
        sleep(0.001)
    return barrier.nWaiting == n

def poolReturn21() -> int:
    return 21

def poolReturn1() -> int:
    return 1

def poolReturn99() -> int:
    return 99

def poolBlockGlobal() -> int:
    _poolBlockStarted.set()
    _poolBlockRelease.wait(timeout=1.0)
    return _poolBlockValue.load()

def poolRaise() -> int:
    raise RuntimeError('pool boom')
    return 0

class TLSBox:
    value: int @ thread_local = 0

    def bump(self) -> int:
        self.value += 1
        return self.value

def setTlsInWorker(box: Box) -> None:
    tls: TLSBox = new()
    TLSBox.value = 100
    box.value = tls.bump()

class ThreadBasicTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        box: Box = new()
        t: Thread = new(lambda: setBox(box))
        self.assertFalse(t.alive)
        t.start()
        self.assertTrue(t.ident != 0)
        self.assertTrue(t.nativeId != 0)
        t.join()
        self.assertEqual(box.value, 42)
        self.assertFalse(t.alive)
        t.join()

class ThreadStartErrorTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        box: Box = new()
        t: Thread = new(lambda: setBox(box))
        raised: bool = False
        try:
            t.join()
        except RuntimeError:
            raised = True
        self.assertTrue(raised)
        t.start()
        raised = False
        try:
            t.start()
        except RuntimeError:
            raised = True
        self.assertTrue(raised)
        t.join()
        raised = False
        try:
            bad: Thread = new(lambda: setBox(box), daemon=True)
        except RuntimeError:
            raised = True
        self.assertTrue(raised)

class IdentTests(TestCaseMixin):
    _testTag = 30

    @override
    def test(self):
        current: Thread = Thread.current
        self.assertTrue(current.ident != 0)
        self.assertTrue(current.nativeId != 0)

class ThreadRegistryTests(TestCaseMixin):
    _testTag = 35

    @override
    def test(self):
        main: Thread = Thread.main
        current: Thread = Thread.current
        self.assertEqual(main.ident, current.ident)
        self.assertEqual(current.ident, Thread.current.ident)
        self.assertEqual(main.name, 'MainThread')
        self.assertTrue(Thread.activeCount >= 1)
        foundMain: bool = False
        threads: list[Thread] = Thread.actives
        for i in range(len(threads)):
            if threads[i].ident == current.ident:
                foundMain = True
        self.assertTrue(foundMain)
        ready: Event = new()
        release: Event = new()
        box: Box = new()
        worker: Thread = new(lambda: registryWorker(ready, release, box))
        worker.start()
        self.assertTrue(ready.wait(timeout=1.0))
        self.assertEqual(box.value, 1)
        workerIdent: int64 = worker.ident
        foundWorker: bool = False
        workerThreads: list[Thread] = Thread.actives
        for i in range(len(workerThreads)):
            if workerThreads[i].ident == workerIdent:
                foundWorker = True
        self.assertTrue(foundWorker)
        release.set()
        worker.join()

class LockTests(TestCaseMixin):
    _testTag = 40

    @override
    def test(self):
        lock: Lock = new()
        box: Box = new()
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.locked())
        self.assertFalse(lock.acquire(blocking=False))
        t: Thread = new(lambda: holdLock(lock, box))
        t.start()
        sleep(0.02)
        self.assertEqual(box.value, 0)
        lock.release()
        t.join()
        self.assertEqual(box.value, 7)
        self.assertFalse(lock.locked())
        raised: bool = False
        try:
            lock.release()
        except RuntimeError:
            raised = True
        self.assertTrue(raised)
        raised = False
        try:
            lock.acquire(blocking=False, timeout=0.1)
        except ValueError:
            raised = True
        self.assertTrue(raised)

class AtomicTests(TestCaseMixin):
    _testTag = 50

    @override
    def test(self):
        counter: atomic[int] = new(0)
        self.assertEqual(counter.load(), 0)
        self.assertTrue(counter.compareExchange(0, 5))
        self.assertFalse(counter.compareExchange(0, 9))
        self.assertEqual(counter.exchange(1), 5)
        self.assertEqual(counter.fetchAdd(2), 1)
        self.assertEqual(counter.fetchSub(1), 3)
        self.assertEqual(counter.load(), 2)
        t1: Thread = new(lambda: addMany(counter, 50))
        t2: Thread = new(lambda: addMany(counter, 50))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(counter.load(), 102)

class QueueTests(TestCaseMixin):
    _testTag = 60

    @override
    def test(self):
        q: Queue[int] = new(1)
        self.assertFalse(q)
        q.putNoWait(10)
        self.assertEqual(len(q), 1)
        self.assertTrue(q)
        self.assertTrue(q.full())
        raised: bool = False
        try:
            q.putNoWait(20)
        except FullError:
            raised = True
        self.assertTrue(raised)
        self.assertEqual(q.getNoWait(), 10)
        q.taskDone()
        q.join()
        self.assertFalse(q)
        raised = False
        try:
            q.getNoWait()
        except EmptyError:
            raised = True
        self.assertTrue(raised)
        box: Box = new()
        t: Thread = new(lambda: queueConsume(q, box))
        t.start()
        sleep(0.02)
        q.put(33)
        q.join()
        t.join()
        self.assertEqual(box.value, 33)
        q.putNoWait(44)
        q.shutdown()
        self.assertEqual(q.getNoWait(), 44)
        q.taskDone()
        raised = False
        try:
            q.getNoWait()
        except ShutDownError:
            raised = True
        self.assertTrue(raised)
        raised = False
        try:
            q.putNoWait(55)
        except ShutDownError:
            raised = True
        self.assertTrue(raised)

class QueueBlockingTests(TestCaseMixin):
    _testTag = 70

    @override
    def test(self):
        q: Queue[int] = new()
        t: Thread = new(lambda: queueDelayedPut(q, 77))
        t.start()
        self.assertEqual(q.get(timeout=1.0), 77)
        q.taskDone()
        q.join()
        t.join()

class ThreadLocalTests(TestCaseMixin):
    _testTag = 80

    @override
    def test(self):
        tls: TLSBox = new()
        TLSBox.value = 5
        self.assertEqual(tls.bump(), 6)
        self.assertEqual(TLSBox.value, 6)
        box: Box = new()
        t: Thread = new(lambda: setTlsInWorker(box))
        t.start()
        t.join()
        self.assertEqual(box.value, 101)
        self.assertEqual(TLSBox.value, 6)

class RLockTests(TestCaseMixin):
    _testTag = 90

    @override
    def test(self):
        lock: RLock = new()
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.locked())
        box: Box = new()
        releaseThread: Thread = new(lambda: rlockReleaseFromOther(lock, box))
        releaseThread.start()
        releaseThread.join()
        self.assertEqual(box.value, 1)
        acquireThread: Thread = new(lambda: rlockAcquireAfterRelease(lock, box))
        acquireThread.start()
        sleep(0.02)
        self.assertEqual(box.value, 1)
        lock.release()
        sleep(0.02)
        self.assertEqual(box.value, 1)
        lock.release()
        acquireThread.join()
        self.assertEqual(box.value, 2)
        self.assertFalse(lock.locked())
        raised: bool = False
        try:
            lock.release()
        except RuntimeError:
            raised = True
        self.assertTrue(raised)

class ConditionTests(TestCaseMixin):
    _testTag = 100

    @override
    def test(self):
        cond: Condition = new()
        ready: Event = new()
        box: Box = new()
        waiter: Thread = new(lambda: conditionWaiter(cond, ready, box))
        waiter.start()
        self.assertTrue(ready.wait(timeout=1.0))
        cond.acquire()
        cond.notify()
        self.assertEqual(box.value, 0)
        cond.release()
        waiter.join()
        self.assertEqual(box.value, 11)
        ready2: Event = new()
        recursiveBox: Box = new()
        recursiveWaiter: Thread = new(lambda: conditionRecursiveWaiter(cond, ready2, recursiveBox))
        recursiveWaiter.start()
        self.assertTrue(ready2.wait(timeout=1.0))
        cond.acquire()
        cond.notifyAll()
        cond.release()
        recursiveWaiter.join()
        self.assertEqual(recursiveBox.value, 22)
        flag: Box = new()
        cond.acquire()
        setter: Thread = new(lambda: conditionSetFlag(cond, flag))
        setter.start()
        self.assertTrue(cond.waitFor(lambda: flag.value == 33, timeout=1.0))
        cond.release()
        setter.join()
        raised: bool = False
        try:
            cond.notify()
        except RuntimeError:
            raised = True
        self.assertTrue(raised)

class EventTests(TestCaseMixin):
    _testTag = 110

    @override
    def test(self):
        evt: Event = new()
        self.assertFalse(evt.isSet())
        self.assertFalse(evt.wait(timeout=0.01))
        evt.set()
        self.assertTrue(evt.isSet())
        self.assertTrue(evt.wait(timeout=0.0))
        evt.clear()
        self.assertFalse(evt.isSet())
        box: Box = new()
        waiter: Thread = new(lambda: eventWaiter(evt, box))
        waiter.start()
        sleep(0.02)
        self.assertEqual(box.value, 0)
        evt.set()
        waiter.join()
        self.assertEqual(box.value, 44)

class SemaphoreTests(TestCaseMixin):
    _testTag = 120

    @override
    def test(self):
        sem: Semaphore = new(1)
        self.assertTrue(sem.acquire())
        self.assertFalse(sem.acquire(blocking=False))
        box: Box = new()
        waiter: Thread = new(lambda: semaphoreWaiter(sem, box))
        waiter.start()
        sleep(0.02)
        self.assertEqual(box.value, 0)
        sem.release()
        waiter.join()
        self.assertEqual(box.value, 55)
        raised: bool = False
        try:
            sem.release(0)
        except ValueError:
            raised = True
        self.assertTrue(raised)
        raised = False
        try:
            bad: Semaphore = new(-1)
        except ValueError:
            raised = True
        self.assertTrue(raised)

class BoundedSemaphoreTests(TestCaseMixin):
    _testTag = 130

    @override
    def test(self):
        sem: BoundedSemaphore = new(1)
        raised: bool = False
        try:
            sem.release()
        except ValueError:
            raised = True
        self.assertTrue(raised)
        self.assertTrue(sem.acquire())
        sem.release()
        raised = False
        try:
            sem.release()
        except ValueError:
            raised = True
        self.assertTrue(raised)

class BarrierTests(TestCaseMixin):
    _testTag = 140

    @override
    def test(self):
        sleep(0.01)
        barrier: Barrier = new(2)
        self.assertEqual(barrier.parties, 2)
        ready: Event = new()
        done: Event = new()
        box: Box = new()
        waiter: Thread = new(lambda: barrierWaiter(barrier, ready, done, box))
        waiter.start()
        self.assertTrue(ready.wait(timeout=1.0))
        self.assertTrue(waitBarrierWaiting(barrier, 1))
        mainIndex: int = barrier.wait(timeout=1.0)
        self.assertTrue(done.wait(timeout=1.0))
        waiter.join()
        self.assertEqual(mainIndex + box.value, 1)
        self.assertFalse(barrier.broken)
        self.assertEqual(barrier.nWaiting, 0)
        rounds: int = 3
        counter: atomic[int] = new(0)
        loopWaiter: Thread = new(lambda: barrierRoundsWaiter(barrier, rounds, counter))
        loopWaiter.start()
        for _i in range(rounds):
            barrier.wait(timeout=1.0)
        loopWaiter.join()
        self.assertEqual(counter.load(), rounds)
        _barrierActionCount.store(0)
        actionBarrier: Barrier = new(2, barrierGlobalAction)
        actionReady: Event = new()
        actionDone: Event = new()
        actionWaiter: Thread = new(lambda: barrierWaiter(actionBarrier, actionReady, actionDone, Box()))
        actionWaiter.start()
        self.assertTrue(actionReady.wait(timeout=1.0))
        self.assertTrue(waitBarrierWaiting(actionBarrier, 1))
        actionBarrier.wait(timeout=1.0)
        self.assertTrue(actionDone.wait(timeout=1.0))
        actionWaiter.join()
        self.assertEqual(_barrierActionCount.load(), 1)
        timeoutBarrier: Barrier = new(2)
        raised: bool = False
        try:
            timeoutBarrier.wait(timeout=0.01)
        except BrokenBarrierError:
            raised = True
        self.assertTrue(raised)
        self.assertTrue(timeoutBarrier.broken)
        timeoutBarrier.reset()
        self.assertFalse(timeoutBarrier.broken)
        resetBarrier: Barrier = new(2)
        resetReady: Event = new()
        resetBox: Box = new()
        resetWaiter: Thread = new(lambda: barrierBrokenWaiter(resetBarrier, resetReady, resetBox))
        resetWaiter.start()
        self.assertTrue(resetReady.wait(timeout=1.0))
        self.assertTrue(waitBarrierWaiting(resetBarrier, 1))
        resetBarrier.reset()
        resetWaiter.join()
        self.assertEqual(resetBox.value, 1)
        self.assertFalse(resetBarrier.broken)
        abortBarrier: Barrier = new(2)
        abortReady: Event = new()
        abortBox: Box = new()
        abortWaiter: Thread = new(lambda: barrierBrokenWaiter(abortBarrier, abortReady, abortBox))
        abortWaiter.start()
        self.assertTrue(abortReady.wait(timeout=1.0))
        abortBarrier.abort()
        abortWaiter.join()
        self.assertEqual(abortBox.value, 1)
        self.assertTrue(abortBarrier.broken)
        raised = False
        try:
            abortBarrier.wait(timeout=0.01)
        except BrokenBarrierError:
            raised = True
        self.assertTrue(raised)

class ThreadPoolTests(TestCaseMixin):
    _testTag = 150

    @override
    def test(self):
        pool: ThreadPool[int] = new(2)
        future: Future[int] = pool.submit(poolReturn21)
        self.assertEqual(future.result(timeout=1.0), 21)
        self.assertTrue(future.done())
        self.assertFalse(future.cancelled())
        self.assertFalse(future.exception(timeout=0.0))
        pool.shutdown()
        raised: bool = False
        try:
            pool.submit(poolReturn1)
        except RuntimeError:
            raised = True
        self.assertTrue(raised)
        timeoutPool: ThreadPool[int] = new(1)
        _poolBlockStarted.clear()
        _poolBlockRelease.clear()
        _poolBlockValue.store(5)
        slow: Future[int] = timeoutPool.submit(poolBlockGlobal)
        self.assertTrue(_poolBlockStarted.wait(timeout=1.0))
        raised = False
        try:
            slow.result(timeout=0.01)
        except TimeoutError:
            raised = True
        self.assertTrue(raised)
        self.assertFalse(slow.cancel())
        _poolBlockRelease.set()
        self.assertEqual(slow.result(timeout=1.0), 5)
        timeoutPool.shutdown()
        cancelPool: ThreadPool[int] = new(1)
        _poolBlockStarted.clear()
        _poolBlockRelease.clear()
        _poolBlockValue.store(11)
        first: Future[int] = cancelPool.submit(poolBlockGlobal)
        self.assertTrue(_poolBlockStarted.wait(timeout=1.0))
        second: Future[int] = cancelPool.submit(poolReturn99)
        self.assertTrue(second.cancel())
        _poolBlockRelease.set()
        self.assertEqual(first.result(timeout=1.0), 11)
        raised = False
        try:
            second.result(timeout=0.0)
        except CancelledError:
            raised = True
        self.assertTrue(raised)
        cancelPool.shutdown()
        errorPool: ThreadPool[int] = new(1)
        failed: Future[int] = errorPool.submit(poolRaise)
        raised = False
        try:
            failed.result(timeout=1.0)
        except RuntimeError:
            raised = True
        self.assertTrue(raised)
        self.assertTrue(failed.exception(timeout=0.0))
        errorPool.shutdown()

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
