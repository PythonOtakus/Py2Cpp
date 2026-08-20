"""集成测落盘根目录（相对进程 cwd）；``clean.bat`` 会删除 ``_test_temp/``。"""
from ..builtins import *
from ..io.path import Path

_TestTemp: str = "_test_temp"


def ensureTestTemp() -> None:
  if not Path(_TestTemp).exists():
    Path(_TestTemp).mkdir()
