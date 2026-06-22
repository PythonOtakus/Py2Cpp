from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
"""``system.environ``：``Environ`` 映射、``expandvars`` / ``expanduser``。"""

from py2cpp.system.environ import Environ, environ


class EnvironMappingTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    key: str = "PY2CPP_ENV_TEST_KEY"
    try:
      del environ[key]
    except KeyError:
      pass
    self.assertFalse(key in environ)
    environ[key] = "alpha"
    self.assertEqual(environ[key], "alpha")
    self.assertEqual(environ.get(key), "alpha")
    self.assertEqual(environ.get(key + "_missing", "z"), "z")
    self.assertTrue(key in environ)
    del environ[key]
    self.assertFalse(key in environ)


class EnvironExpandvarsTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    key: str = "PY2CPP_ENV_EXPAND"
    try:
      del environ[key]
    except KeyError:
      pass
    environ[key] = "world"
    e: Environ = environ
    self.assertEqual(environ[key], "world")
    self.assertEqual(e.expandvars("hello $PY2CPP_ENV_EXPAND"), "hello world")
    self.assertEqual(e.expandvars("hello ${PY2CPP_ENV_EXPAND}"), "hello world")
    self.assertEqual(e.expandvars("hello %PY2CPP_ENV_EXPAND%"), "hello world")
    self.assertEqual(e.expandvars("unknown $NOT_A_REAL_PY2CPP_VAR"), "unknown $NOT_A_REAL_PY2CPP_VAR")
    self.assertEqual(e.expandvars("a$$b"), "a$b")
    del environ[key]


class EnvironExpanduserTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    e: Environ = environ
    if "USERPROFILE" in e:
      home: str = e["USERPROFILE"]
      self.assertEqual(e.expanduser("~"), home)
      self.assertEqual(e.expanduser("~\\docs"), home + "\\docs")
    else:
      self.assertEqual(e.expanduser("/abs/path"), "/abs/path")


def main() -> int:
  suite: TestSuite = new()
  suite.addTest(EnvironMappingTests())
  suite.addTest(EnvironExpandvarsTests())
  suite.addTest(EnvironExpanduserTests())
  runner: TextTestRunner = new()
  return runner.run(suite)
