"""``py2cpp.serde.pyml`` 的已实现语法回归测试。

完整目标覆盖由 ``docs/serde-pyml.md`` §10 定义。模块样例见
``test/serde/pyml_modules/game/``（``showcase.pyml`` 覆盖现有语法全集）。
"""
from py2cpp import *
from py2cpp.serde.pyml import Pyml, PymlContext, PymlError
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class PymlVariablesAndExpressionsTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    source: str = """
    $asset_root: "assets/ui"
    $scale: 2
    $enabled: true
    $count: 3
    $count: += 4
    $count: *= 2
    $count: -= 4
    $count: /= 5
    $count: %= 4
    $name: "button"
    $name: += "_primary"
    window:
      width: = 160 * $scale
      height: = 300 / $scale
      count: = $count
      title: = f"{$asset_root}/{$name}.png"
      visible: = $enabled
      mode: = "hi" if $enabled else "lo"
      = f"build_{$scale}": = $count % 5
    """.stripLines()
    expanded: str = ""
    failed: bool = False
    try:
      expanded = Pyml.expand(source)
    except PymlError:
      failed = True
    self.assertFalse(failed)
    self.assertEqual(
      expanded,
      """
      window:
        width: 320
        height: 150
        count: 2
        title: "assets/ui/button_primary.png"
        visible: true
        mode: "hi"
        build_2: 2
      """.stripLines() + "\n",
    )

    decoded: dict[str, dict[str, int]] = Pyml.loads[dict[str, dict[str, int]]](
      """
        $scale: 2
        window:
          width: = 160 * $scale
      """.stripLines(),
    )
    self.assertEqual(decoded["window"]["width"], 320)

    indentedTemplate: str = """
    $value: 4
    item: = $value * 2
    """.stripLines()
    self.assertEqual(Pyml.expand(indentedTemplate), "item: 8\n")

    collections: str = Pyml.expand(
      """
      $presets:
        low: 512
        high: 2048
      $plugins: [core]
      $plugins: += [input]
      builds:
        @for $name, $size in $presets.items():
          = $name: = $size
      plugins:
        @expand $plugins
      """.stripLines(),
    )
    self.assertEqual(
      collections,
      """
      builds:
        low: 512
        high: 2048
      plugins:
        - core
        - input
      """.stripLines() + "\n",
    )

    paths: str = Pyml.expand(
      """
      $state: {ui: {buttons: [{label: "start", colors: {primary: blue}, tags: [base]}]}}
      $state.ui.buttons[0].colors.primary: "green"
      $state["ui"]["buttons"][0]["label"]: += "_go"
      $state.ui.buttons[0].tags[0]: "primary"
      $state.ui.buttons[0].id: 7
      $state.ui.buttons[0].id: += 1
      $indexes: [0]
      $field: "ui"
      $label_key: "label"
      $state[$field]["buttons"][$indexes[0]][$label_key]: += "_nested"
      index: = $indexes[0]
      field: = $state[$field].buttons[$indexes[0]].label
      label: = $state.ui.buttons[0].label
      color: = $state.ui.buttons[0].colors.primary
      tag: = $state.ui.buttons[0].tags[0]
      id: = $state.ui.buttons[0].id
      """.stripLines(),
    )
    self.assertEqual(
      paths,
      """
      index: 0
      field: "start_go_nested"
      label: "start_go_nested"
      color: "green"
      tag: "primary"
      id: 8
      """.stripLines() + "\n",
    )


class PymlControlFlowTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    source: str = """
    $enabled: true
    items:
      @if $enabled:
        - selected
      @for $i in range(1, 4):
        - = $i * 2
    """.stripLines()
    expanded: str = Pyml.expand(source)
    self.assertEqual(
      expanded,
      """
      items:
        - selected
        - 2
        - 4
        - 6
      """.stripLines() + "\n",
    )
    values: dict[str, list[int]] = Pyml.loads[dict[str, list[int]]](
      """
        $enabled: true
        items:
          @if $enabled:
            - 1
          @for $i in range(2, 4):
            - = $i
      """.stripLines(),
    )
    self.assertEqual(len(values["items"]), 3)
    self.assertEqual(values["items"][0], 1)
    self.assertEqual(values["items"][2], 3)

    scoped: str = Pyml.expand(
      """
      $enabled: true
      @if $enabled:
        $enabled: false
      @for $item in [1, 2]:
        $enabled: = $item == 1
      result: = $enabled
      """.stripLines(),
    )
    self.assertEqual(scoped, "result: true\n")

    branches: str = Pyml.expand(
      """
      $pick_one: false
      $pick_two: true
      pick:
        @if $pick_one:
          - one
        @elif $pick_two:
          - two
        @else:
          - other
      skip:
        @if false:
          - never
        @elif false:
          - also_never
        @else:
          - fallback
      """.stripLines(),
    )
    self.assertEqual(
      branches,
      """
      pick:
        - two
      skip:
        - fallback
      """.stripLines() + "\n",
    )


