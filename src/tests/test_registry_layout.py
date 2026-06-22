"""``constant`` 布局 / codegen 注入表与 ``layout_config_emit`` / ``stdlib_inject_emit`` 一致。"""
from __future__ import annotations

import unittest

from src.emit.layout_config_emit import (
  _HEADER_INL_BEFORE_NS_CLOSE,
  _HEADER_SKIP_OPERATORS_BEFORE_INL,
  _HEADER_TAIL_SKIP_UMBRELLA,
  _INL_EXTRA_OPERATORS_INL,
  _INL_SKIP_OPERATORS_H,
  _INL_SKIP_UMBRELLA,
  _JSON_API_MODULE,
  _PROTOCOL_TRAITS_MODULE,
  module_inl_extra_include_lines,
)
from src.constant.class_header_inject import CLASS_HEADER_INJECT_SPECS
from src.constant.inject_discovery import (
  discover_class_header_inject_templates,
  discover_module_paste_after_templates,
  discover_module_paste_before_templates,
)
from src.constant.inject_specs import (
  CLASS_PASTE_TEMPLATE_SPECS,
  PASTE_AFTER_SPECS,
  PASTE_BEFORE_SPECS,
)
from src.emit.stdlib_inject_emit import (
  STDLIB_CLASS_INL_PASTE as CLASS_PASTE_HOOKS,
  STDLIB_INL_PASTE_AFTER as PASTE_AFTER_HOOKS,
  STDLIB_INL_PASTE_BEFORE as PASTE_BEFORE_HOOKS,
)
from src.constant.stdlib_discovery import (
  STDLIB_REL_PATH_SET,
  is_stdlib_codegen_module,
  stdlib_module_paths_for_rel_paths,
)
from src.constant.stdlib_modules import (
  HEADER_INL_BEFORE_NS_CLOSE_PKG,
  HEADER_SKIP_OPERATORS_BEFORE_INL_REL,
  HEADER_TAIL_SKIP_UMBRELLA_REL,
  INL_EXTRA_OPERATORS_INL_REL,
  INL_SKIP_OPERATORS_H_REL,
  INL_SKIP_UMBRELLA_REL,
  JSON_API_MODULE_REL,
  MODULE_INL_PY_STR_TO_CBUF_REL,
  PROTOCOL_TRAITS_MODULE_REL,
  STDLIB_CODEGEN_MODULES,
)
from src.constant.template_module_bindings import validate_template_module_bindings
from src.constant.stdlib_layout import RUNTIME_PKG, stdlib_module_path


