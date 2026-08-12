"""``py2cpp.serde.yaml`` 基础语法、容器和文件流测试。"""
from py2cpp import *
from py2cpp.io import StringIO
from py2cpp.serde.yaml import Yaml
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class YamlScalarTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Yaml.loads[int]("42"), 42)
    self.assertEqual(Yaml.loads[bool]("true"), True)
    self.assertEqual(Yaml.loads[bool]("FALSE"), False)
    self.assertEqual(Yaml.loads[str]("'hello'"), "hello")
    self.assertEqual(Yaml.loads[str]('"hello\\nworld"'), "hello\nworld")


class YamlContainerTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    values: list[int] = Yaml.loads[list[int]]("- 1\n- 2\n- 3\n")
    self.assertEqual(len(values), 3)
    self.assertEqual(values[1], 2)


class YamlStreamTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    values: list[int] = [1, 2, 3]
    encoded: str = Yaml.dumps(values)
    self.assertEqual(encoded, "[1,2,3]")
    decoded: list[int] = Yaml.loads[list[int]](encoded)
    self.assertEqual(decoded[0], 1)
    stream: StringIO = new()
    Yaml.dump_string(values, stream)
    stream.seek(0)
    back: list[int] = Yaml.load_string[list[int]](stream)
    self.assertEqual(back[2], 3)


def main():
  suite: TestSuite = new()
  suite.addTest(YamlScalarTests())
  suite.addTest(YamlContainerTests())
  suite.addTest(YamlStreamTests())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
