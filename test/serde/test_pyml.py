"""``py2cpp.serde.pyml`` 的已实现语法回归测试。

完整目标覆盖由 ``docs/serde-pyml.md`` §10 定义。随着解释器阶段推进，本文件
依次补充 ``@elif``/``@else``、dict 迭代、``@def``、``@inline``、``@expand``
和 ``@from`` 的可执行回归；在对应语法尚未落地前不把未实现行为伪装成绿测。
"""
from py2cpp import *
from py2cpp.serde.pyml import Pyml, PymlContext, PymlError
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

    collections: str = Pyml.expand("""$presets:
  low: 512
  high: 2048
$plugins: [core]
$plugins: += [input]
builds:
  @for $name, $size in $presets.items():
    = $name: = $size
plugins:
  @expand $plugins
""")
    self.assertEqual(
      collections,
      "builds:\n  low: 512\n  high: 2048\nplugins:\n  - core\n  - input\n",
    )


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

    scoped: str = Pyml.expand("""$enabled: true
@if $enabled:
  $enabled: false
@for $item in [1, 2]:
  $enabled: = $item == 1
result: = $enabled
""")
    self.assertEqual(scoped, "result: true\n")


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

    expanded_mapping: str = Pyml.expand("""$defaults:
  color: blue
  padding: [12, 8]
panel:
  @expand $defaults
  title: \"settings\"
""")
    self.assertEqual(
      expanded_mapping,
      "panel:\n  color: blue\n  padding: [12, 8]\n  title: \"settings\"\n",
    )
    overwritten: str = Pyml.expand("""$defaults:
  title: \"imported\"
panel:
  title: \"local\"
  @expand $defaults
""")
    self.assertEqual(overwritten, "panel:\n  title: \"imported\"\n")


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

    invalid_key: bool = False
    try:
      Pyml.expand("$items: [1]\n= $items:\n  value: 1\n")
    except PymlError:
      invalid_key = True
    self.assertTrue(invalid_key)


class PymlModulesTests(TestCaseMixin):
  _test_tag = 25

  @override
  def test(self):
    context: PymlContext = new(
      module_name="game.main",
      module_root="test/serde/pyml_modules",
    )
    expanded: str = Pyml.expand("""@from .ui.button import $button, $twice as $double
@from game.config import $title
ui:
  start:
    @expand $button($title)
value: = $double(3)
""", context)
    self.assertEqual(
      expanded,
      "ui:\n  start:\n    text: \"PyML\"\n    color: \"blue\"\nvalue: 6\n",
    )

    imported_all: str = Pyml.expand("""@from game.config import *
title: = $title
""", context)
    self.assertEqual(imported_all, "title: \"PyML\"\n")

    cyclic: bool = False
    cycle_context: PymlContext = new(
      module_name="game.cycle_a",
      module_root="test/serde/pyml_modules",
    )
    try:
      Pyml.expand("@from .cycle_b import *\n", cycle_context)
    except PymlError:
      cyclic = True
    self.assertTrue(cyclic)

    collision: bool = False
    try:
      Pyml.expand("""$title: \"local\"
@from game.config import $title
""", context)
    except PymlError:
      collision = True
    self.assertTrue(collision)


def main():
  suite: TestSuite = new()
  suite.addTest(PymlVariablesAndExpressionsTests())
  suite.addTest(PymlControlFlowTests())
  suite.addTest(PymlCallablesTests())
  suite.addTest(PymlErrorTests())
  suite.addTest(PymlModulesTests())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
