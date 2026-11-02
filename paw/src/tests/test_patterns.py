"""``analysis.patterns``：译器命名约定。"""
from __future__ import annotations

import re
import unittest

from src.analysis.patterns import (
  auto_template_type_param_name,
  py2cpp_emit_symbol,
  temp_name,
)


def _temp_serial(name: str) -> int:
  m = re.search(r"\d+$", name)
  assert m is not None
  return int(m.group())


class TempNameTests(unittest.TestCase):
  def test_py2cpp_prefix_and_monotonic(self):
    a = temp_name("tmp")
    b = temp_name("seq")
    c = temp_name("_x")
    pat = re.compile(r"^__py2cpp_[a-z]+\d+$")
    self.assertRegex(a, pat)
    self.assertRegex(b, pat)
    self.assertRegex(c, pat)
    self.assertTrue(a.startswith("__py2cpp_tmp"))
    self.assertTrue(b.startswith("__py2cpp_seq"))
    self.assertTrue(c.startswith("__py2cpp_x"))
    self.assertLess(_temp_serial(a), _temp_serial(b))
    self.assertLess(_temp_serial(b), _temp_serial(c))


class EmitSymbolTests(unittest.TestCase):
  def test_auto_template_type_param(self):
    reserved = {"Ts", "__Ts"}
    self.assertEqual(
      auto_template_type_param_name("T0", reserved=set()),
      "__T0",
    )
    self.assertEqual(
      auto_template_type_param_name("Ts", reserved={"Ts"}),
      "__Ts",
    )
    self.assertEqual(
      auto_template_type_param_name("Ts", reserved={"Ts", "__Ts"}),
      "__Ts1",
    )

  def test_py2cpp_emit_symbol(self):
    self.assertEqual(py2cpp_emit_symbol("vt_loop"), "__py2cpp_vt_loop")
    self.assertEqual(
      py2cpp_emit_symbol("type_if", "pick", "2", "pick"),
      "__py2cpp_type_if_pick_2_pick",
    )


if __name__ == "__main__":
  unittest.main()
