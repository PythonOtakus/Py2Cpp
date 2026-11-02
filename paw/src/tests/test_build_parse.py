"""``parse_build_literal`` 译器单测。"""
from __future__ import annotations

import unittest

from src.passes.build_parse import (
  AssignSegment,
  BuildParseError,
  ExprValue,
  IndexRefValue,
  ListDescentSegment,
  ListRootPlan,
  LiteralValue,
  StructRootPlan,
  parse_build_literal,
)


class BuildParseTests(unittest.TestCase):
  def test_struct_root_assign(self):
    plan = parse_build_literal('name="alpha", min_score=5', list_root=False)
    self.assertIsInstance(plan, StructRootPlan)
    self.assertEqual(len(plan.body.segments), 2)
    seg0 = plan.body.segments[0]
    self.assertIsInstance(seg0, AssignSegment)
    self.assertEqual(seg0.field, "name")
    self.assertIsInstance(seg0.value, LiteralValue)
    self.assertEqual(seg0.value.value, "alpha")

  def test_list_descent_single_template(self):
    plan = parse_build_literal(
      'teams[:1] > name="alpha", members[:2] > score=10,name="amy"',
      list_root=False,
    )
    self.assertIsInstance(plan, StructRootPlan)
    teams = plan.body.segments[0]
    self.assertIsInstance(teams, ListDescentSegment)
    self.assertEqual(teams.count, 1)
    self.assertIsNone(teams.index_bind)
    self.assertEqual(len(teams.body.segments), 2)
    members = teams.body.segments[1]
    self.assertIsInstance(members, ListDescentSegment)
    self.assertEqual(members.count, 2)

  def test_list_root(self):
    plan = parse_build_literal('[:2] > name="alpha"', list_root=True)
    self.assertIsInstance(plan, ListRootPlan)
    self.assertEqual(plan.count, 2)

  def test_index_bind(self):
    plan = parse_build_literal(
      "teams[:3]: $i > name={prefix + str($i)}, min_score=$i",
      list_root=False,
    )
    teams = plan.body.segments[0]
    self.assertIsInstance(teams, ListDescentSegment)
    self.assertEqual(teams.index_bind, "i")
    name_seg = teams.body.segments[0]
    self.assertIsInstance(name_seg.value, ExprValue)
    self.assertIn("i", name_seg.value.index_refs)
    score_seg = teams.body.segments[1]
    self.assertIsInstance(score_seg.value, IndexRefValue)
    self.assertEqual(score_seg.value.name, "i")

  def test_empty_list_descent(self):
    plan = parse_build_literal("members[:0] >", list_root=False)
    seg = plan.body.segments[0]
    self.assertIsInstance(seg, ListDescentSegment)
    self.assertEqual(seg.count, 0)
    self.assertEqual(seg.body.segments, ())

  def test_list_root_requires_prefix(self):
    with self.assertRaises(BuildParseError):
      parse_build_literal("name=alpha", list_root=True)

  def test_struct_rejects_list_root_syntax(self):
    with self.assertRaises(BuildParseError):
      parse_build_literal("[:1] > name=alpha", list_root=False)

  def test_rejects_single_index(self):
    with self.assertRaises(BuildParseError):
      parse_build_literal("teams[0] > name=alpha", list_root=False)


if __name__ == "__main__":
  unittest.main()
