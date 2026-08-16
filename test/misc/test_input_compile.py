"""内置 ``input`` 编译回归（不在普通 run 中阻塞 stdin）。"""
from py2cpp import *
from py2cpp.core.exceptions import EOFError
from py2cpp.system.environ import environ
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def readUserLine() -> str:
  return input("name: ")


def readTypedValues() -> int:
  a: int = input[int]("i: ")
  b: float = input[float]("f: ")
  if b > 3.4 and b < 3.6:
    return a
  return -1


class InputCompileTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    # 默认只验证翻译/编译能解析 ``input(prompt)``；设置环境变量时才实际消费 stdin，
    # 避免普通 run-all 在交互式控制台阻塞。
    mode: str = environ.get("PY2CPP_INPUT_TEST", "")
    match mode:
      case "yes":
        got: str = readUserLine()
        self.assertEqual(got, "hello")
      case "typed":
        self.assertEqual(readTypedValues(), 42)
      case "eof":
        try:
          _: str = input()
          self.assertTrue(False)
        except EOFError:
          self.assertTrue(True)
      case _:
        self.assertTrue(True)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
