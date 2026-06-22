"""``templates/**/+*.inl`` 注入片段：译期 ``expand_template`` + 缓存。"""
from __future__ import annotations

from functools import lru_cache

from .expand_py2cpp_template import expand_template


@lru_cache(maxsize=None)
def expanded_inject_template(template_rel: str) -> str:
  """展开 ``+*.inl``（或显式注册的 inject 模板）供 paste 写入模块 ``.inl``。"""
  return expand_template(template_rel)