class PymlCallablesTests(TestCaseMixin):
  _testTag = 15

  @override
  def test(self):
    source: str = """
      @def $sum_to($n):
        $s: 0
        @for $i in range($n + 1):
          $s: += $i
        @return $s
      @def $grade($high):
        @if $high:
          @return "S"
        @else:
          @return "B"
      @inline $button($text, $color: \"#3b82f6\"):
        text: = $text
        color: = $color
        padding: [12, 8]
      @inline $base_plugins():
        - core
        - input
      @inline $enabled_plugins($want_debug):
        $base: [core, input]
        @for $plugin in $base:
          - = $plugin
        @if $want_debug:
          - diagnostics
        @else:
          - release_metrics
      total: = $sum_to(4)
      rank: = $grade(true)
      ui:
        start:
          @expand $button(\"开始\", $color: \"red\")
      plugins:
        @expand $base_plugins()
        @expand $enabled_plugins(true)
        - editor
    """.stripLines()
    expanded: str = Pyml.expand(source)
    self.assertEqual(
      expanded,
      """
        total: 10
        rank: "S"
        ui:
          start:
            text: "开始"
            color: "red"
            padding: [12, 8]
        plugins:
          - core
          - input
          - "core"
          - "input"
          - diagnostics
          - editor
      """.stripLines() + "\n",
    )

    missingReturn: bool = False
    try:
      Pyml.expand(
        """
          @def $bad():
            $x: 1
          value: = $bad()
        """.stripLines(),
      )
    except PymlError:
      missingReturn = True
    self.assertTrue(missingReturn)

    expandedMapping: str = Pyml.expand(
      """
        $defaults:
          color: blue
          padding: [12, 8]
        panel:
          @expand $defaults
          title: "settings"
      """.stripLines(),
    )
    self.assertEqual(
      expandedMapping,
      """
        panel:
          color: blue
          padding: [12, 8]
          title: "settings"
      """.stripLines() + "\n",
    )
    overwritten: str = Pyml.expand(
      """
        $defaults:
          title: "imported"
        panel:
          title: "local"
          @expand $defaults
      """.stripLines(),
    )
    self.assertEqual(
      overwritten,
      """
        panel:
          title: "imported"
      """.stripLines() + "\n",
    )


class PymlErrorTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    undefined: bool = False
    try:
      Pyml.expand("value: = $missing\n")
    except PymlError:
      undefined = True
    self.assertTrue(undefined)

    invalidFor: bool = False
    try:
      Pyml.expand("@for $item in 1:\n  - = $item\n")
    except PymlError:
      invalidFor = True
    self.assertTrue(invalidFor)

    invalidKey: bool = False
    try:
      Pyml.expand(
        """
          $items: [1]
          = $items:
            value: 1
        """.stripLines(),
      )
    except PymlError:
      invalidKey = True
    self.assertTrue(invalidKey)

    orphanElse: bool = False
    try:
      Pyml.expand("@else:\n  - x\n")
    except PymlError:
      orphanElse = True
    self.assertTrue(orphanElse)


