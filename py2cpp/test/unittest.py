"""轻量单元测试框架（API 参考 ``unittest``，适配 py2cpp 无反射 / 无动态派发）。

用法概要
--------
1. 子类 ``TestCase``（``@refcount``），用 ``@override`` 实现虚函数 ``test()``。
2. 继承 ``TestCaseMixin``（``@mixin``，已继承 ``TestCase``）；混入声明 ``_test_tag``，子类只需写 ``_test_tag = <编号>``。
   混入内联 ``run``（``begin_test`` → ``test()`` → ``end_test``），名称用 ``Self.__name__``。
3. 亦可手写 ``@override`` 的 ``run``（会覆盖混入的 ``run``）。
4. ``main()`` 中 ``return TextTestRunner().run(suite)``（0=成功）。

``TextTestRunner(verbosity=1)``：逐用例一行进度（含耗时）+ 汇总；``verbosity=2`` 另打印 ``tag``；``0`` 静默。
"""
from ..builtins import *
from ..util.list import list
from ..text import str
from ..system.time import format_duration, perf_counter

_BANNER_WIDTH: int = 70


class TestResult:
  """聚合一次运行的统计（类似 ``unittest.TestResult``）。"""

  def __init__(self):
    self.tests_run: int = 0
    self.tests_failed: int = 0
    self.assertions_failed: int = 0
    self.failed_tags: list[int] = []
    self.failed_names: list[str] = []
    self.failed_deltas: list[int] = []
    self._current_tag: int = 0
    self._case_failures_before: int = 0
    self.verbosity: int = 0
    self.case_total: int = 0
    self._current_name: str = "."
    self._case_start: float64 = 0.0
    self.case_elapsed: list[float64] = []
    self.total_seconds: float64 = 0.0

  @immutable
  def format_elapsed(self, seconds: float64) -> str:
    return format_duration(seconds)

  @immutable
  def wasSuccessful(self) -> bool:
    return self.tests_failed == 0 and self.assertions_failed == 0

  def hline(self, ch: str) -> str:
    """分隔线（``ch * _BANNER_WIDTH``），供 runner 与失败详情复用。"""
    return ch * _BANNER_WIDTH

  def begin_test(self, tag: int, case_failures: int, name: str) -> None:
    self.tests_run += 1
    self._current_tag = tag
    self._current_name = name
    self._case_failures_before = case_failures
    self._case_start = perf_counter()

  def end_test(self, case_failures: int) -> None:
    elapsed: float64 = perf_counter() - self._case_start
    self.case_elapsed.append(elapsed)
    elapsed_s: str = self.format_elapsed(elapsed)
    delta: int = case_failures - self._case_failures_before
    if delta > 0:
      self.tests_failed += 1
      self.failed_tags.append(self._current_tag)
      self.failed_names.append(self._current_name)
      self.failed_deltas.append(delta)
      self.assertions_failed += delta
    if self.verbosity >= 1:
      prefix: str = self._progress_prefix()
      if delta > 0:
        print(
          f"{prefix}  FAIL  {self._current_name}  "
          f"(tag={self._current_tag}, assertions={delta}, {elapsed_s})",
          flush=True,
        )
      elif self.verbosity >= 2:
        print(
          f"{prefix}  PASS  {self._current_name}  "
          f"(tag={self._current_tag}, {elapsed_s})",
          flush=True,
        )
      else:
        print(f"{prefix}  PASS  {self._current_name}  ({elapsed_s})", flush=True)

  def print_failed_details(self) -> None:
    n_fail: int = len(self.failed_tags)
    if n_fail == 0:
      return
    print(self.hline("="))
    print("  failures")
    print(self.hline("="))
    for i in range(n_fail):
      idx: int = i + 1
      print(
        f"  #{idx}  tag={self.failed_tags[i]}  {self.failed_names[i]}  "
        f"(assertions={self.failed_deltas[i]})"
      )

  def _progress_prefix(self) -> str:
    if self.case_total > 0:
      return f"[{self.tests_run:3d}/{self.case_total:3d}]"
    return f"[{self.tests_run:3d}]"


