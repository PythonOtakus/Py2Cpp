"""语义绑定：Syntax → HIR → MidIR。"""
from __future__ import annotations

from .bind import bind_module, lower_to_mid

__all__ = ["bind_module", "lower_to_mid"]
