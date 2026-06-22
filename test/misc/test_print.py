"""内建 ``print`` 冒烟（参考手册运算符/内建节）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner



class PrintSmokeTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    # ``print`` 多参数与字面量（编译期 lowering，运行期不校验 stdout）
    print("ok", 1, True)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
