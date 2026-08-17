"""轻量单元测试框架（API 参考 ``unittest``，适配 py2cpp 无反射 / 无动态派发）。

用法概要
--------
1. 子类 ``TestCase``（``@refcount``），用 ``@override`` 实现虚函数 ``test()``。
2. 继承 ``TestCaseMixin``（``@mixin``，已继承 ``TestCase``）；混入声明 ``_testTag``，子类只需写 ``_testTag = <编号>``。
   混入内联 ``run``（``beginTest`` → ``test()`` → ``endTest``），名称用 ``Self.__name__``。
3. 亦可手写 ``@override`` 的 ``run``（会覆盖混入的 ``run``）。
4. ``main()`` 中 ``return TextTestRunner().run(suite)``（0=成功）。

``TextTestRunner(verbosity=1)``：逐用例一行进度（含耗时）+ 汇总；``verbosity=2`` 另打印 ``tag``；``0`` 静默。
"""
from ..builtins import *
from ..util.list import list
from ..text import str
from ..system.time import formatDuration, perfCounter

_BannerWidth: int = 70


@refcount
class TestResult:
  """聚合一次运行的统计（类似 ``unittest.TestResult``）。

  须 ``@refcount``：经 ``run`` / ``beginTest`` / ``endTest`` 传递时共享同一实例；
  若按值传递，``beginTest`` 的计数与用例名会丢失（进度恒为 ``[0/N]``、名为 ``.``、耗时异常）。
  """

  def __init__(self):
    self.testsRun: int = 0
    self.testsFailed: int = 0
    self.assertionsFailed: int = 0
    self.failedTags: list[int] = []
    self.failedNames: list[str] = []
    self.failedDeltas: list[int] = []
    self._currentTag: int = 0
    self._caseFailuresBefore: int = 0
    self.verbosity: int = 0
    self.caseTotal: int = 0
    self._currentName: str = "."
    self._caseStart: float64 = 0.0
    self.caseElapsed: list[float64] = []
    self.totalSeconds: float64 = 0.0

  @immutable
  def formatElapsed(self, seconds: float64) -> str:
    return formatDuration(seconds)

  @immutable
  def wasSuccessful(self) -> bool:
    return self.testsFailed == 0 and self.assertionsFailed == 0

  def hline(self, ch: str) -> str:
    """分隔线（``ch * _BannerWidth``），供 runner 与失败详情复用。"""
    return ch * _BannerWidth

  def beginTest(self, tag: int, caseFailures: int, name: str) -> None:
    self.testsRun += 1
    self._currentTag = tag
    self._currentName = name
    self._caseFailuresBefore = caseFailures
    self._caseStart = perfCounter()

  def endTest(self, caseFailures: int) -> None:
    elapsed: float64 = perfCounter() - self._caseStart
    self.caseElapsed.append(elapsed)
    elapsedS: str = self.formatElapsed(elapsed)
    delta: int = caseFailures - self._caseFailuresBefore
    if delta > 0:
      self.testsFailed += 1
      self.failedTags.append(self._currentTag)
      self.failedNames.append(self._currentName)
      self.failedDeltas.append(delta)
      self.assertionsFailed += delta
    if self.verbosity >= 1:
      prefix: str = self._progressPrefix()
      if delta > 0:
        print(
          f"{prefix}  FAIL  {self._currentName}  "
          f"(tag={self._currentTag}, assertions={delta}, {elapsedS})",
          flush=True,
        )
      elif self.verbosity >= 2:
        print(
          f"{prefix}  PASS  {self._currentName}  "
          f"(tag={self._currentTag}, {elapsedS})",
          flush=True,
        )
      else:
        print(f"{prefix}  PASS  {self._currentName}  ({elapsedS})", flush=True)

  def printFailedDetails(self) -> None:
    nFail: int = len(self.failedTags)
    if nFail == 0:
      return
    print(self.hline("="))
    print("  failures")
    print(self.hline("="))
    for i in range(nFail):
      idx: int = i + 1
      print(
        f"  #{idx}  tag={self.failedTags[i]}  {self.failedNames[i]}  "
        f"(assertions={self.failedDeltas[i]})"
      )

  def _progressPrefix(self) -> str:
    if self.caseTotal > 0:
      return f"[{self.testsRun:3d}/{self.caseTotal:3d}]"
    return f"[{self.testsRun:3d}]"


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

  def beginTest(self, result: TestResult, tag: int, name: str) -> None:
    self.setUp()
    result.beginTest(tag, self.failures, name)

  def endTest(self, result: TestResult) -> None:
    result.endTest(self.failures)
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

  _testTag: int @const = 0

  @override
  def run(self, result: TestResult) -> None:
    self.beginTest(result, self._testTag, Self.__name__)
    self.test()
    self.endTest(result)


class TestSuite:
  """用例容器：持有 ``list[TestCase]``（C++ 为 ``PyList<RefCount<TestCase>>``）并虚调用 ``run``。"""

  def __init__(self):
    self._cases: list[TestCase] = []

  def addTest(self, case: TestCase) -> None:
    self._cases.append(case)

  def run(self, result: TestResult) -> None:
    for testCase in self._cases:
      testCase.run(result)

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
    result.caseTotal = total
    if self.verbosity > 0:
      print(result.hline("="))
      print("  py2cpp unittest")
      print(f"  cases: {total}")
      print(result.hline("="))
      print("")
    suiteStart: float64 = perfCounter()
    suite.run(result)
    result.totalSeconds = perfCounter() - suiteStart
    if self.verbosity > 0:
      passed: int = result.testsRun - result.testsFailed
      print("")
      print(result.hline("-"))
      print("  summary")
      print(result.hline("-"))
      print(f"  ran:               {result.testsRun}")
      print(f"  passed:            {passed}")
      print(f"  failed cases:      {result.testsFailed}")
      print(f"  failed assertions: {result.assertionsFailed}")
      print(f"  time:              {result.formatElapsed(result.totalSeconds)}")
      if not result.wasSuccessful():
        print("")
        result.printFailedDetails()
      print("")
      print(result.hline("="))
      if result.wasSuccessful():
        print(f"  Ok ({result.testsRun} tests)")
      else:
        print(
          f"  FAILED ({result.testsFailed} case(s), "
          f"{result.assertionsFailed} assertion(s))"
        )
      print(result.hline("="))
    if not result.wasSuccessful():
      return result.testsFailed
    return 0
