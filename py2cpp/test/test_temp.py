"""集成测落盘根目录（相对进程 cwd）；``clean.bat`` 会删除 ``_test_temp/``。"""
from ..builtins import *
from ..io.file import mkdir
from ..io.file.path import exists

_TEST_TEMP: str = "_test_temp"


def ensure_test_temp() -> None:
  if not exists(_TEST_TEMP):
    mkdir(_TEST_TEMP)