class RegistryLayoutTests(unittest.TestCase):
  def test_header_skip_from_constant(self):
    expected = stdlib_module_paths_for_rel_paths(HEADER_SKIP_OPERATORS_BEFORE_INL_REL)
    self.assertEqual(_HEADER_SKIP_OPERATORS_BEFORE_INL, expected)

  def test_header_inl_before_ns_close(self):
    self.assertEqual(_HEADER_INL_BEFORE_NS_CLOSE, frozenset(HEADER_INL_BEFORE_NS_CLOSE_PKG))
    self.assertIn(RUNTIME_PKG, _HEADER_INL_BEFORE_NS_CLOSE)

  def test_json_api_module(self):
    self.assertEqual(_JSON_API_MODULE, stdlib_module_path(JSON_API_MODULE_REL))

  def test_protocol_traits_module(self):
    self.assertEqual(_PROTOCOL_TRAITS_MODULE, stdlib_module_path(PROTOCOL_TRAITS_MODULE_REL))

  def test_layout_emit_module_sets(self):
    self.assertEqual(
      _HEADER_TAIL_SKIP_UMBRELLA,
      stdlib_module_paths_for_rel_paths(HEADER_TAIL_SKIP_UMBRELLA_REL),
    )
    self.assertEqual(
      _INL_SKIP_UMBRELLA,
      stdlib_module_paths_for_rel_paths(INL_SKIP_UMBRELLA_REL),
    )
    self.assertEqual(
      _INL_SKIP_OPERATORS_H,
      stdlib_module_paths_for_rel_paths(INL_SKIP_OPERATORS_H_REL),
    )
    self.assertEqual(
      _INL_EXTRA_OPERATORS_INL,
      stdlib_module_paths_for_rel_paths(INL_EXTRA_OPERATORS_INL_REL),
    )

  def test_text_str_inl_layout(self):
    mp = stdlib_module_path(MODULE_INL_PY_STR_TO_CBUF_REL)
    lines = module_inl_extra_include_lines(mp)
    self.assertEqual(len(lines), 6)
    self.assertTrue(any("protocol_traits" in ln for ln in lines))
    self.assertTrue(any("operators.h" in ln for ln in lines))
    self.assertTrue(any("util/memory" in ln for ln in lines))
    self.assertTrue(any("<stdio.h>" in ln for ln in lines))

  def test_paste_before_specs_covered(self):
    discovered = {stdlib_module_path(m) for m, _ in discover_module_paste_before_templates()}
    expected = {stdlib_module_path(rel) for rel, _ in PASTE_BEFORE_SPECS}
    expected |= discovered
    self.assertEqual(set(PASTE_BEFORE_HOOKS.keys()), expected)
    for rel, key in PASTE_BEFORE_SPECS:
      self.assertIn(rel, STDLIB_REL_PATH_SET, msg=rel)
      self.assertIn(stdlib_module_path(rel), PASTE_BEFORE_HOOKS)
    for module_rel, _ in discover_module_paste_before_templates():
      self.assertIn(module_rel, STDLIB_REL_PATH_SET, msg=module_rel)
      self.assertIn(stdlib_module_path(module_rel), PASTE_BEFORE_HOOKS)

  def test_paste_after_specs_covered(self):
    discovered = {stdlib_module_path(m) for m, _, _ in discover_module_paste_after_templates()}
    expected = {stdlib_module_path(rel) for rel, _ in PASTE_AFTER_SPECS}
    expected |= discovered
    self.assertEqual(set(PASTE_AFTER_HOOKS.keys()), expected)
    special_keys = frozenset({"exceptions_group"})
    for rel, key in PASTE_AFTER_SPECS:
      self.assertIn(rel, STDLIB_REL_PATH_SET, msg=rel)
      self.assertIn(key, special_keys, msg=key)
      self.assertIn(stdlib_module_path(rel), PASTE_AFTER_HOOKS)
    for module_rel, _, _ in discover_module_paste_after_templates():
      self.assertIn(module_rel, STDLIB_REL_PATH_SET, msg=module_rel)
      self.assertIn(stdlib_module_path(module_rel), PASTE_AFTER_HOOKS)

  def test_class_header_inject_specs_covered(self):
    for class_name, keys in CLASS_HEADER_INJECT_SPECS.items():
      for key in keys:
        self.assertIn(
          key,
          ("exception_cause_header", "base_exception_group_header", "exception_group_header"),
          msg=key,
        )
    self.assertIn(("text/str", "text/+str.h"), discover_class_header_inject_templates())
    self.assertIn(("core/exceptions", "core/+exceptions.h"), discover_class_header_inject_templates())

  def test_class_paste_specs_covered(self):
    expected_classes = set(CLASS_PASTE_TEMPLATE_SPECS)
    self.assertEqual(set(CLASS_PASTE_HOOKS.keys()), expected_classes)
    for class_name in CLASS_PASTE_TEMPLATE_SPECS:
      self.assertIn(class_name, CLASS_PASTE_HOOKS)

  def test_codegen_modules_discovered(self):
    for rel in STDLIB_CODEGEN_MODULES:
      self.assertIn(rel, STDLIB_REL_PATH_SET, msg=rel)
      self.assertTrue(is_stdlib_codegen_module(stdlib_module_path(rel)), msg=rel)

  def test_template_module_bindings(self):
    validate_template_module_bindings()


if __name__ == "__main__":
  unittest.main()
