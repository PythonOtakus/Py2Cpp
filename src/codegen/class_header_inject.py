"""类头 ``PY2CPP_INJECT_CLASS``：``templates/**/+*.h`` 展开后注入类体尾部。"""
from __future__ import annotations

from functools import lru_cache

from ..constant.inject_discovery import discover_class_header_inject_templates
from .expand_py2cpp_template import expand_template, extract_py2cpp_inject_class_blocks


@lru_cache(maxsize=None)
def _class_header_inject_index() -> dict[tuple[str, str], tuple[str, ...]]:
  """``(module_rel, cpp_class_name)`` → 按模板顺序拼接的 inject 片段。"""
  merged: dict[tuple[str, str], list[str]] = {}
  for module_rel, template_rel in discover_class_header_inject_templates():
    expanded = expand_template(template_rel, apply_allman=False)
    for class_name, blobs in extract_py2cpp_inject_class_blocks(expanded).items():
      key = (module_rel, class_name)
      merged.setdefault(key, []).extend(blobs)
  return {key: tuple(blobs) for key, blobs in merged.items()}


def class_header_inject_blobs(module_rel: str, cpp_class_name: str) -> tuple[str, ...]:
  return _class_header_inject_index().get((module_rel, cpp_class_name), ())

