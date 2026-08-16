"""捕获形参未在 type if 中出现 → 翻译失败。"""
from py2cpp import *


def badCapture[T, _U = ...](x: T) -> int:
  if T is int:
    return 1
  else:
    return 0
