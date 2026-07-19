"""Win32 打开/保存文件对话框。"""
from ..builtins import *


@native
def pick_open_file(title: str, filter_ext: str) -> str:
  """``GetOpenFileName``；取消或失败返回 ``""``。"""
  ...

@native
def pick_save_file(title: str, filter_ext: str, default_name: str) -> str:
  """``GetSaveFileName``；取消或失败返回 ``""``。"""
  ...
