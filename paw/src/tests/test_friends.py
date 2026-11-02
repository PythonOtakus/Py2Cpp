"""``class B(friends=(A,))``：友元类与 protected 访问检查。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.access import (
  class_grants_friend_access,
  collect_external_protected_accesses,
  validate_module_friend_names,
)
from src.passes.access import expand_member_access
from src.analysis.ir import ClassInfo, parse_class_friends
from src.passes.mixins import expand_mixins
from src.translator import Translator


class ParseFriendsTests(unittest.TestCase):
  def test_parse_tuple(self):
    node = ast.parse("class Vault(friends=(Reader, Op)): pass").body[0]
    self.assertEqual(parse_class_friends(node), ["Reader", "Op"])

  def test_parse_single(self):
    node = ast.parse("class Vault(friends=Reader): pass").body[0]
    self.assertEqual(parse_class_friends(node), ["Reader"])


class FriendAccessTests(unittest.TestCase):
  def _build(self, src: str) -> Translator:
    mod = ast.parse(src)
    tr = Translator("test/friends", "test/friends.py")
    for node in mod.body:
      if isinstance(node, ast.ClassDef):
        tr.classes[node.name] = ClassInfo(node, "test/friends")
    expand_mixins(tr)
    return tr

  def test_friend_may_read_protected(self):
    src = """
class Vault(friends=(Reader,)):
  def __init__(self):
    self._code: int = 99

class Reader:
  def read(self, v: Vault) -> int:
    return v._code
"""
    tr = self._build(src)
    ext = collect_external_protected_accesses(
      tr.classes, tr.module_functions, tr.module_asts, tr.import_bindings,
    )
    self.assertEqual(ext, set())
    self.assertTrue(class_grants_friend_access("Reader", "Vault", tr.classes))

  def test_non_friend_rejected(self):
    src = """
class Vault:
  def __init__(self):
    self._code: int = 0

class Stranger:
  def peek(self, v: Vault) -> int:
    return v._code
"""
    tr = self._build(src)
    ext = collect_external_protected_accesses(
      tr.classes, tr.module_functions, tr.module_asts, tr.import_bindings,
    )
    self.assertIn(("Stranger", "Vault", "_code"), ext)

  def test_parse_forward_friend_class_name(self):
    node = ast.parse("class Host(friends=(Later,)): pass").body[0]
    self.assertEqual(parse_class_friends(node), ["Later"])

  def test_forward_friend_same_module(self):
    """友元类名可在宿主之后定义；译器全模块解析后绑定。"""
    src = """
class Host(friends=(Later,)):
  def __init__(self):
    self._code: int = 0

class Later:
  def peek(self, h: Host) -> int:
    return h._code
"""
    tr = self._build(src)
    validate_module_friend_names(tr.classes)
    expand_member_access(tr)
    self.assertTrue(class_grants_friend_access("Later", "Host", tr.classes))

  def test_string_friend_rejected(self):
    node = ast.parse('class Host(friends=("Later",)): pass').body[0]
    with self.assertRaises(SyntaxError) as ctx:
      parse_class_friends(node)
    self.assertIn("勿用字符串", str(ctx.exception))

  def test_friend_decl_extra_type_params(self):
    src = """
class Query[T, U]:
  pass

class Table[T](friends=(Query,)):
  pass
"""
    tr = self._build(src)
    host = tr.classes["Table"]
    lines = tr._friend_class_decl_lines(host)
    self.assertEqual(
      lines,
      [
        "template<typename _U>",
        "friend class Query<_T, _U>;",
      ],
    )


if __name__ == "__main__":
  unittest.main()
