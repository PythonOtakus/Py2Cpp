"""仓库与 ``py2cpp/`` 包根路径。"""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
PY2CPP_ROOT = _REPO_ROOT / "py2cpp"
