"""Win32 打开/保存文件对话框。"""
from ..builtins import *


@native
def pickOpenFile(title: str, filterExt: str) -> str:
  """``GetOpenFileName``；取消或失败返回 ``""``。"""
  ...

@native
def pickSaveFile(title: str, filterExt: str, defaultName: str) -> str:
  """``GetSaveFileName``；取消或失败返回 ``""``。"""
  ...
