"""``expand_iter_fields_meta``：``Self.get_field_annotation[Meta](field)`` 折叠。"""
from __future__ import annotations

import ast
import textwrap
import unittest

from src.analysis.ir import ClassInfo
from src.passes.match_case import expand_iter_fields_meta, parse_self_get_field_annotation_meta


class ExpandIterFieldsMetaTests(unittest.TestCase):
  def test_parse_get_field_annotation_subscript(self):
    mod = ast.parse("Self.get_field_annotation[UILabelMeta](field)")
    expr = mod.body[0].value
    parsed = parse_self_get_field_annotation_meta(expr)
    self.assertIsNotNone(parsed)
    assert parsed is not None
    self.assertEqual(parsed[0], "UILabelMeta")
    self.assertIsInstance(parsed[1], ast.Name)
    self.assertEqual(parsed[1].id, "field")

  def test_expand_panel_shape(self):
    mixin_src = textwrap.dedent(
      '''
      class UIPanelMixin:
        def draw(self, ctx):
          for field in Self.iter_fields(public_only=True):
            label: str = field
            ui_label = Self.get_field_annotation[UILabelMeta](field)
            if ui_label is not None:
              label = ui_label.text
            invisible = Self.get_field_annotation[UIInvisibleMeta](field)
            slider = Self.get_field_annotation[UISliderMeta](field)
            if invisible is not None:
              pass
            elif slider is not None:
              setattr(self, field, label)
            else:
              setattr(self, field, label)
      '''
    )
    host_src = textwrap.dedent(
      '''
      class Player:
        hp: int @UILabelMeta("HP") @UISliderMeta(0, 100) = 0
        enabled: bool = True
        _seed: int @UIInvisibleMeta = 0
      '''
    )
    mixin_method = ast.parse(mixin_src).body[0].body[0]
    host = ClassInfo(ast.parse(host_src).body[0])
    expanded = expand_iter_fields_meta(mixin_method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    src_dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("value='HP'", src_dump)
    self.assertNotIn("alias", src_dump)
    self.assertNotIn("value='_seed'", src_dump)

  def test_is_none_meta_guard_unrolls(self):
    mixin_src = textwrap.dedent(
      '''
      class UIPanelMixin:
        def sync(self, win):
          for field in Self.iter_fields(public_only=True):
            invisible = Self.get_field_annotation[UIInvisibleMeta](field)
            if invisible is None:
              setattr(self, field, win.synced(getattr(self, field)))
      '''
    )
    host_src = textwrap.dedent(
      '''
      class Player:
        hp: int = 0
        _seed: int @UIInvisibleMeta = 0
      '''
    )
    mixin_method = ast.parse(mixin_src).body[0].body[0]
    host = ClassInfo(ast.parse(host_src).body[0])
    expanded = expand_iter_fields_meta(mixin_method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    src_dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("synced", src_dump)
    self.assertIn("attr='hp'", src_dump)
    self.assertNotIn("attr='_seed'", src_dump)
    self.assertNotIn("value=False", src_dump)

  def test_public_only_skips_leading_underscore(self):
    mixin_src = textwrap.dedent(
      '''
      class UIPanelMixin:
        def draw(self, ctx):
          for field in Self.iter_fields(public_only=True):
            setattr(self, field, field)
      '''
    )
    host_src = textwrap.dedent(
      '''
      class Player:
        hp: int = 0
        _seed: int = 0
      '''
    )
    mixin_method = ast.parse(mixin_src).body[0].body[0]
    host = ClassInfo(ast.parse(host_src).body[0])
    expanded = expand_iter_fields_meta(mixin_method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    src_dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("value='hp'", src_dump)
    self.assertNotIn("value='_seed'", src_dump)


if __name__ == "__main__":
  unittest.main()