class PymlPathAccessTests(TestCaseMixin):
  _testTag = 22

  @override
  def test(self):
    expanded: str = Pyml.expand(
      """
        @def $pick($items, $index):
          @return $items[$index]
        $items: [3, 5, 7, 11]
        $map: {"a.b": {"a]b": 20}}
        $index: 1
        $items[$index + 1]: *= 2
        $items[len($items) - 1]: -= 1
        $items[-1]: /= 2
        $items[0 if true else 1]: %= 2
        $selected: = $pick($items, $index)
        $map["new"]: = $selected
        $map["a.b"]["a]b"]: += 1
        selected: = $selected
        last: = $items[-1]
        special: = $map["a.b"]["a]b"]
        created: = $map["new"]
      """.stripLines(),
    )
    self.assertEqual(
      expanded,
      """
        selected: 5
        last: 5
        special: 21
        created: 5
      """.stripLines() + "\n",
    )

    isolated: str = Pyml.expand(
      """
        $state: {items: [1]}
        @if true:
          $state.items[0]: 2
        @for $i in [3]:
          $state.items[0]: = $i
        result: = $state.items[0]
      """.stripLines(),
    )
    self.assertEqual(isolated, "result: 1\n")

    invalidIndexType: bool = False
    try:
      Pyml.expand("$items: [1]\nvalue: = $items[\"zero\"]\n")
    except PymlError:
      invalidIndexType = True
    self.assertTrue(invalidIndexType)

    outOfRange: bool = False
    try:
      Pyml.expand("$items: [1]\nvalue: = $items[1]\n")
    except PymlError:
      outOfRange = True
    self.assertTrue(outOfRange)

    missingIntermediate: bool = False
    try:
      Pyml.expand("$state: {}\n$state.missing.value: 1\n")
    except PymlError:
      missingIntermediate = True
    self.assertTrue(missingIntermediate)

    invalidContainer: bool = False
    try:
      Pyml.expand("$state: 1\nvalue: = $state.value\n")
    except PymlError:
      invalidContainer = True
    self.assertTrue(invalidContainer)


class PymlModulesTests(TestCaseMixin):
  _testTag = 25

  @override
  def test(self):
    context: PymlContext = new(
      moduleName="game.main",
      moduleRoot="test/serde/pyml_modules",
    )
    expanded: str = Pyml.expand(
      """
        @from .ui.button import $button, $twice as $double
        @from game.config import $title
        ui:
          start:
            @expand $button($title)
        value: = $double(3)
      """.stripLines(),
      context,
    )
    self.assertEqual(
      expanded,
      """
        ui:
          start:
            text: "PyML"
            color: "blue"
        value: 6
      """.stripLines() + "\n",
    )

    importedAll: str = Pyml.expand(
      """
        @from game.config import *
        title: = $title
        debug: = $debug
      """.stripLines(),
      context,
    )
    self.assertEqual(
      importedAll,
      """
      title: "PyML"
      debug: true
      """.stripLines() + "\n",
    )

    parentRelative: str = Pyml.expand(
      """
        @from .ui.widgets import $chip
        badge:
          @expand $chip("OK")
      """.stripLines(),
      context,
    )
    self.assertEqual(
      parentRelative,
      """
      badge:
        text: "OK"
        color: "#3b82f6"
      """.stripLines() + "\n",
    )

    cyclic: bool = False
    cycleContext: PymlContext = new(
      moduleName="game.cycle_a",
      moduleRoot="test/serde/pyml_modules",
    )
    try:
      Pyml.expand("@from .cycle_b import *\n", cycleContext)
    except PymlError:
      cyclic = True
    self.assertTrue(cyclic)

    collision: bool = False
    try:
      Pyml.expand(
        """
          $title: "local"
          @from game.config import $title
        """.stripLines(),
        context,
      )
    except PymlError:
      collision = True
    self.assertTrue(collision)


class PymlShowcaseTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    # 模块组合冒烟；完整语法样例见 game/showcase.pyml（插件/手工验收）。
    context: PymlContext = new(
      moduleName="game.main",
      moduleRoot="test/serde/pyml_modules",
    )
    expanded: str = Pyml.expand(
      """
        @from .ui.button import $button, $grade
        @from .defaults import $base_plugins
        @from game.config import $title, $debug
        ui:
          start:
            @expand $button($title)
        plugins:
          @expand $base_plugins()
        rank: = $grade(true)
        mode: = "dev" if $debug else "prod"
      """.stripLines(),
      context,
    )
    self.assertEqual(
      expanded,
      """
      ui:
        start:
          text: "PyML"
          color: "blue"
      plugins:
        - core
        - input
      rank: "S"
      mode: "dev"
      """.stripLines() + "\n",
    )


def main():
  suite: TestSuite = new()
  suite.addTest(PymlVariablesAndExpressionsTests())
  suite.addTest(PymlControlFlowTests())
  suite.addTest(PymlCallablesTests())
  suite.addTest(PymlErrorTests())
  suite.addTest(PymlPathAccessTests())
  suite.addTest(PymlModulesTests())
  suite.addTest(PymlShowcaseTests())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
