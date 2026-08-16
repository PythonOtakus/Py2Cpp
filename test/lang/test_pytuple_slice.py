"""``PyTuple`` 定长切片 ``(T,…)[i:j]`` 集成测。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner



class PyTupleSliceTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    t: (int, int, int)
    t = 1, 2, 3
    mid: (int,)
    mid = t[1:-1]
    v: int
    v = mid[0]
    self.assertEqual(v, 2)

    t2: (int, int, int)
    t2 = 10, 20, 30
    tail: (int, int)
    tail = t2[1:]
    a: int
    b: int
    a = tail[0]
    b = tail[1]
    self.assertEqual(a, 20)
    self.assertEqual(b, 30)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  main()
