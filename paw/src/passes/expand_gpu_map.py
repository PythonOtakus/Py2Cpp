"""``.map`` 调用点校验（展开由 ``gpu_map_emit`` 完成）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator


def expand_gpu_map(tr: Translator) -> None:
  """P1：``.map`` 在 emit 阶段内联；此处预留 pass 挂载点。"""
  del tr
