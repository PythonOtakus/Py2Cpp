"""标准库 ``@native`` / codegen 片段注入（写入各模块 ``.inl``）。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable

from ..codegen.inject_template_emit import expanded_inject_template
from ..constant.inject_discovery import (
  discover_module_paste_after_templates,
  discover_module_paste_before_templates,
  discover_zeus_paste_after_templates,
)
from ..constant.inject_specs import (
  CLASS_PASTE_MODULE_REL,
  CLASS_PASTE_TEMPLATE_SPECS,
  PASTE_AFTER_SPECS,
  PASTE_AFTER_TO_HEADER_MODULE_RELS,
)
from ..constant.stdlib_layout import stdlib_module_path

if TYPE_CHECKING:
  from ..translator import Translator

PasteHook = Callable[["Translator"], None]


def _emit_exceptions_group_runtime(tr: Translator) -> None:
  from ..codegen.exception_group_gen import render_exception_group_impl
  from ..codegen.expand_py2cpp_template import expand_exception_repr_inl
  from .union_mro_emit import emit_union_mro_inl

  mod = stdlib_module_path("core/exceptions")
  paste_cpp_to_inl_target(tr, mod, expand_exception_repr_inl())
  with with_stdlib_inl(tr, mod):
    for info in tr.classes.values():
      if info.module_path != mod or not info.is_union_mro:
        continue
      emit_union_mro_inl(tr, info)
  paste_cpp_to_inl_target(tr, mod, render_exception_group_impl(tr))


def paste_cpp_impl(tr: Translator, impl: str) -> None:
  for line in impl.strip().splitlines():
    tr.write_line(line)
  tr.write_line()


def paste_cpp_to_inl_target(tr: Translator, module_path: str, impl: str) -> None:
  prev_inl = tr.inl_target
  tr.inl_target = module_path
  with tr._use_source():
    paste_cpp_impl(tr, impl)
  tr.inl_target = prev_inl


def paste_cpp_in_module_inl(tr: Translator, module_path: str, impl: str) -> None:
  with with_stdlib_inl(tr, module_path):
    paste_cpp_impl(tr, impl)


@contextmanager
def with_stdlib_inl(tr: Translator, module_path: str):
  with (
    tr._use_module_inl(module_path),
    tr._use_import_bindings(module_path),
    tr._use_inl_namespace(module_path),
  ):
    yield


def _chain_paste_hooks(hooks: tuple[PasteHook, ...]) -> PasteHook:
  def hook(tr: Translator) -> None:
    for fn in hooks:
      fn(tr)

  return hook


def _paste_before_template_hook(module_rel: str, template_rel: str) -> PasteHook:
  impl = expanded_inject_template(template_rel)
  module_path = stdlib_module_path(module_rel)

  def hook(tr: Translator) -> None:
    paste_cpp_to_inl_target(tr, module_path, impl)

  return hook


def _paste_after_template_hook(
  module_rel: str,
  template_rel: str,
  *,
  in_module: bool,
  module_path: str | None = None,
  templates_root: str | None = None,
) -> PasteHook:
  impl = expanded_inject_template(template_rel, templates_root)
  mp = module_path if module_path is not None else stdlib_module_path(module_rel)

  if in_module:

    def hook(tr: Translator) -> None:
      paste_cpp_in_module_inl(tr, mp, impl)

    return hook

  def hook(tr: Translator) -> None:
    paste_cpp_to_inl_target(tr, mp, impl)

  return hook


def _class_template_paste_hook(class_name: str, template_rels: tuple[str, ...]) -> PasteHook:
  module_rel = CLASS_PASTE_MODULE_REL[class_name]
  module_path = stdlib_module_path(module_rel)

  def hook(tr: Translator) -> None:
    for template_rel in template_rels:
      impl = expanded_inject_template(template_rel)
      with tr._use_module_inl(module_path), tr._use_source():
        paste_cpp_impl(tr, impl)

  return hook


def _build_paste_after_hooks() -> dict[str, PasteHook]:
  hooks: dict[str, PasteHook] = {}

  for rel, impl_key in PASTE_AFTER_SPECS:
    mp = stdlib_module_path(rel)
    if impl_key != "exceptions_group":
      raise ValueError(f"unknown PASTE_AFTER impl_key: {impl_key}")
    hooks[mp] = _emit_exceptions_group_runtime

  for module_rel, template_rel, in_module in discover_module_paste_after_templates():
    if module_rel in PASTE_AFTER_TO_HEADER_MODULE_RELS:
      continue
    mp = stdlib_module_path(module_rel)
    th = _paste_after_template_hook(module_rel, template_rel, in_module=in_module)
    if mp in hooks:
      hooks[mp] = _chain_paste_hooks((hooks[mp], th))
    else:
      hooks[mp] = th

  # Zeus：用户模块路径直接作 hook 键；注入写在模块 namespace 内（与 ui 等 in_module 一致）。
  for module_rel, template_rel, templates_root in discover_zeus_paste_after_templates():
    th = _paste_after_template_hook(
      module_rel,
      template_rel,
      in_module=True,
      module_path=module_rel,
      templates_root=templates_root,
    )
    if module_rel in hooks:
      hooks[module_rel] = _chain_paste_hooks((hooks[module_rel], th))
    else:
      hooks[module_rel] = th

  return hooks


def _build_class_paste_hooks() -> dict[str, PasteHook]:
  return {
    class_name: _class_template_paste_hook(class_name, template_rels)
    for class_name, template_rels in CLASS_PASTE_TEMPLATE_SPECS.items()
  }


def _build_paste_before_hooks() -> dict[str, PasteHook]:
  hooks: dict[str, PasteHook] = {}
  for module_rel, template_rel in discover_module_paste_before_templates():
    mp = stdlib_module_path(module_rel)
    th = _paste_before_template_hook(module_rel, template_rel)
    if mp in hooks:
      hooks[mp] = _chain_paste_hooks((hooks[mp], th))
    else:
      hooks[mp] = th
  return hooks


STDLIB_INL_PASTE_BEFORE: dict[str, PasteHook] = _build_paste_before_hooks()
STDLIB_INL_PASTE_AFTER: dict[str, PasteHook] = _build_paste_after_hooks()

STDLIB_CLASS_INL_PASTE: dict[str, PasteHook] = _build_class_paste_hooks()


def emit_stdlib_module_paste_before(tr: Translator, module_path: str) -> None:
  hook = STDLIB_INL_PASTE_BEFORE.get(module_path)
  if hook is not None:
    hook(tr)


def emit_stdlib_module_paste_after(tr: Translator, module_path: str) -> None:
  hook = STDLIB_INL_PASTE_AFTER.get(module_path)
  if hook is not None:
    hook(tr)


def emit_stdlib_class_runtime(tr: Translator, class_name: str) -> None:
  hook = STDLIB_CLASS_INL_PASTE.get(class_name)
  if hook is not None:
    hook(tr)
