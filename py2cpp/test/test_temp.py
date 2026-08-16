"""集成测落盘根目录（相对进程 cwd）；``clean.bat`` 会删除 ``_test_temp/``。"""
from ..builtins import *
from ..io.file import mkdir
from ..io.file.path import exists

_TestTemp: str = "_test_temp"


def ensureTestTemp() -> None:
  if not exists(_TestTemp):
    mkdir(_TestTemp)