@refcount
class TestCase:
  """测试基类：软断言（累加 ``failures``，不抛异常）。"""

  def __init__(self):
    self.failures = 0

  def setUp(self) -> None:
    pass

  def tearDown(self) -> None:
    pass

  @virtual
  def run(self, result: TestResult) -> None:
    """子类或混入覆盖：默认不执行用例。"""
    pass

  @virtual
  def test(self) -> None:
    """子类覆盖：具体断言写在此方法中。"""
    pass

  def begin_test(self, result: TestResult, tag: int, name: str) -> None:
    self.setUp()
    result.begin_test(tag, self.failures, name)

  def end_test(self, result: TestResult) -> None:
    result.end_test(self.failures)
    self.tearDown()

  def assertEqual(self, first, second) -> None:
    if first != second:
      self.failures += 1

  def assertNotEqual(self, first, second) -> None:
    if first == second:
      self.failures += 1

  def assertTrue(self, expr: bool) -> None:
    if not expr:
      self.failures += 1

  def assertFalse(self, expr: bool) -> None:
    if expr:
      self.failures += 1

  def assertIs(self, first: int, second: int) -> None:
    if first != second:
      self.failures += 1

  def assertIsNone(self, value: int) -> None:
    if value != 0:
      self.failures += 1

  def assertIsNotNone(self, value: int) -> None:
    if value == 0:
      self.failures += 1

  def assertIn(self, needle: str, haystack: str) -> None:
    if needle not in haystack:
      self.failures += 1

  def assertNotIn(self, needle: str, haystack: str) -> None:
    if needle in haystack:
      self.failures += 1

  def assertGreater(self, first: int, second: int) -> None:
    if first <= second:
      self.failures += 1

  def assertGreaterEqual(self, first: int, second: int) -> None:
    if first < second:
      self.failures += 1

  def assertLess(self, first: int, second: int) -> None:
    if first >= second:
      self.failures += 1

  def assertLessEqual(self, first: int, second: int) -> None:
    if first > second:
      self.failures += 1


@mixin
class TestCaseMixin(TestCase):
  """混入类：内联 ``run``；宿主仅写 ``class Foo(TestCaseMixin)`` 即继承 ``TestCase``。"""

  _test_tag: int @const = 0

  @override
  def run(self, result: TestResult) -> None:
    self.begin_test(result, self._test_tag, Self.__name__)
    self.test()
    self.end_test(result)


class TestSuite:
  """用例容器：持有 ``list[TestCase]``（C++ 为 ``PyList<RefCount<TestCase>>``）并虚调用 ``run``。"""

  def __init__(self):
    self._cases: list[TestCase] = []

  def addTest(self, case: TestCase) -> None:
    self._cases.append(case)

  def run(self, result: TestResult) -> None:
    for test_case in self._cases:
      test_case.run(result)

  @immutable
  def countTestCases(self) -> int:
    return len(self._cases)


class TextTestRunner:
  """运行套件并输出报告（``verbosity``: 0=静默，1=逐用例+汇总，2=另含 tag）。"""

  def __init__(self, verbosity: int = 1):
    self.verbosity: int = verbosity

  def run(self, suite: TestSuite) -> int:
    result: TestResult = new()
    result.verbosity = self.verbosity
    total: int = suite.countTestCases()
    result.case_total = total
    if self.verbosity > 0:
      print(result.hline("="))
      print("  py2cpp unittest")
      print(f"  cases: {total}")
      print(result.hline("="))
      print("")
    suite_start: float64 = perf_counter()
    suite.run(result)
    result.total_seconds = perf_counter() - suite_start
    if self.verbosity > 0:
      passed: int = result.tests_run - result.tests_failed
      print("")
      print(result.hline("-"))
      print("  summary")
      print(result.hline("-"))
      print(f"  ran:               {result.tests_run}")
      print(f"  passed:            {passed}")
      print(f"  failed cases:      {result.tests_failed}")
      print(f"  failed assertions: {result.assertions_failed}")
      print(f"  time:              {result.format_elapsed(result.total_seconds)}")
      if not result.wasSuccessful():
        print("")
        result.print_failed_details()
      print("")
      print(result.hline("="))
      if result.wasSuccessful():
        print(f"  OK ({result.tests_run} tests)")
      else:
        print(
          f"  FAILED ({result.tests_failed} case(s), "
          f"{result.assertions_failed} assertion(s))"
        )
      print(result.hline("="))
    if not result.wasSuccessful():
      return result.tests_failed
    return 0
