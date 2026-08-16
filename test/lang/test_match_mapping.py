"""``match`` 映射模式（dict / frozendict）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def readPort(cfg: dict[str, int]) -> int:
  match cfg:
    case {"port": p}:
      return p
    case {"host": _, "port": p}:
      return p
    case _:
      return 8080


def nestedCfg(cfg: dict[str, dict[str, int]]) -> int:
  match cfg:
    case {"inner": {"x": v}}:
      return v
    case _:
      return -1


def restKeys(cfg: dict[str, int]) -> int:
  match cfg:
    case {"a": 1, **rest}:
      return len(rest)
    case _:
      return -1


class MatchMappingTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(readPort({"port": 9000}), 9000)
    self.assertEqual(readPort({"host": 0, "port": 77, "extra": 1}), 77)
    self.assertEqual(readPort({}), 8080)
    inner: dict[str, int] = {"x": 42}
    self.assertEqual(nestedCfg({"inner": inner}), 42)
    self.assertEqual(restKeys({"a": 1, "b": 2, "c": 3}), 2)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
