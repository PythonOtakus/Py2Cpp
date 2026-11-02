"""``propagate_mixin_instance_fields``：混入实例字段并入宿主。"""
from __future__ import annotations

import unittest

from src.passes.dataclass_expand import expand_dataclass
from src.passes.mixins import expand_mixins
from src.translator import Translator


class MixinInstanceFieldsPass(unittest.TestCase):
  def test_mixin_instance_field_merged_into_host(self):
    code = '''
from py2cpp import mixin

@mixin
class CounterMixin:
  hits: int = 0

  def bump(self) -> None:
    self.hits = self.hits + 1

class Host(CounterMixin):
  pass
'''
    tr = Translator("mod", "mod.py")
    tr._parse_modules([("mod", code)])
    expand_mixins(tr)
    host = tr.classes["Host"]
    self.assertIn("hits", host.fields)
    self.assertIn("bump", host.methods)

  def test_mixin_dataclass_init_merged_into_host(self):
    code = '''
from py2cpp import mixin, dataclass

@dataclass
@mixin
class CounterMixin:
  hits: int = 0

class Host(CounterMixin):
  pass
'''
    tr = Translator("mod", "mod.py")
    tr._parse_modules([("mod", code)])
    expand_dataclass(tr)
    expand_mixins(tr)
    host = tr.classes["Host"]
    self.assertTrue(host.is_dataclass)
    self.assertIn("hits", host.fields)
    self.assertEqual(len(host.inits), 1)
    self.assertIn("hits", host.inits[0].args.args[1].arg)


if __name__ == "__main__":
  unittest.main()
