"""字段多 ``@`` 注解：``match`` 优先级与 ``UILabelMeta`` kwargs 合并。"""
from __future__ import annotations

import ast
import unittest

from src.passes.match_case import (
  field_annotation_markers_from_ann,
  merged_field_annotation_kwargs,
  resolve_field_annotation_match,
)


class MultiFieldAnnotationTests(unittest.TestCase):
  def test_markers_and_kwargs(self):
    mod = ast.parse('hp: int @UILabelMeta("HP") @UISliderMeta(0, 100) = 0')
    ann = mod.body[0]
    assert isinstance(ann, ast.AnnAssign)
    markers = field_annotation_markers_from_ann(ann.annotation)
    self.assertEqual(markers, ["UISliderMeta", "UILabelMeta"])
    kwargs = merged_field_annotation_kwargs(ann.annotation)
    self.assertEqual(kwargs["label"], "HP")
    self.assertEqual(kwargs["slider_lo"], "0")
    self.assertEqual(kwargs["slider_hi"], "100")

  def test_invisible_marker_without_call(self):
    mod = ast.parse("_seed: int @UIInvisibleMeta = 0")
    ann = mod.body[0]
    assert isinstance(ann, ast.AnnAssign)
    markers = field_annotation_markers_from_ann(ann.annotation)
    self.assertEqual(markers, ["UIInvisibleMeta"])
    markers = ["UISliderMeta", "UILabelMeta", "UIInvisibleMeta"]
    cases = {"UIInvisibleMeta": [], "UISliderMeta": [], "_": []}
    self.assertEqual(resolve_field_annotation_match(markers, cases), "UIInvisibleMeta")
    markers2 = ["UISliderMeta", "UILabelMeta"]
    self.assertEqual(resolve_field_annotation_match(markers2, cases), "UISliderMeta")
    self.assertIsNone(resolve_field_annotation_match(["UILabelMeta"], cases))


if __name__ == "__main__":
  unittest.main()
