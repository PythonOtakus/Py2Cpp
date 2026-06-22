"""``parse_selector_path`` 译器单测。"""
from __future__ import annotations

import ast
import unittest

from src.passes.selector_parse import (
  BindStep,
  CountStep,
  DescendantStep,
  FieldStep,
  FilterStep,
  GroupStep,
  IndexStep,
  MultiBracketStep,
  ProjectionStep,
  RefStep,
  SelectorChainPlan,
  SelectorParseError,
  SelectorPlan,
  SliceStep,
  SortStep,
  SortKey,
  StrIndexStep,
  parse_selector_chain,
  parse_selector_literal,
  parse_selector_path,
)


class SelectorParseTests(unittest.TestCase):
  def test_field_chain(self):
    plan = parse_selector_path(".teams[0].name")
    self.assertEqual(
      plan.steps,
      (FieldStep("teams"), IndexStep(0), FieldStep("name")),
    )

  def test_list_root_index(self):
    plan = parse_selector_path("[-1]")
    self.assertEqual(plan.steps, (IndexStep(-1),))

  def test_slice_and_filter(self):
    plan = parse_selector_path(".members[1:3]{.score > 0}")
    self.assertEqual(len(plan.steps), 3)
    self.assertIsInstance(plan.steps[0], FieldStep)
    self.assertIsInstance(plan.steps[1], SliceStep)
    self.assertEqual(plan.steps[1].lo, 1)
    self.assertEqual(plan.steps[1].hi, 3)
    filt = plan.steps[2]
    self.assertIsInstance(filt, FilterStep)
    self.assertIsInstance(filt.expr, ast.Compare)

  def test_filter_compound(self):
    plan = parse_selector_path('.items{.score > 0 and .active}')
    filt = plan.steps[1]
    self.assertIsInstance(filt, FilterStep)
    self.assertIsInstance(filt.expr, ast.BoolOp)

  def test_bare_identifier_not_element_field(self):
    plan = parse_selector_path(".items{score > 0}")
    filt = plan.steps[1]
    self.assertIsInstance(filt, FilterStep)
    self.assertIsInstance(filt.expr, ast.Compare)
    self.assertIsInstance(filt.expr.left, ast.Name)
    self.assertEqual(filt.expr.left.id, "score")

  def test_dot_prefix_element_field(self):
    plan = parse_selector_path(".items{.score > 0}")
    filt = plan.steps[1]
    self.assertIsInstance(filt, FilterStep)
    self.assertIsInstance(filt.expr, ast.Compare)
    self.assertIsInstance(filt.expr.left, ast.Attribute)
    self.assertEqual(filt.expr.left.attr, "score")

  def test_projection_parse(self):
    plan = parse_selector_path(".f.(a.b, c).d")
    self.assertEqual(plan.steps[0], FieldStep("f"))
    proj = plan.steps[1]
    self.assertIsInstance(proj, ProjectionStep)
    self.assertEqual(proj.arms[0].steps, (FieldStep("a"), FieldStep("b")))
    self.assertEqual(proj.arms[1].steps, (FieldStep("c"),))
    self.assertEqual(plan.steps[2], FieldStep("d"))

  def test_projection_simple_arms(self):
    plan = parse_selector_path(".items[-1].(name, id)")
    self.assertIsInstance(plan.steps[1], IndexStep)
    proj = plan.steps[2]
    self.assertIsInstance(proj, ProjectionStep)
    self.assertEqual(proj.arms[0].steps, (FieldStep("name"),))
    self.assertEqual(proj.arms[1].steps, (FieldStep("id"),))

  def test_multi_bracket(self):
    plan = parse_selector_path(".members[1, 2:4]")
    self.assertEqual(plan.steps[0], FieldStep("members"))
    mb = plan.steps[1]
    self.assertIsInstance(mb, MultiBracketStep)
    self.assertEqual(mb.items[0], IndexStep(1))
    self.assertEqual(mb.items[1], SliceStep(2, 4))

  def test_nested_projection(self):
    plan = parse_selector_path(".f.(a.(x, y), b).d")
    proj = plan.steps[1]
    self.assertIsInstance(proj, ProjectionStep)
    inner = proj.arms[0].steps[1]
    self.assertIsInstance(inner, ProjectionStep)
    self.assertEqual(
      inner.arms,
      (SelectorPlan((FieldStep("x"),)), SelectorPlan((FieldStep("y"),))),
    )

  def test_filter_before_projection(self):
    plan = parse_selector_path(".members{.score > 0}.(name, score)")
    self.assertIsInstance(plan.steps[0], FieldStep)
    self.assertIsInstance(plan.steps[1], FilterStep)
    self.assertIsInstance(plan.steps[2], ProjectionStep)

  def test_empty_path_rejected(self):
    with self.assertRaises(SelectorParseError):
      parse_selector_path("")

  def test_open_hi_slice(self):
    plan = parse_selector_path(".items[:2]")
    sl = plan.steps[1]
    self.assertIsInstance(sl, SliceStep)
    self.assertIsNone(sl.lo)
    self.assertEqual(sl.hi, 2)
    self.assertIsNone(sl.step)

  def test_open_lo_slice(self):
    plan = parse_selector_path(".items[2:]")
    sl = plan.steps[1]
    self.assertIsInstance(sl, SliceStep)
    self.assertEqual(sl.lo, 2)
    self.assertIsNone(sl.hi)
    self.assertIsNone(sl.step)

  def test_wildcard_slice(self):
    plan = parse_selector_path(".teams[:].name")
    self.assertEqual(plan.steps[0], FieldStep("teams"))
    sl = plan.steps[1]
    self.assertIsInstance(sl, SliceStep)
    self.assertIsNone(sl.lo)
    self.assertIsNone(sl.hi)
    self.assertIsNone(sl.step)

  def test_slice_step(self):
    plan = parse_selector_path(".items[::2]")
    sl = plan.steps[1]
    self.assertIsInstance(sl, SliceStep)
    self.assertIsNone(sl.lo)
    self.assertIsNone(sl.hi)
    self.assertEqual(sl.step, 2)

  def test_slice_lo_hi_step(self):
    plan = parse_selector_path(".items[1:5:2]")
    sl = plan.steps[1]
    self.assertEqual((sl.lo, sl.hi, sl.step), (1, 5, 2))

  def test_descendant(self):
    plan = parse_selector_path(".teams..name")
    self.assertEqual(plan.steps[0], FieldStep("teams"))
    self.assertEqual(plan.steps[1], DescendantStep("name"))

  def test_top_level_comma_rejected(self):
    with self.assertRaises(SelectorParseError) as ctx:
      parse_selector_literal(".teams[0].name, .teams[1].name")
    self.assertIn("顶层 ',' 多路径已废除", str(ctx.exception))

  def test_multi_index_field_path(self):
    plan = parse_selector_path(".teams[0, 1].name")
    self.assertEqual(plan.steps[0], FieldStep("teams"))
    mb = plan.steps[1]
    self.assertIsInstance(mb, MultiBracketStep)
    self.assertEqual(mb.items, (IndexStep(0), IndexStep(1)))
    self.assertEqual(plan.steps[2], FieldStep("name"))

  def test_root_projection_multi_index_suffix(self):
    plan = parse_selector_path(".(teams[0], teams[1]).name")
    proj = plan.steps[0]
    self.assertIsInstance(proj, ProjectionStep)
    self.assertEqual(len(proj.arms), 2)
    self.assertEqual(
      proj.arms[0].steps,
      (FieldStep("teams"), IndexStep(0)),
    )
    self.assertEqual(plan.steps[1], FieldStep("name"))

  def test_str_index(self):
    plan = parse_selector_path(".data['x']")
    self.assertEqual(plan.steps[0], FieldStep("data"))
    self.assertEqual(plan.steps[1], StrIndexStep("x"))

  def test_multi_str_index(self):
    plan = parse_selector_path(".data['u', 'v']")
    mb = plan.steps[1]
    self.assertIsInstance(mb, MultiBracketStep)
    self.assertEqual(mb.items, (StrIndexStep("u"), StrIndexStep("v")))

  def test_str_index_escape(self):
    plan = parse_selector_path('.data["a\\"b"]')
    self.assertEqual(plan.steps[1], StrIndexStep('a"b'))

  def test_mixed_bracket_rejected(self):
    with self.assertRaises(SelectorParseError):
      parse_selector_path(".items[0, 'x']")

  def test_optional_index(self):
    plan = parse_selector_path(".teams?[0].name")
    self.assertEqual(plan.steps[0], FieldStep("teams"))
    self.assertEqual(plan.steps[1], IndexStep(0, optional=True))

  def test_optional_field(self):
    plan = parse_selector_path(".meta?.title")
    self.assertEqual(plan.steps[0], FieldStep("meta"))
    self.assertEqual(plan.steps[1], FieldStep("title", optional=True))

  def test_root_dot_field(self):
    plan = parse_selector_path(".teams")
    self.assertEqual(plan.steps, (FieldStep("teams"),))

  def test_root_optional_field(self):
    plan = parse_selector_path("?.title")
    self.assertEqual(plan.steps, (FieldStep("title", optional=True),))

  def test_bare_root_field_rejected(self):
    with self.assertRaises(SelectorParseError):
      parse_selector_path("teams")

  def test_optional_str_index(self):
    plan = parse_selector_path(".data?['x']")
    self.assertEqual(plan.steps[1], StrIndexStep("x", optional=True))

  def test_bind_ref_semicolon(self):
    plan = parse_selector_literal(".teams[0]:$t; $t.name")
    self.assertIsInstance(plan, SelectorChainPlan)
    self.assertEqual(
      plan.bind_prefix,
      (FieldStep("teams"), IndexStep(0), BindStep("t")),
    )
    self.assertEqual(plan.steps, (RefStep("t"), FieldStep("name")))

  def test_bind_ref_inline(self):
    plan = parse_selector_literal(".teams[0]:$t.members[1].name")
    self.assertIsInstance(plan, SelectorChainPlan)
    self.assertEqual(plan.bind_prefix, ())
    self.assertEqual(
      plan.steps,
      (
        FieldStep("teams"),
        IndexStep(0),
        BindStep("t"),
        FieldStep("members"),
        IndexStep(1),
        FieldStep("name"),
      ),
    )

  def test_filter_bind_ref_desugar(self):
    plan = parse_selector_literal(".teams[0]:$t.members{.score > $t.min_score}.name")
    self.assertIsInstance(plan, SelectorChainPlan)
    filt = plan.steps[4]
    self.assertIsInstance(filt, FilterStep)
    self.assertIn("t", filt.bind_refs)
    self.assertIsInstance(filt.expr, ast.Compare)
    self.assertIsInstance(filt.expr.comparators[0], ast.Attribute)
    self.assertEqual(filt.expr.comparators[0].value.id, "_bind_t")

  def test_top_level_comma_with_dollar_rejected(self):
    with self.assertRaises(SelectorParseError) as ctx:
      parse_selector_literal(".teams[0]:$t; $t.name, .teams[1].name")
    self.assertIn("顶层 ',' 多路径已废除", str(ctx.exception))

  def test_semicolon_right_comma_rejected(self):
    with self.assertRaises(SelectorParseError):
      parse_selector_chain(".teams[0]:$t; $t.name, name")

  def test_projection_dollar_rejected(self):
    with self.assertRaises(SelectorParseError):
      parse_selector_path(".f.($t.name, c)")

  def test_filter_bind_requires_ancestor(self):
    with self.assertRaises(SelectorParseError) as ctx:
      parse_selector_literal(".members{.score > $t.min_score}")
    self.assertIn("同链祖先", str(ctx.exception))

  def test_ref_requires_ancestor_bind(self):
    with self.assertRaises(SelectorParseError) as ctx:
      parse_selector_literal(".teams[0]; $t.name")
    self.assertIn("同链祖先", str(ctx.exception))

  def test_semicolon_right_root_path(self):
    plan = parse_selector_literal(".teams[0]:$t; .teams[1].name")
    self.assertEqual(plan.bind_prefix[-1], BindStep("t"))
    self.assertEqual(
      plan.steps,
      (FieldStep("teams"), IndexStep(1), FieldStep("name")),
    )

  def test_semicolon_root_forbids_left_bind_in_filter(self):
    with self.assertRaises(SelectorParseError) as ctx:
      parse_selector_literal(
        ".teams[0]:$t; .teams[0].members{.score > $t.min_score}.name",
      )
    self.assertIn("左段", str(ctx.exception))

  def test_post_sort(self):
    plan = parse_selector_path(".members{.score > 0}@sort(-.score, .name)")
    self.assertEqual(len(plan.steps), 2)
    self.assertEqual(len(plan.post_steps), 1)
    sort = plan.post_steps[0]
    self.assertIsInstance(sort, SortStep)
    self.assertEqual(len(sort.keys), 2)
    self.assertTrue(sort.keys[0].descending)
    self.assertFalse(sort.keys[1].descending)

  def test_post_count_bare(self):
    plan = parse_selector_path(".teams@count")
    self.assertEqual(plan.post_steps, (CountStep(),))

  def test_post_count_key(self):
    plan = parse_selector_path(".members@count(.name)")
    cnt = plan.post_steps[0]
    self.assertIsInstance(cnt, CountStep)
    self.assertIsNotNone(cnt.expr)

  def test_post_group(self):
    plan = parse_selector_path(".members@group(.name)")
    grp = plan.post_steps[0]
    self.assertIsInstance(grp, GroupStep)

  def test_post_group_count_rejected(self):
    with self.assertRaises(SelectorParseError) as ctx:
      parse_selector_path(".members@group(.dept)@count")
    self.assertIn("@group 后不支持 @count", str(ctx.exception))

  def test_post_group_sort_rejected(self):
    with self.assertRaises(SelectorParseError) as ctx:
      parse_selector_path(".members@group(.name)@sort(.score)")
    self.assertIn("@group 后不支持 @sort", str(ctx.exception))

  def test_post_bind_suffix(self):
    plan = parse_selector_literal(
      ".teams[0]:$t; $t.members@sort(.name)",
    )
    self.assertIsInstance(plan, SelectorChainPlan)
    self.assertEqual(len(plan.post_steps), 1)
    self.assertIsInstance(plan.post_steps[0], SortStep)

  def test_post_sort_expr_binop(self):
    plan = parse_selector_literal(
      ".teams[0]:$t; $t.members@sort(.score - $t.min_score)",
    )
    sort = plan.post_steps[0]
    self.assertIsInstance(sort.keys[0].expr, ast.BinOp)

  def test_post_sort_parent_bind_key(self):
    plan = parse_selector_literal(
      ".teams[0]:$t; $t.members@sort($t.min_score, .name)",
    )
    sort = plan.post_steps[0]
    self.assertIsInstance(sort, SortStep)
    self.assertIn("t", sort.keys[0].bind_refs)

  def test_post_sort_forbid_prefix_bind_on_root_nav(self):
    with self.assertRaises(SelectorParseError) as ctx:
      parse_selector_literal(
        ".teams[0]:$t; .teams[0].members@sort($t.name, .name)",
      )
    self.assertIn("后处理内引用左段", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
