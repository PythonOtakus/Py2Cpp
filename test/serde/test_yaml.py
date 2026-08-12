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


class YamlContainerTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    values: list[int] = Yaml.loads[list[int]]("- 1\n- 2\n- 3\n")
    self.assertEqual(len(values), 3)
    self.assertEqual(values[1], 2)
    aliases: list[int] = Yaml.loads[list[int]]("- &base 7\n- *base\n")
    self.assertEqual(aliases[1], 7)
    merged: dict[str, dict[str, int]] = Yaml.loads[dict[str, dict[str, int]]]("base: &defaults {a: 1, b: 2}\nproduction:\n  <<: *defaults\n  c: 3\n")
    self.assertEqual(merged["production"]["a"], 1)
    self.assertEqual(merged["production"]["c"], 3)
    nested: list[list[int]] = Yaml.loads[list[list[int]]]("[[1, 2], [3, 4]]")
    self.assertEqual(nested[1][0], 3)




class YamlDocumentTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    docs: list[int] = Yaml.loads_all[int]("---\n1\n---\n2\n...\n")
    self.assertEqual(len(docs), 2)
    self.assertEqual(docs[0], 1)
    self.assertEqual(docs[1], 2)
    streamed: list[int] = Yaml.load_all_string[int](StringIO("---\n3\n---\n4\n"))
    self.assertEqual(streamed[0], 3)
    self.assertEqual(streamed[1], 4)


class YamlBlockScalarTests(TestCaseMixin):
  _test_tag = 25

  @override
  def test(self):
    stripped: dict[str, str] = Yaml.loads[dict[str, str]]("text: |-\n  one\n  two\n")
    self.assertEqual(stripped["text"], "one\ntwo")
    folded: dict[str, str] = Yaml.loads[dict[str, str]]("text: >-\n  one\n  two\n")
    self.assertEqual(folded["text"], "one two")
    kept: dict[str, str] = Yaml.loads[dict[str, str]]("text: |+\n  one\n  two\n")
    self.assertEqual(kept["text"], "one\ntwo\n\n")

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
  suite.addTest(YamlDocumentTests())
  suite.addTest(YamlBlockScalarTests())
  suite.addTest(YamlStreamTests())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
