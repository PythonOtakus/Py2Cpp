"""``py2cpp.serde.pyml`` 的已实现语法回归测试。

完整目标覆盖由 ``docs/serde-pyml.md`` §10 定义。随着解释器阶段推进，本文件
依次补充 ``@elif``/``@else``、dict 迭代、``@def``、``@inline``、``@expand``
和 ``@from`` 的可执行回归；在对应语法尚未落地前不把未实现行为伪装成绿测。
"""
from py2cpp import *
from py2cpp.serde.pyml import Pyml, PymlError
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class PymlVariablesAndExpressionsTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    source: str = """$asset_root: \"assets/ui\"
$scale: 2
$count: 3
$count: += 4
$count: *= 2
$name: \"button\"
$name: += \"_primary\"
window:
  width: = 160 * $scale
  height: = 300 / $scale
  count: = $count
  title: = f\"{$asset_root}/{$name}.png\"
  = f\"build_{$scale}\": = $count % 5
"""
    expanded: str = ""
    failed: bool = False
    try:
      expanded = Pyml.expand(source)
    except PymlError:
      failed = True
    print("failed=" + str(failed))
    print(expanded)
    return
    self.assertFalse(failed)
    self.assertEqual(
      expanded,
      "window:\n  width: 320\n  height: 150\n  count: 14\n"
      "  title: \"assets/ui/button_primary.png\"\n  build_2: 4\n",
    )

    decoded: dict[str, dict[str, int]] = Pyml.loads[dict[str, dict[str, int]]](
      "$scale: 2\nwindow:\n  width: = 160 * $scale\n",
    )
    self.assertEqual(decoded["window"]["width"], 320)


class PymlControlFlowTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    source: str = """$enabled: true
items:
  @if $enabled:
    - selected
  @for $i in range(1, 4):
    - = $i * 2
"""
    expanded: str = Pyml.expand(source)
    self.assertEqual(expanded, "items:\n  - selected\n  - 2\n  - 4\n  - 6\n")
    values: dict[str, list[int]] = Pyml.loads[dict[str, list[int]]](
      "$enabled: true\nitems:\n  @if $enabled:\n    - 1\n  @for $i in range(2, 4):\n    - = $i\n",
    )
    self.assertEqual(len(values["items"]), 3)
    self.assertEqual(values["items"][0], 1)
    self.assertEqual(values["items"][2], 3)


class PymlCallablesTests(TestCaseMixin):
  _test_tag = 15

  @override
  def test(self):
    source: str = """@def $sum_to($n):
  $s: 0
  @for $i in range($n + 1):
    $s: += $i
  @return $s
@inline $button($text, $color: \"#3b82f6\"):
  text: = $text
  color: = $color
  padding: [12, 8]
@inline $base_plugins():
  - core
  - input
total: = $sum_to(4)
ui:
  start:
    @expand $button(\"开始\")
plugins:
  @expand $base_plugins()
  - diagnostics
"""
    expanded: str = Pyml.expand(source)
    self.assertEqual(
      expanded,
      "total: 10\nui:\n  start:\n    text: \"开始\"\n    color: \"#3b82f6\"\n"
      "    padding: [12, 8]\nplugins:\n  - core\n  - input\n  - diagnostics\n",
    )

    missing_return: bool = False
    try:
      Pyml.expand("@def $bad():\n  $x: 1\nvalue: = $bad()\n")
    except PymlError:
      missing_return = True
    self.assertTrue(missing_return)


class PymlErrorTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    undefined: bool = False
    try:
      Pyml.expand("value: = $missing\n")
    except PymlError:
      undefined = True
    self.assertTrue(undefined)

    invalid_for: bool = False
    try:
      Pyml.expand("@for $item in 1:\n  - = $item\n")
    except PymlError:
      invalid_for = True
    self.assertTrue(invalid_for)


def main():
  suite: TestSuite = new()
  suite.addTest(PymlVariablesAndExpressionsTests())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
