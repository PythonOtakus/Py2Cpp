"""``Self.iter_methods`` / ``Self.iter_methods[Ann]`` 展开。"""
from __future__ import annotations

import ast
import textwrap
import unittest

from src.analysis.ir import ClassInfo
from src.passes.method_meta import (
  annotated_methods,
  expand_iter_methods_subscript_meta,
  expand_iter_methods_loop,
  method_meta_label,
)


class MethodMetaTests(unittest.TestCase):
  def test_annotated_methods_order(self):
    host_src = textwrap.dedent(
      '''
      class Panel:
        def alpha(self) -> None:
          pass
        @UIButtonMeta("Go")
        def go(self) -> None:
          pass
        @UIButtonMeta()
        def apply(self) -> None:
          pass
      '''
    )
    host = ClassInfo(ast.parse(host_src).body[0])
    self.assertEqual(annotated_methods(host, "UIButtonMeta"), ["go", "apply"])

  def test_method_meta_label(self):
    host_src = textwrap.dedent(
      '''
      class Panel:
        @UIButtonMeta("保存")
        def save(self) -> None:
          pass
        @UIButtonMeta()
        def apply(self) -> None:
          pass
      '''
    )
    host = ClassInfo(ast.parse(host_src).body[0])
    self.assertEqual(method_meta_label(host, "save", "UIButtonMeta"), "保存")
    self.assertEqual(method_meta_label(host, "apply", "UIButtonMeta"), "apply")

  def test_expand_iter_methods(self):
    mixin_src = textwrap.dedent(
      '''
      class M:
        def draw(self):
          for name in Self.iter_methods(public_only=True):
            x: str = name
      '''
    )
    host_src = textwrap.dedent(
      '''
      class P:
        def a(self) -> None:
          pass
        def _hidden(self) -> None:
          pass
      '''
    )
    method = ast.parse(mixin_src).body[0].body[0]
    host = ClassInfo(ast.parse(host_src).body[0])
    expanded = expand_iter_methods_loop(method, host, {"P": host})
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertEqual(dump.count("value='a'"), 1)
    self.assertNotIn("value='_hidden'", dump)

  def test_expand_iter_methods_glob(self):
    mixin_src = textwrap.dedent(
      '''
      class M:
        def draw(self):
          for name in Self.iter_methods(glob="on_*"):
            x: str = name
      '''
    )
    host_src = textwrap.dedent(
      '''
      class P:
        def on_click(self) -> None:
          pass
        def draw(self) -> None:
          pass
      '''
    )
    method = ast.parse(mixin_src).body[0].body[0]
    host = ClassInfo(ast.parse(host_src).body[0])
    expanded = expand_iter_methods_loop(method, host, {"P": host})
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("value='on_click'", dump)
    self.assertNotIn("value='draw'", dump)

  def test_expand_button_loop_btn_label(self):
    mixin_src = textwrap.dedent(
      '''
      class M:
        def on_click(self, button_label: str) -> None:
          for method in Self.iter_methods[UIButtonMeta]():
            label: str = method
            ui_btn = Self.get_method_annotation[UIButtonMeta](method)
            if ui_btn is not None and ui_btn.label:
              label = ui_btn.label
            if label == button_label:
              getattr(self, method)()
      '''
    )
    host_src = textwrap.dedent(
      '''
      class P:
        @UIButtonMeta("保存")
        def save(self) -> None:
          pass
      '''
    )
    method = ast.parse(mixin_src).body[0].body[0]
    host = ClassInfo(ast.parse(host_src).body[0])
    expanded = expand_iter_methods_subscript_meta(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("value='保存'", dump)
    self.assertIn("attr='save'", dump)

  def test_expand_button_loop(self):
    mixin_src = textwrap.dedent(
      '''
      class M:
        def draw(self, win):
          for method in Self.iter_methods[UIButtonMeta]():
            label: str = method
            ui_btn = Self.get_method_annotation[UIButtonMeta](method)
            if ui_btn is not None and ui_btn.label:
              label = ui_btn.label
            if win.button(label):
              getattr(self, method)()
      '''
    )
    host_src = textwrap.dedent(
      '''
      class P:
        @UIButtonMeta("Go")
        def go(self) -> None:
          pass
      '''
    )
    method = ast.parse(mixin_src).body[0].body[0]
    host = ClassInfo(ast.parse(host_src).body[0])
    expanded = expand_iter_methods_subscript_meta(method, host)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("value='Go'", dump)
    self.assertIn("attr='go'", dump)


if __name__ == "__main__":
  unittest.main()
