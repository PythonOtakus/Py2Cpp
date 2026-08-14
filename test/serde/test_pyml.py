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
    source: str = """
    $asset_root: "assets/ui"
    $scale: 2
    $count: 3
    $count: += 4
    $count: *= 2
    $name: "button"
    $name: += "_primary"
    window:
      width: = 160 * $scale
      height: = 300 / $scale
      count: = $count
      title: = f"{$asset_root}/{$name}.png"
      = f"build_{$scale}": = $count % 5
    """.striplines()
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
        count: 14
        title: "assets/ui/button_primary.png"
        build_2: 4
      """.striplines() + "\n",
    )

    decoded: dict[str, dict[str, int]] = Pyml.loads[dict[str, dict[str, int]]](
      """
        $scale: 2
        window:
          width: = 160 * $scale
      """.striplines(),
    )
    self.assertEqual(decoded["window"]["width"], 320)

    indented_template: str = """
    $value: 4
    item: = $value * 2
    """.striplines()
    self.assertEqual(Pyml.expand(indented_template), "item: 8\n")

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
      """.striplines(),
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
      """.striplines() + "\n",
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
      """.striplines(),
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
      """.striplines() + "\n",
    )


class PymlControlFlowTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    source: str = """
    $enabled: true
    items:
      @if $enabled:
        - selected
      @for $i in range(1, 4):
        - = $i * 2
    """.striplines()
    expanded: str = Pyml.expand(source)
    self.assertEqual(
      expanded,
      """
      items:
        - selected
        - 2
        - 4
        - 6
      """.striplines() + "\n",
    )
    values: dict[str, list[int]] = Pyml.loads[dict[str, list[int]]](
      """
        $enabled: true
        items:
          @if $enabled:
            - 1
          @for $i in range(2, 4):
            - = $i
      """.striplines(),
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
      """.striplines(),
    )
    self.assertEqual(scoped, "result: true\n")


class PymlCallablesTests(TestCaseMixin):
  _test_tag = 15

  @override
  def test(self):
    source: str = """
      @def $sum_to($n):
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
    """.striplines()
    expanded: str = Pyml.expand(source)
    self.assertEqual(
      expanded,
      """
        total: 10
        ui:
          start:
            text: "开始"
            color: "#3b82f6"
            padding: [12, 8]
        plugins:
          - core
          - input
          - diagnostics
      """.striplines() + "\n",
    )

    missing_return: bool = False
    try:
      Pyml.expand(
        """
          @def $bad():
            $x: 1
          value: = $bad()
        """.striplines(),
      )
    except PymlError:
      missing_return = True
    self.assertTrue(missing_return)

    expanded_mapping: str = Pyml.expand(
      """
        $defaults:
          color: blue
          padding: [12, 8]
        panel:
          @expand $defaults
          title: "settings"
      """.striplines(),
    )
    self.assertEqual(
      expanded_mapping,
      """
        panel:
          color: blue
          padding: [12, 8]
          title: "settings"
      """.striplines() + "\n",
    )
    overwritten: str = Pyml.expand(
      """
        $defaults:
          title: "imported"
        panel:
          title: "local"
          @expand $defaults
      """.striplines(),
    )
    self.assertEqual(
      overwritten,
      """
        panel:
          title: "imported"
      """.striplines() + "\n",
    )


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
      Pyml.expand(
        """
          $items: [1]
          = $items:
            value: 1
        """.striplines(),
      )
    except PymlError:
      invalid_key = True
    self.assertTrue(invalid_key)


class PymlPathAccessTests(TestCaseMixin):
  _test_tag = 22

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
      """.striplines(),
    )
    self.assertEqual(
      expanded,
      """
        selected: 5
        last: 5
        special: 21
        created: 5
      """.striplines() + "\n",
    )

    isolated: str = Pyml.expand(
      """
        $state: {items: [1]}
        @if true:
          $state.items[0]: 2
        @for $i in [3]:
          $state.items[0]: = $i
        result: = $state.items[0]
      """.striplines(),
    )
    self.assertEqual(isolated, "result: 1\n")

    invalid_index_type: bool = False
    try:
      Pyml.expand("$items: [1]\nvalue: = $items[\"zero\"]\n")
    except PymlError:
      invalid_index_type = True
    self.assertTrue(invalid_index_type)

    out_of_range: bool = False
    try:
      Pyml.expand("$items: [1]\nvalue: = $items[1]\n")
    except PymlError:
      out_of_range = True
    self.assertTrue(out_of_range)

    missing_intermediate: bool = False
    try:
      Pyml.expand("$state: {}\n$state.missing.value: 1\n")
    except PymlError:
      missing_intermediate = True
    self.assertTrue(missing_intermediate)

    invalid_container: bool = False
    try:
      Pyml.expand("$state: 1\nvalue: = $state.value\n")
    except PymlError:
      invalid_container = True
    self.assertTrue(invalid_container)


class PymlModulesTests(TestCaseMixin):
  _test_tag = 25

  @override
  def test(self):
    context: PymlContext = new(
      module_name="game.main",
      module_root="test/serde/pyml_modules",
    )
    expanded: str = Pyml.expand(
      """
        @from .ui.button import $button, $twice as $double
        @from game.config import $title
        ui:
          start:
            @expand $button($title)
        value: = $double(3)
      """.striplines(),
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
      """.striplines() + "\n",
    )

    imported_all: str = Pyml.expand(
      """
        @from game.config import *
        title: = $title
      """.striplines(),
      context,
    )
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
      Pyml.expand(
        """
          $title: "local"
          @from game.config import $title
        """.striplines(),
        context,
      )
    except PymlError:
      collision = True
    self.assertTrue(collision)


def main():
  suite: TestSuite = new()
  suite.addTest(PymlVariablesAndExpressionsTests())
  suite.addTest(PymlControlFlowTests())
  suite.addTest(PymlCallablesTests())
  suite.addTest(PymlErrorTests())
  suite.addTest(PymlPathAccessTests())
  suite.addTest(PymlModulesTests())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
