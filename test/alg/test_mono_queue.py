"""``alg.mono_queue``：滑动窗口 min / max。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.mono_queue import MonoQueue


class MonoQueueMinWindowTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    q: MonoQueue[int] = new()
    q.push(1)
    q.push(3)
    q.push(2)
    self.assertTrue(q.min() == 1)
    q.pop()
    self.assertTrue(q.min() == 2)
    q.pop()
    self.assertTrue(q.min() == 2)


class MonoQueueMaxWindowTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    q: MonoQueue[int] = new(False)
    q.push(1)
    q.push(3)
    q.push(2)
    self.assertTrue(q.max() == 3)
    q.pop()
    self.assertTrue(q.max() == 3)
    q.pop()
    self.assertTrue(q.max() == 2)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(MonoQueueMinWindowTests())
  suite.addTest(MonoQueueMaxWindowTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
