"""``match`` 映射模式（dict / frozendict）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def read_port(cfg: dict[str, int]) -> int:
  match cfg:
    case {"port": p}:
      return p
    case {"host": _, "port": p}:
      return p
    case _:
      return 8080


def nested_cfg(cfg: dict[str, dict[str, int]]) -> int:
  match cfg:
    case {"inner": {"x": v}}:
      return v
    case _:
      return -1


def rest_keys(cfg: dict[str, int]) -> int:
  match cfg:
    case {"a": 1, **rest}:
      return len(rest)
    case _:
      return -1


class MatchMappingTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(read_port({"port": 9000}), 9000)
    self.assertEqual(read_port({"host": 0, "port": 77, "extra": 1}), 77)
    self.assertEqual(read_port({}), 8080)
    inner: dict[str, int] = {"x": 42}
    self.assertEqual(nested_cfg({"inner": inner}), 42)
    self.assertEqual(rest_keys({"a": 1, "b": 2, "c": 3}), 2)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
