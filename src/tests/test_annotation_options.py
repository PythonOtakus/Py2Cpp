"""``@annotation`` 选项、MRO 展开与 ``repeatable`` 校验。"""
from __future__ import annotations

import ast
import textwrap
import unittest

from src.analysis.ir import ClassInfo
from src.passes.annotation_options import (
  AnnotationOptions,
  check_annotation_repeatable,
  collect_iter_field_names,
  filter_iter_names,
  parse_annotation_options,
  parse_self_iter_call_options,
  walk_entity_bases,
)
from src.passes.match_case import _host_iter_field_names, extract_field_annotation_meta
from src.passes.mixins import annotated_fields, is_annotation_class


class AnnotationOptionsParseTests(unittest.TestCase):
  def test_defaults(self):
    src = textwrap.dedent(
      '''
      @annotation
      class Meta:
        pass
      '''
    )
    node = ast.parse(src).body[0]
    opts = parse_annotation_options(node)
    self.assertIsNotNone(opts)
    assert opts is not None
    self.assertEqual(opts, AnnotationOptions())

  def test_inheritable_repeatable(self):
    src = textwrap.dedent(
      '''
      @annotation(inheritable=True, repeatable=True)
      class Meta:
        pass
      '''
    )
    node = ast.parse(src).body[0]
    opts = parse_annotation_options(node)
    assert opts is not None
    self.assertTrue(opts.inheritable)
    self.assertTrue(opts.repeatable)


class AnnotationMroTests(unittest.TestCase):
  def _classes(self, src: str) -> dict[str, ClassInfo]:
    mod = ast.parse(src)
    return {ci.name: ci for ci in (ClassInfo(n) for n in mod.body if isinstance(n, ast.ClassDef))}

  def test_walk_entity_bases_skips_mixin(self):
    src = textwrap.dedent(
      '''
      class Base:
        pass
      @mixin
      class Mix:
        pass
      class Host(Mix, Base):
        pass
      '''
    )
    classes = self._classes(src)
    for ci in classes.values():
      ci.is_mixin = ci.name == "Mix"
      ci.is_annotation = False
      ci.is_protocol = False
    host = classes["Host"]
    bases = walk_entity_bases(host, classes)
    self.assertEqual([b.name for b in bases], ["Base"])

  def test_collect_fields_mro(self):
    src = textwrap.dedent(
      '''
      class Base:
        a: int = 0
        b: int = 0
      class Derived(Base):
        c: int = 0
      '''
    )
    classes = self._classes(src)
    derived = classes["Derived"]
    names = collect_iter_field_names(
      derived,
      classes,
      public_only=False,
      mro=True,
      host_iter_field_names=_host_iter_field_names,
    )
    self.assertEqual(names, ["c", "a", "b"])

  def test_annotated_fields_inheritable_mro(self):
    src = textwrap.dedent(
      '''
      @annotation(inheritable=True)
      class TagMeta:
        pass
      class Base:
        score: int @TagMeta = 1
      class Derived(Base):
        title: str = "x"
      '''
    )
    classes = self._classes(src)
    for ci in classes.values():
      ci.is_annotation = is_annotation_class(ci)
      if ci.is_annotation:
        ci.annotation_options = parse_annotation_options(ci.node)
    for ci in classes.values():
      if not ci.is_annotation:
        extract_field_annotation_meta(ci)
    derived = classes["Derived"]
    self.assertEqual(
      annotated_fields(derived, "TagMeta", classes, mro=False),
      [],
    )
    self.assertEqual(
      annotated_fields(derived, "TagMeta", classes, mro=True),
      ["score"],
    )

  def test_collect_fields_glob(self):
    src = textwrap.dedent(
      '''
      class Box:
        alpha: int = 0
        beta: int = 0
        _hidden: int = 0
      '''
    )
    classes = self._classes(src)
    box = classes["Box"]
    names = collect_iter_field_names(
      box,
      classes,
      public_only=False,
      mro=False,
      glob="*a*",
      host_iter_field_names=_host_iter_field_names,
    )
    self.assertEqual(names, ["alpha", "beta"])

  def test_parse_iter_glob_option(self):
    node = ast.parse('Self.iter_fields(glob="on_*")').body[0].value
    opts = parse_self_iter_call_options(
      node,
      allowed=frozenset({"public_only", "mro", "glob"}),
      label="Self.iter_fields",
    )
    assert opts is not None
    self.assertEqual(opts.glob, "on_*")

  def test_filter_iter_names(self):
    self.assertEqual(
      filter_iter_names(["go", "apply", "draw"], "on_*"),
      [],
    )
    self.assertEqual(
      filter_iter_names(["go", "apply", "draw"], "*"),
      ["go", "apply", "draw"],
    )


class AnnotationRepeatableTests(unittest.TestCase):
  def test_duplicate_field_marker_fails(self):
    src = textwrap.dedent(
      '''
      @annotation
      class DupMeta:
        pass
      class Box:
        x: int @DupMeta @DupMeta = 0
      '''
    )
    mod = ast.parse(src)
    classes = {ci.name: ci for ci in (ClassInfo(n) for n in mod.body if isinstance(n, ast.ClassDef))}
    for ci in classes.values():
      ci.is_annotation = is_annotation_class(ci)
      if ci.is_annotation:
        ci.annotation_options = parse_annotation_options(ci.node)
    for ci in classes.values():
      if not ci.is_annotation:
        extract_field_annotation_meta(ci)

    tr = type("Tr", (), {"classes": classes})()
    with self.assertRaises(ValueError):
      check_annotation_repeatable(tr)  # type: ignore[arg-type]


if __name__ == "__main__":
  unittest.main()
