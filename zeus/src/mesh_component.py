"""``MeshComponent`` / ``CameraComponent`` 已并入 ``scene``（避免用户头循环 include）。"""
from __future__ import annotations

from .scene import CameraComponent, MeshComponent

__all__ = ["MeshComponent", "CameraComponent"]
