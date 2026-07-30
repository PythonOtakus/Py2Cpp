"""``templates/**/+*.inl`` 注入片段：译期 ``expand_template`` + 缓存。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .expand_py2cpp_template import expand_template


@lru_cache(maxsize=None)
def expanded_inject_template(template_rel: str, templates_root: str | None = None) -> str:
  """展开 ``+*.inl``（或显式注册的 inject 模板）供 paste 写入模块 ``.inl``。

  ``templates_root`` 为绝对路径字符串时从该根读取（如 ``zeus/templates``）；``None`` 用仓库根 ``templates/``。
  """
  root = Path(templates_root) if templates_root else None
  return expand_template(template_rel, templates_root=root)
