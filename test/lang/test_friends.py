"""友元类 ``class B(friends=(A,))``：``A`` 可访问 ``B`` 的 protected 成员。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class VaultReader:
  def read(self, v: Vault) -> int:
    return v._code

  def bump(self, v: Vault) -> None:
    v._code += 1


class Vault(friends=(VaultReader,)):
  def __init__(self):
    self._code: int = 99

  @immutable
  def tag(self) -> int:
    return self._code


class FriendClassTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    v: Vault = new()
    r: VaultReader = new()
    self.assertEqual(r.read(v), 99)
    r.bump(v)
    self.assertEqual(v.tag(), 100)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
